"""Runner-only demo lifecycle. Import is inert; all outward operations guarded."""
import hashlib
import errno
import socket
import ssl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from ci_fixture_setup import prepare
from container_e2e import Suite, Failure, require
from release_artifact_e2e import ReleaseSuite, guard, cleanup_project, validate_image
from browser_bootstrap import verify
from frontend_release import TESTS, STAGES
from demo_edge import Edge, public_host

ROOT=Path(__file__).resolve().parent.parent
COMPOSE='deploy/compose.demo.yaml'
LOCK=ROOT/'deploy/demo-images.json'

def private_json(path,value):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'w') as f:
        json.dump(value,f)

def lock():
    value=json.loads(LOCK.read_text())
    require(hashlib.sha256((ROOT/COMPOSE).read_bytes()).hexdigest()==value['composeSha256'],'DEMO_COMPOSE_MISMATCH')
    require(value['frontendSource']=='a15410f2eb2c7d987c142fd7e3758eb237c6c70d','DEMO_FRONTEND_SOURCE_MISMATCH')
    require(value['images']['frontend']=='bhupirao/paymesh-frontend@sha256:a3f7e6929ae7754bc1c45a6d84be626e659e68f72bc559c4a177a0029dbb25e5','DEMO_FRONTEND_DIGEST_MISMATCH')
    from release_artifact_e2e import release_lock
    old=release_lock()
    require(all(value['images'][k]==old['images'][k] for k in ('java','python','llama')),'DEMO_BACKEND_DIGEST_MISMATCH')
    return value

def validate_config(config):
    lock()
    require(set(config['services'])=={'java','python','frontend','llama','postgres'},'DEMO_SERVICE_SET_MISMATCH')
    require(set(config.get('volumes',{}))=={'container_pgdata'},'DEMO_VOLUME_SET_MISMATCH')
    for name,service in config['services'].items():
        require('build' not in service,'DEMO_BUILD_FORBIDDEN')
        if name!='postgres':require(service['image']==lock()['images'][name],'DEMO_IMAGE_MISMATCH')
        else:require(service['image']=='postgres:16.16-bookworm','DEMO_POSTGRES_MISMATCH')
        for port in service.get('ports',[]):
            require(name=='java' and port['host_ip']=='127.0.0.1' and str(port['published'])=='15500' and port['target']==15500,'DEMO_PORT_EXPOSED')

class DemoSuite(ReleaseSuite):
    def __init__(self):
        super().__init__();self.compose[-1]=COMPOSE;self.lock=lock()
    def identity(self):
        Suite.identity(self)
        ids=self.command(self.compose+['ps','-q']).decode().split()
        records=json.loads(self.command(['docker','inspect',*ids]))
        require(len(records)==5,'FIVE_HEALTHY_SERVICES_REQUIRED')
        for c in records:
            service=c['Config']['Labels']['com.docker.compose.service']
            if service=='postgres':
                require(c['Config']['Image']=='postgres:16.16-bookworm','DEMO_POSTGRES_MISMATCH');continue
            image=json.loads(self.command(['docker','image','inspect',self.lock['images'][service]]))[0]
            if service!='frontend':validate_image(c,image,service,self.lock)
            else:
                require(c['Config']['Image']==self.lock['images'][service] and c['Image']==image['Id']
                        and self.lock['images'][service] in image.get('RepoDigests',[])
                        and image['Os']=='linux' and image['Architecture']=='amd64'
                        and image['Config']['Labels']['org.opencontainers.image.revision']==self.lock['frontendSource'],'DEMO_FRONTEND_IDENTITY_MISMATCH')

def browser_gate(report):
    require(report.get('success') is True and report.get('modelInferenceVerified') is True
            and report.get('publishedImagesOnly') is True and report.get('retries')==0
            and report.get('infrastructureError') is False,'DEMO_BROWSER_GATE_FAILED')
    tests=report.get('tests',[]);steps=report.get('steps',[])
    require(len(tests)==3 and {t['code'] for t in tests}==TESTS
            and all(t['status']=='passed' and t['chromiumLaunchStatus']=='SUCCEEDED' for t in tests)
            and {s['code'] for s in steps if s.get('passed')}==STAGES,'DEMO_COMPLETE_CHROMIUM_REQUIRED')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None

def challenge(location,status):
    # A redirect alone is insufficient: require the pinned provider's Access
    # broker, HTTPS, no userinfo and an explicit login path. Never follow it.
    from urllib.parse import urlsplit
    try:p=urlsplit(location);port=p.port
    except ValueError:return False
    return status in (302,303,307) and p.scheme=='https' and p.hostname=='login.trycloudflare.com' and port in (None,443) and not p.username and p.path=='/authorize'

# The printed URL precedes cloudflared StartServer: it is not a readiness signal.
# A hard-bounded child performs each GET so DNS resolution cannot exceed the
# parent admission deadline. No cookies, credentials or proxy environment used.
PROBE_BUDGET_SECONDS=30
PROBE_ATTEMPTS=10
PROBE_ATTEMPT_SECONDS=5
TRANSIENT_NETWORK=frozenset(('DNS_TEMPORARY_FAILURE','DNS_NAME_NOT_RESOLVED',
    'CONNECTION_REFUSED','CONNECTION_RESET','NETWORK_UNREACHABLE','NETWORK_TIMEOUT','ATTEMPT_TIMEOUT'))
PROBE_NETWORK=frozenset((*TRANSIENT_NETWORK,'NONE','TLS_CERTIFICATE_REJECTED',
    'TLS_NEGOTIATION_FAILED','DNS_FAILURE','UNKNOWN_NETWORK_ERROR'))

def network_details(error):
    reason=error.reason if isinstance(error,urllib.error.URLError) else error
    number=getattr(reason,'errno',None)
    number=number if type(number) is int and -4096<=number<=4096 else None
    if isinstance(reason,ssl.SSLCertVerificationError):return 'TLS_CERTIFICATE_REJECTED',number
    if isinstance(reason,ssl.SSLError):return 'TLS_NEGOTIATION_FAILED',number
    if isinstance(reason,socket.gaierror):
        if number==socket.EAI_AGAIN:return 'DNS_TEMPORARY_FAILURE',number
        if number==socket.EAI_NONAME:return 'DNS_NAME_NOT_RESOLVED',number
        return 'DNS_FAILURE',number
    if isinstance(reason,TimeoutError):return 'NETWORK_TIMEOUT',number
    if isinstance(reason,ConnectionRefusedError):return 'CONNECTION_REFUSED',number
    if isinstance(reason,ConnectionResetError):return 'CONNECTION_RESET',number
    if isinstance(reason,OSError) and number in (errno.ENETUNREACH,errno.EHOSTUNREACH):return 'NETWORK_UNREACHABLE',number
    return 'UNKNOWN_NETWORK_ERROR',number

def probe_once(url):
    public_host(url) # Fixed provider host only; no arbitrary URL or path input.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(url+'/_demo/start',timeout=4) as response:
            status=response.status;location=response.headers.get('Location','')
    except urllib.error.HTTPError as response:
        status=response.code;location=response.headers.get('Location','');response.close()
    except (urllib.error.URLError,OSError) as error:
        category,number=network_details(error)
        return {'status':None,'location':'','networkCategory':category,'networkErrno':number}
    require(type(status) is int and 100<=status<=599 and type(location) is str
            and len(location)<=2048,'OTP_PROBE_RESPONSE_INVALID')
    return {'status':status,'location':location,'networkCategory':'NONE','networkErrno':None}

def probe_liveness(child,stopped,deadline):
    require(child.poll() is None,'DEMO_TUNNEL_EXITED')
    require(not stopped.is_set(),'DEMO_CANCELLED')
    require(time.monotonic()<deadline,'OTP_PROBE_DEADLINE_EXCEEDED')

def otp_probe(url,child,stopped,session_deadline,trace):
    public_host(url)
    deadline=min(session_deadline,time.monotonic()+PROBE_BUDGET_SECONDS)
    for attempt in range(PROBE_ATTEMPTS):
        probe_liveness(child,stopped,deadline)
        trace.probe_attempts=attempt+1
        try:
            result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'otp-probe'],
                input=json.dumps({'url':url}).encode(),capture_output=True,
                timeout=min(PROBE_ATTEMPT_SECONDS,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            # subprocess.run kills/reaps only its own child before returning.
            value={'status':None,'location':'','networkCategory':'ATTEMPT_TIMEOUT','networkErrno':None}
        else:
            require(result.returncode==0,'OTP_PROBE_EXECUTION_FAILED')
            require(len(result.stdout)<=4096,'OTP_PROBE_RESPONSE_INVALID')
            try:value=json.loads(result.stdout)
            except (ValueError,UnicodeError):raise Failure('OTP_PROBE_RESPONSE_INVALID') from None
            require(type(value) is dict and set(value)=={'status','location','networkCategory','networkErrno'}
                and type(value['networkCategory']) is str and value['networkCategory'] in PROBE_NETWORK and type(value['location']) is str
                and len(value['location'])<=2048,'OTP_PROBE_RESPONSE_INVALID')
            status=value['status'];number=value['networkErrno']
            require(status is None or type(status) is int and 100<=status<=599,'OTP_PROBE_RESPONSE_INVALID')
            require(number is None or type(number) is int and -4096<=number<=4096,'OTP_PROBE_RESPONSE_INVALID')
            require((status is None)==(value['networkCategory']!='NONE'),'OTP_PROBE_RESPONSE_INVALID')
        trace.probe_status=value['status'];trace.network_category=value['networkCategory'];trace.network_errno=value['networkErrno']
        trace.challenge_match=challenge(value['location'],value['status']) if value['status'] is not None else None
        probe_liveness(child,stopped,deadline) # Never accept a late/cancelled result.
        if trace.challenge_match:
            print('DEMO_OTP_PROBE_READY_DIAGNOSTIC='+json.dumps({'attempts':trace.probe_attempts,
                'lastTransientCategory':trace.last_transient,'validChallengeObserved':True}),flush=True)
            return value['status'],value['location']
        if value['status'] is not None:
            # Only gateway/service-unavailable responses can be readiness races;
            # auth failures and unexpected redirects fail the original gate now.
            if value['status'] not in (502,503,504):return value['status'],value['location']
            trace.last_transient='HTTP_SERVICE_NOT_READY'
        else:
            require(value['networkCategory'] in TRANSIENT_NETWORK,'OTP_PROBE_NONRETRYABLE_NETWORK_ERROR')
            trace.last_transient=value['networkCategory']
        if attempt+1==PROBE_ATTEMPTS:break
        delay=min((.5,1,2,3)[min(attempt,3)],max(0,deadline-time.monotonic()))
        stopped.wait(delay) # Interruptible, bounded, no credentials retried.
    require(False,'OTP_PROBE_ATTEMPTS_EXHAUSTED')


def terminate(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.kill();child.wait(timeout=3)
    require(child is None or child.poll() is not None,'DEMO_PUBLIC_PROCESS_STILL_RUNNING')

def closed(folder):
    path=folder/'demo-processes.json'
    if not path.exists():return not (folder/'public-access-starting.json').exists()
    record=json.loads(path.read_text())
    # PID reuse never authorizes signalling another process. A reused PID
    # remains conservatively unverified; no Docker deletion in that case.
    receipt=folder/'public-access-closed.json'
    return all(not Path('/proc/'+str(pid)).exists() for pid in record['pids']) and receipt.exists() and json.loads(receipt.read_text()).get('success') is True

def allowed_email(email):
    return len(email)<=254 and bool(re.fullmatch(r'[A-Za-z0-9.!#$%&\x27+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',email)) and ',' not in email

# Fixed vocabulary only. Exception messages and tunnel log excerpts must never
# cross into stdout/artifacts, even if a failed provider request contains secrets.
SERVE_OPERATIONS=frozenset(('BROWSER_ACCEPTANCE','FINAL_COUNTS','RECIPIENT_CONFIGURATION',
    'SESSION_BUDGET','BINARY_INTEGRITY','CLI_CAPABILITY','CREDENTIAL_READ','EDGE_STARTUP','SIGNAL_SETUP',
    'TUNNEL_LOG_SETUP','TUNNEL_SPAWN','TUNNEL_STARTUP_WAIT','PUBLIC_HOST_VALIDATION',
    'OTP_PROBE','OTP_CHALLENGE_VALIDATION','SESSION_OPEN','SESSION_ACTIVE','PUBLIC_ACCESS_SHUTDOWN'))
SERVE_FAILURES=frozenset(('DEMO_BROWSER_GATE_FAILED','DEMO_COMPLETE_CHROMIUM_REQUIRED',
    'DEMO_FINAL_COUNTS_REQUIRED','EXACT_DEMO_EMAIL_REQUIRED','DEMO_DURATION_INVALID',
    'DEMO_ADMISSION_DEADLINE_EXCEEDED','CLOUDFLARED_CHECKSUM_MISMATCH',
    'QUICK_TUNNEL_EMAIL_AUTH_UNSUPPORTED','DEMO_TUNNEL_EXITED','DEMO_TUNNEL_LOG_LIMIT',
    'PROTECTED_TUNNEL_NOT_ESTABLISHED','OTP_ACCESS_GATE_UNVERIFIED','DEMO_EXPIRED',
    'DEMO_PUBLIC_PROCESS_STILL_RUNNING','DEMO_CANCELLED','OTP_PROBE_DEADLINE_EXCEEDED',
    'OTP_PROBE_EXECUTION_FAILED','OTP_PROBE_RESPONSE_INVALID','OTP_PROBE_NONRETRYABLE_NETWORK_ERROR',
    'OTP_PROBE_ATTEMPTS_EXHAUSTED'))

def error_code(error):
    from container_e2e import Failure
    if isinstance(error,Failure) and len(error.args)==1 and type(error.args[0]) is str and error.args[0] in SERVE_FAILURES:
        return error.args[0]
    if isinstance(error,subprocess.TimeoutExpired):return 'SUBPROCESS_TIMEOUT'
    if isinstance(error,urllib.error.HTTPError):return 'OTP_PROBE_HTTP_ERROR'
    if isinstance(error,urllib.error.URLError):return 'OTP_PROBE_NETWORK_ERROR'
    if isinstance(error,TimeoutError):return 'OPERATION_TIMEOUT'
    if isinstance(error,OSError):return 'LOCAL_OS_OPERATION_FAILED'
    if isinstance(error,ValueError):return 'INVALID_LOCAL_STATE'
    return 'UNCLASSIFIED_SERVE_ERROR'

class ServeTrace:
    def __init__(self):
        self.operation='BROWSER_ACCEPTANCE';self.child=None;self.log=None
        self.probe_status=None;self.challenge_match=None;self.access_opened=False
        self.probe_attempts=0;self.network_category='NONE';self.network_errno=None;self.last_transient='NONE'
        self.started=time.monotonic();self.failure=None
    def at(self,code):
        require(code in SERVE_OPERATIONS,'UNKNOWN_DEMO_OPERATION')
        self.operation=code
    def capture(self,error):
        if self.failure is not None:return
        code=self.child.poll() if self.child is not None else None
        state='NOT_STARTED' if self.child is None else 'RUNNING' if code is None else 'EXITED'
        if type(code) is not int or not -255<=code<=255:code=None
        raw=b''
        if self.log is not None:
            try:
                with self.log.open('rb') as stream:raw=stream.read(262144)
            except OSError:pass
        lower=raw.lower();category='UNCLASSIFIED_OR_NO_TUNNEL_OUTPUT'
        for marker,fixed in (
            (b'flag provided but not defined','CLI_ARGUMENT_REJECTED'),
            (b'--allowed-mail is only supported for quick tunnels','CLI_ARGUMENT_REJECTED'),
            (b'validate quick tunnel recipient policy','RECIPIENT_POLICY_REJECTED'),
            (b'initialize quick tunnel assertion validator','AUTH_VALIDATOR_INITIALIZATION_FAILED'),
            (b'initialize quick tunnel authentication handler','AUTH_HANDLER_INITIALIZATION_FAILED'),
            (b'initialize quick tunnel session manager','AUTH_SESSION_INITIALIZATION_FAILED'),
            (b'initialize quick tunnel state manager','AUTH_STATE_INITIALIZATION_FAILED'),
            (b'failed to request quick tunnel','QUICK_TUNNEL_REQUEST_FAILED'),
            (b'error parsing yaml in config file','CONFIGURATION_PARSE_FAILED')):
            if marker in lower:category=fixed;break
        types={'Failure','Denied','TimeoutExpired','URLError','HTTPError','TimeoutError',
            'FileNotFoundError','PermissionError','ConnectionRefusedError','OSError',
            'ValueError','JSONDecodeError','RuntimeError'}
        kind=type(error).__name__
        kind=kind if kind in types else 'UNCLASSIFIED_EXCEPTION'
        number=getattr(error,'errno',None)
        number=number if type(number) is int and -4096<=number<=4096 else None
        self.failure={'success':False,'operationCode':self.operation,'failureCode':error_code(error),
            'exceptionType':kind,'osErrorNumber':number,
            'elapsedMs':min(3600000,max(0,int((time.monotonic()-self.started)*1000))),
            'tunnelProcessState':state,'tunnelExitCodeAtFailure':code,
            'protectedStartupObserved':b'Your protected quick Tunnel has been created!' in raw,
            'hostnameObserved':bool(re.search(rb'https://[a-z0-9-]+[.]trycloudflare[.]com',raw)),
            'tunnelOutputCategory':category,'otpProbeHttpStatus':self.probe_status,
            'otpChallengeMatched':self.challenge_match,'accessOpened':self.access_opened,
            'otpProbeAttempts':self.probe_attempts,'networkFailureCategory':self.network_category,
            'networkErrorNumber':self.network_errno,'lastTransientCategory':self.last_transient,
            'rawLogsRetained':False}
    def emit(self,folder):
        if self.failure is None:return
        private_json(folder/'sanitized-demo-serve.json',self.failure)
        print('DEMO_SERVE_FAILURE_DIAGNOSTIC='+json.dumps(self.failure,sort_keys=True),flush=True)

def serve(suite):
    trace=ServeTrace()
    try:return _serve(suite,trace)
    except Exception as error:
        trace.capture(error)
        try:trace.emit(suite.folder)
        except Exception:print('DEMO_SERVE_DIAGNOSTIC_UNAVAILABLE',flush=True)
        raise


def _serve(suite,trace):
    folder=suite.folder
    browser_gate(json.loads((folder/'sanitized-browser.json').read_text()))
    trace.at('FINAL_COUNTS')
    require(json.loads((folder/'sanitized-browser-final.json').read_text()).get('success') is True,'DEMO_FINAL_COUNTS_REQUIRED')
    trace.at('RECIPIENT_CONFIGURATION')
    email=os.environ.pop('DEMO_ALLOWED_EMAIL','')
    require(allowed_email(email),'EXACT_DEMO_EMAIL_REQUIRED')
    trace.at('SESSION_BUDGET')
    minutes=os.environ.get('DEMO_MINUTES','10');require(minutes in ('5','10','15'),'DEMO_DURATION_INVALID')
    started=json.loads((folder/'demo-created.json').read_text())['created']
    remaining=started+45*60-time.time()
    require(remaining>=120,'DEMO_ADMISSION_DEADLINE_EXCEEDED')
    deadline=time.monotonic()+min(int(minutes)*60,remaining)
    trace.at('BINARY_INTEGRITY')
    spec=json.loads((ROOT/'deploy/cloudflared-demo.json').read_text());binary=folder/'cloudflared'
    require(hashlib.sha256(binary.read_bytes()).hexdigest()==spec['sha256'],'CLOUDFLARED_CHECKSUM_MISMATCH')
    trace.at('CLI_CAPABILITY')
    result=subprocess.run([str(binary),'tunnel','--help'],capture_output=True,timeout=10)
    require(result.returncode==0 and b'--allowed-mail' in result.stdout,'QUICK_TUNNEL_EMAIL_AUTH_UNSUPPORTED')
    trace.at('CREDENTIAL_READ')
    credentials=[('Admin','ci-admin@e2e.example.test',(folder/'secrets/admin_password').read_text()),('Merchant','browser-a@e2e.example.test',(folder/'secrets/merchant_password').read_text())]
    trace.at('EDGE_STARTUP')
    server=Edge(ROOT,credentials,deadline);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    child=None;stopped=threading.Event()
    def stop(*args):stopped.set()
    trace.at('SIGNAL_SETUP')
    previous={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
    log=folder/'private-tunnel.log';trace.log=log
    trace.at('TUNNEL_LOG_SETUP')
    try:
        with os.fdopen(os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as output:
            # No config file/account token; exact recipient, never a domain/wildcard.
            private_json(folder/'public-access-starting.json',{'attempted':True})
            trace.at('TUNNEL_SPAWN')
            child=subprocess.Popen([str(binary),'--no-autoupdate','tunnel','--config','/dev/null','--url','http://127.0.0.1:15501','--allowed-mail',email],stdout=output,stderr=output)
            trace.child=child
            private_json(folder/'demo-processes.json',{'pids':[child.pid]})
            trace.at('TUNNEL_STARTUP_WAIT')
            until=time.monotonic()+90;url=None
            while time.monotonic()<until and not stopped.is_set():
                require(child.poll() is None,'DEMO_TUNNEL_EXITED')
                require(log.stat().st_size<=262144,'DEMO_TUNNEL_LOG_LIMIT')
                raw=log.read_text(errors='replace')
                matches=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',raw)
                if matches and 'Your protected quick Tunnel has been created!' in raw:
                    url=matches[0];break
                stopped.wait(.5)
            require(url is not None and not stopped.is_set(),'PROTECTED_TUNNEL_NOT_ESTABLISHED')
            trace.at('PUBLIC_HOST_VALIDATION')
            server.host=public_host(url)
            # Server remains locked until the unauthenticated internet probe
            # proves the Access challenge is before the origin.
            trace.at('OTP_PROBE')
            status,location=otp_probe(url,child,stopped,deadline,trace)
            trace.probe_status=status if type(status) is int and 100<=status<=599 else None
            trace.challenge_match=challenge(location,status)
            trace.at('OTP_CHALLENGE_VALIDATION')
            require(challenge(location,status),'OTP_ACCESS_GATE_UNVERIFIED')
            require(time.monotonic()<deadline and not stopped.is_set(),'DEMO_EXPIRED')
            trace.at('SESSION_OPEN')
            server.active=True;trace.access_opened=True
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
                summary.write('## Temporary authenticated acceptance demo\n\nEmail OTP is required. Synthetic credentials are available only behind that gate.\n\n'+url+'/_demo/start\n\n'+url+'/merchant/login\n\n'+url+'/admin/login\n\n'+url+'/docs/\n\nMaximum access: '+minutes+' minutes; ends earlier on cancellation or failure.\n')
            # Step summaries may appear only after the blocking step ends.
            # This validated base entry URL is intentionally public; no email,
            # credential, auth state, payment link or checkout token is included.
            print('DEMO_AUTHENTICATED_ENTRY='+url+'/_demo/start',flush=True)
            print('DEMO_OTP_GATE_VERIFIED_ACCESS_OPEN',flush=True)
            trace.at('SESSION_ACTIVE')
            while time.monotonic()<deadline and not stopped.wait(.5):
                require(child.poll() is None,'DEMO_TUNNEL_EXITED')
                require(log.stat().st_size<=262144,'DEMO_TUNNEL_LOG_LIMIT')
    except Exception as error:
        trace.capture(error) # Capture natural exit status BEFORE owned termination.
        raise
    finally:
        trace.at('PUBLIC_ACCESS_SHUTDOWN')
        server.active=False
        terminate(child) # Public access closes before database/container teardown.
        server.shutdown();server.server_close();thread.join(timeout=3)
        private_json(folder/'public-access-closed.json',{'success':True,'reason':'expired_cancelled_or_finished','publicProcessExited':True})
        for s,handler in previous.items():signal.signal(s,handler)
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
            summary.write('\n**Session closed.** The temporary URL is no longer usable. Require the separate cleanup receipt for container/volume absence.\n')
        print('DEMO_PUBLIC_ACCESS_CLOSED',flush=True)

def main(action):
    guard();lock()
    if action=='otp-probe':
        raw=sys.stdin.buffer.read(2049);require(len(raw)<=2048,'OTP_PROBE_RESPONSE_INVALID')
        value=json.loads(raw);require(type(value) is dict and set(value)=={'url'} and type(value['url']) is str,'OTP_PROBE_RESPONSE_INVALID')
        print(json.dumps(probe_once(value['url'])),flush=True);return 0
    if action=='fixtures':
        prepare()
        # GITHUB_ENV is consumed only by the NEXT Actions step.
        from ci_fixture_setup import runner_project
        folder=Path(os.environ['RUNNER_TEMP'])/runner_project()
        private_json(folder/'demo-created.json',{'created':time.time()});return 0
    suite=DemoSuite()
    if action in ('seed','final'):return verify(suite,action)
    if action=='serve':serve(suite);return 0
    if action=='cleanup':
        require(closed(suite.folder),'PUBLIC_ACCESS_CLOSURE_UNVERIFIED_NO_CLEANUP')
        return cleanup_project(suite.project,suite.folder,compose_file=COMPOSE,validate_config=validate_config)
    if action=='diagnostics':
        # Fixed fields only: no raw application/tunnel logs in public artifacts.
        private_json(suite.folder/'sanitized-demo-failure.json',{'success':False,'failureCode':'DEMO_STAGE_FAILED','rawLogsRetained':False});return 0
    require(False,'UNKNOWN_DEMO_ACTION')

if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1] if len(sys.argv)==2 else ''))
    except Exception:
        print('DEMO_GUARD_OR_OPERATION_FAILED_NO_RAW_OUTPUT');raise SystemExit(1)
