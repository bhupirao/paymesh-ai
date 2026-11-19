"""Failure-only, bounded, redacted diagnostics for the disposable CI project.
Never writes raw output or uploads environment/configuration files.
"""
import json,os,re,selectors,subprocess,time
from pathlib import Path
from ci_fixture_setup import runner_project
MAX_CAPTURE=128*1024
TAIL_LINES=200
SECRET_NAMES=('db_password','ai_token','razorpay_secret','stripe_secret','settlement_token','admin_password','merchant_password','jwt_private','jwt_public')

def secret_values(folder):
    directory=folder/'secrets'
    if directory.is_symlink() or directory.stat().st_mode&0o077:raise ValueError('PRIVATE_SECRET_DIRECTORY_REQUIRED')
    values=[]
    for name in SECRET_NAMES:
        p=directory/name
        if p.is_symlink() or not p.is_file() or p.stat().st_uid!=os.getuid() or p.stat().st_mode&0o022 or not 8<=p.stat().st_size<=16384:raise ValueError('SECRET_INVENTORY_UNAVAILABLE')
        value=p.read_text().strip()
        if len(value)<8:raise ValueError('SECRET_INVENTORY_UNAVAILABLE')
        values.extend([value,json.dumps(value)[1:-1]])
        # Timestamped/escaped PEM lines still reveal key material unless each
        # body line is removed independently of its surrounding block.
        if 'KEY-----' in value:values.extend(s for s in value.splitlines() if len(s)>=16 and not s.startswith('-----'))
    return sorted(set(values),key=len,reverse=True)

def redact(text,values):
    for value in values:text=text.replace(value,'[REDACTED]')
    text=re.sub(r'-----BEGIN [A-Z ]*KEY-----[\s\S]*?(?:-----END [A-Z ]*KEY-----|\Z)','[REDACTED KEY]',text)
    text=re.sub(r'(?m)^\s*[A-Za-z0-9+/]{40,}={0,2}\s*$','[REDACTED ENCODED MATERIAL]',text)
    text=re.sub(r'\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b','[REDACTED JWT]',text)
    text=re.sub(r'(?i)\b(?:Bearer|Basic)\s+[^\s,;"\']+','[REDACTED AUTHORIZATION]',text)
    text=re.sub(r'(?im)((?:set-cookie|cookie)\s*[:=])[^\r\n]*',r'\1 [REDACTED]',text)
    text=re.sub(r'''(?ix)(["']?[\w.-]*(?:password|passwd|secret|token|api[_-]?key|credential)[\w.-]*["']?\s*[:=]\s*)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;&]+)''',r'\1[REDACTED]',text)
    text=re.sub(r'(?i)([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@',r'\1[REDACTED]@',text)
    return text

def capture(args,limit=MAX_CAPTURE,timeout=15):
    """Bound memory and elapsed time; stop only this newly spawned read-only CLI."""
    child=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    data=bytearray();truncated=False;timed_out=False;selector=selectors.DefaultSelector();selector.register(child.stdout,selectors.EVENT_READ);deadline=time.monotonic()+timeout
    try:
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:timed_out=True;break
            events=selector.select(min(remaining,.25))
            if not events:continue
            block=os.read(child.stdout.fileno(),min(8192,limit+1-len(data)))
            if not block:break
            data.extend(block)
            if len(data)>limit:truncated=True;break
    finally:
        selector.close();child.stdout.close()
        if child.poll() is None and not (truncated or timed_out):
            try:child.wait(timeout=.5)
            except subprocess.TimeoutExpired:pass
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)
    raw=bytes(data[:limit])
    # Drop a partial last line so a cut secret prefix cannot escape full-value masking.
    if truncated or timed_out:raw=raw.rsplit(b'\n',1)[0] if b'\n' in raw else b''
    text=raw.decode('utf-8',errors='replace')
    if truncated:text+='\n[CAPTURE TRUNCATED]\n'
    if timed_out:text+='\n[CAPTURE TIMED OUT]\n'
    return text,{'exitCode':child.returncode,'truncated':truncated,'timedOut':timed_out}

def write(path,text):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'w') as out:out.write(text)

def collect():
    project=runner_project();temp=Path(os.environ['RUNNER_TEMP']).resolve();folder=temp/project
    if os.environ.get('E2E_PROJECT')!=project or Path(os.environ.get('E2E_DIR','')).resolve()!=folder or Path(os.environ.get('E2E_ENV','')).resolve()!=folder/'container.env' or folder.is_symlink():raise ValueError('RUNNER_PROJECT_MISMATCH')
    output=folder/'diagnostics';output.mkdir(mode=0o700,exist_ok=False)
    status={'project':project,'rawLogsWritten':False,'environmentFilesIncluded':False,'commands':{}}
    try:values=secret_values(folder)
    except Exception:
        status['status']='REDACTION_UNAVAILABLE_NO_LOGS_CAPTURED'
        write(output/'status.json',json.dumps(status,indent=2));return
    compose=['docker','compose','--project-name',project,'--env-file',str(folder/'container.env'),'-f','deploy/compose.yaml']
    def save(name,args):
        try:
            text,meta=capture(args);clean=redact(text,values)
            # Fail closed if any full known value survived sanitization.
            if any(value in clean for value in values):raise ValueError('REDACTION_FAILED')
            if len(clean.encode())>MAX_CAPTURE:
                clean=clean.encode()[:MAX_CAPTURE].decode('utf-8',errors='ignore').rsplit('\n',1)[0]+'\n[REDACTED OUTPUT TRUNCATED]\n';meta['redactedOutputTruncated']=True
            write(output/name,clean);status['commands'][name]=meta
        except Exception:
            status['commands'][name]={'captureStatus':'UNAVAILABLE'};return ''
    save('compose-ps.log',compose+['ps','-a'])
    for service in ('java','postgres','python','llama','frontend'):
        save(service+'.log',compose+['logs','--no-color','--timestamps','--tail',str(TAIL_LINES),service])
    try:
        raw,_=capture(compose+['ps','-a','-q'],limit=8192,timeout=10)
        ids=raw.split()
        if not ids or len(ids)>5 or any(not re.fullmatch('[0-9a-f]{12,64}',s) for s in ids):raise ValueError('UNEXPECTED_CONTAINER_IDS')
        # Select ONLY exit/health fields. Never inspect .Config.Env or raw config.
        fmt='{"id":{{json .Id}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"status":{{json .State.Status}},"exitCode":{{json .State.ExitCode}},"oomKilled":{{json .State.OOMKilled}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"unavailable"{{end}},"error":{{json .State.Error}}}'
        save('container-state.log',['docker','inspect','--format',fmt,*ids])
    except Exception:status['commands']['container-state.log']={'captureStatus':'UNAVAILABLE'}
    status['status']='REDACTED_DIAGNOSTICS_CAPTURED';write(output/'status.json',json.dumps(status,indent=2))

if __name__=='__main__':
    try:collect();print('FAILURE_DIAGNOSTICS_FINISHED_NO_RAW_OUTPUT')
    except Exception:print('FAILURE_DIAGNOSTICS_UNAVAILABLE_NO_RAW_OUTPUT')
