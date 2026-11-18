"""Frozen forward-only cold start. Inert on import; no backups, restores or inference.
Application startup/degraded recovery requires separate explicit operator approval.
"""
import getpass,hashlib,hmac,json,os,re,shlex,stat,subprocess,sys,tempfile,time,warnings
from pathlib import Path
from phase673_otp_ops import Stop,protected
from phase697a_process import MacOS,snapshot,assert_same
from ai_reliability_forward import Forward,digest

CONFIRM={'start':'COLD_START_VERIFIED_FORWARD_RELEASE_NO_EXACT_ROLLBACK','degrade':'NEW_RELEASE_CHAT_DISABLED_FORWARD_RECOVERY_ONLY'}
def env_file(path):
 out={}
 for line in protected(Path(path)).read_text().splitlines():
  line=line.strip()
  if not line or line.startswith('#'):continue
  k,sep,v=line.removeprefix('export ').partition('=')
  if not sep or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',k) or k in out:raise Stop('Unsupported protected environment syntax.')
  words=shlex.split(v)
  if len(words)!=1 or '`' in v or '$(' in v:raise Stop('Unsupported protected environment expression.')
  out[k]=words[0].replace('${HOME}',str(Path.home())).replace('$HOME',str(Path.home()))
 return out

def configs(release,m,password,enabled=True):
 private=Path.home()/'.config/paymesh-demo'
 demo=env_file(private/'demo.env');secret=env_file(private/'secrets.env');py=env_file(Path(m['pythonChatFile']))
 props={}
 for line in protected(Path(m['javaChatFile'])).read_text().splitlines():
  if line and not line.startswith('#'):
   key,sep,value=line.partition('=')
   if not sep or key in props:raise Stop('Invalid private Java properties.')
   props[key]=value
 token=py.get('PAYMESH_AI_CHAT_SERVICE_TOKEN','')
 if not re.fullmatch('[A-Za-z0-9_-]{64,128}',token) or not hmac.compare_digest(token,props.get('paymesh.ai.chat.service-token','')):raise Stop('Private Java/Python credentials mismatch.')
 common={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8'}
 java=dict(common)
 for key in ('PAYMESH_DB_USER','PAYMESH_JWT_PRIVATE_KEY_FILE','PAYMESH_JWT_PUBLIC_KEY_FILE','PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED'):
  if not demo.get(key) or '$' in demo[key]:raise Stop('Required demo runtime configuration missing.')
  java[key]=demo[key]
 for key in ('PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN'):
  if not secret.get(key):raise Stop('Existing protected gateway/refund configuration missing.')
  java[key]=secret[key]
 java.update(PAYMESH_DB_URL='jdbc:postgresql://127.0.0.1:5432/paymesh_demo',PAYMESH_DB_PASSWORD=password,SPRING_PROFILES_ACTIVE='demo',PORT='18080',PAYMESH_SETTLEMENT_SCHEDULING_ENABLED='false',PAYMESH_AI_ENABLED='true',PAYMESH_AI_BASE_URL='http://127.0.0.1:8000')
 python=dict(common,**m['pythonSettings']);python.update(PAYMESH_AI_CHAT_SERVICE_TOKEN=token,PAYMESH_AI_CHAT_API_ENABLED='true' if enabled else 'false',PYTHONDONTWRITEBYTECODE='1',__PYVENV_LAUNCHER__=str(release/'python/.venv/bin/python'))
 args=[m['javaExecutable'],'-jar',str(release/'java/paymesh.jar')]+m['javaFlags']+['--paymesh.ai.chat.enabled='+('true' if enabled else 'false')]
 return java,python,args

def empty_ports():
 for port in (8082,8000,18080,5500):
  r=subprocess.run(['/usr/sbin/lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-Fpn'],capture_output=True)
  if r.stdout or r.returncode not in (0,1):raise Stop('An application port is occupied; do not start a duplicate.')

def prompt_password():
 with open('/dev/tty','w') as tty,warnings.catch_warnings():
  warnings.simplefilter('error',getpass.GetPassWarning)
  p=getpass.getpass('PostgreSQL password for paymesh_demo_user (not saved): ',stream=tty)
 if not p:raise Stop('Empty password; no authentication attempted.')
 return p

class Cold(Forward):
 def baseline(self,password):
  from v14_backup_reader import snapshot as read_only_snapshot
  data=read_only_snapshot(password)
  if data['history']!=self.m['migrationHistory'] or data['fingerprints']!=self.m['databaseBaseline']['fingerprints'] or data['counts']!=self.m['databaseBaseline']['tableCounts']:raise Stop('Current V14 data differs from approved backup baseline.')
  return data
 def inspect(self,name,identity):
  s=snapshot(identity[0],self.native)
  if list(s.identity)!=identity:raise Stop('Service identity changed.')
  lines=self.listeners(self.m['ports'][name]).splitlines()
  if [x for x in lines if x.startswith('p')]!=['p'+str(s.identity[0])] or [x for x in lines if x.startswith('n')]!=['n127.0.0.1:'+str(self.m['ports'][name])]:raise Stop('Application listener is not exact IPv4 loopback.')
  expected_cwd=str(self.release/self.m['cwd'][name]) if not Path(self.m['cwd'][name]).is_absolute() else self.m['cwd'][name]
  r=subprocess.run(['/usr/sbin/lsof','-a','-p',str(s.identity[0]),'-d','cwd','-Fn'],capture_output=True,text=True)
  if [x[1:] for x in r.stdout.splitlines() if x.startswith('n')]!=[expected_cwd]:raise Stop('Unexpected service working directory.')
  return s
 def launch(self,name,args,env):
  port=self.m['ports'][name]
  if self.listeners(port):raise Stop('Port occupied; replacement not started.')
  cwd=Path(self.m['cwd'][name]);cwd=cwd if cwd.is_absolute() else self.release/cwd
  with os.fdopen(os.open(self.folder/(name+'.log'),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as log:
   child=subprocess.Popen(args,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  self.e[name+'Pid']=child.pid;self.write()
  identity=snapshot(child.pid,self.native);self.e[name+'Identity']=list(identity.identity);self.write()
  deadline=time.monotonic()+self.m['startupTimeoutSeconds'][name]
  while time.monotonic()<deadline:
   if child.poll() is not None:raise Stop('Service exited; no automatic restart.')
   if self.listeners(port):
    s=self.inspect(name,list(identity.identity))
    if s.argv[1:]!=tuple(args[1:]) or s.environment!=env:raise Stop('Started launch state differs from reviewed configuration.')
    # Bounded health polling belongs to one startup attempt; no inference or process retry.
    try:
     endpoint='/actuator/health/readiness' if name=='java' else '/health' if name in ('ai','llm') else '/'
     if name=='frontend':
      with self.http.open('http://127.0.0.1:5500/',timeout=5) as r:
       if r.status==200:return s
     else:
      h=self.health(endpoint,port)
      if h.get('status') in ('UP','ok'):return s
    except Stop:pass
   time.sleep(1)
  raise Stop('Bounded startup health deadline expired; no automatic retry.')
 def retained(self,evidence,name):
  identity=evidence.get(name+'Identity')
  if not identity:
   if evidence.get(name+'Pid') or self.listeners(self.m['ports'][name]):raise Stop('Unfenced retained service requires separate review.')
   return None
  r=subprocess.run(['/bin/ps','-p',str(identity[0]),'-o','stat='],capture_output=True,text=True)
  if not r.stdout.strip() or r.stdout.strip().startswith('Z'):
   if self.listeners(self.m['ports'][name]):raise Stop('Unexpected retained-service listener.')
   return None
  return self.inspect(name,identity)
 def run_cold(self,mode,prior=None):
  self.check()
  if digest(protected(Path(self.m['backup']['path'])))!=self.m['backup']['sha256'] or digest(protected(Path(self.m['backupEvidence'])))!=self.m['backupEvidenceSha256']:raise Stop('Protected backup/evidence changed.')
  if not sys.stdin.isatty() or not sys.stdout.isatty():raise Stop('Operator terminal required.')
  if input('Type NO_PUBLIC_PROXY_OR_TUNNEL: ').strip()!='NO_PUBLIC_PROXY_OR_TUNNEL' or input('Type '+CONFIRM[mode]+': ').strip()!=CONFIRM[mode]:raise Stop('Operator approval missing.')
  if mode=='start':empty_ports()
  evidence=None
  if mode=='degrade':
   source=protected(Path(prior));evidence=json.loads(source.read_text())
   if evidence.get('releaseManifestSha256')!=digest(self.release/'release-manifest.json'):raise Stop('Recovery evidence belongs to another release.')
   # Never guess which partial process can safely be stopped.
   for n in ('java','ai'):
    if n+'Pid' in evidence and n+'Identity' not in evidence:raise Stop('Unfenced partial child requires separate recovery review.')
  password=prompt_password();before=self.baseline(password)
  java_env,py_env,java_args=configs(self.release,self.m,password,mode=='start')
  self.folder=Path(tempfile.mkdtemp(prefix='ai-reliability-cold-'+mode+'-',dir=self.private));os.chmod(self.folder,0o700)
  self.e.update(stage='pre-start',mode=mode,releaseManifestSha256=digest(self.release/'release-manifest.json'),databaseBefore=before['fingerprints'],indexBefore=digest(Path.home()/'Developer/paymesh-ai/.git/index'));self.write()
  try:
   model_env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8'}
   if mode=='start':
    self.e['stage']='llama-start';self.write();llm=self.launch('llm',self.m['llamaCommand'],model_env)
   else:
    llm=self.retained(evidence,'llm')
    frontend=self.retained(evidence,'frontend')
    for name,service in [('llm',llm),('frontend',frontend)]:
     if service:self.e[name+'Identity']=list(service.identity)
    for n in ('java','ai'):
     if n+'Identity' in evidence:
      ident=evidence[n+'Identity'];r=subprocess.run(['/bin/ps','-p',str(ident[0]),'-o','stat='],capture_output=True,text=True)
      if r.stdout.strip() and not r.stdout.strip().startswith('Z'):self.stop(self.inspect(n,ident),self.m['ports'][n])
      elif self.listeners(self.m['ports'][n]):raise Stop('Unexpected recovery listener.')
     elif self.listeners(self.m['ports'][n]):raise Stop('Unrecorded process must not be stopped.')
   sink=self.folder/'chat-validation-diagnostics.jsonl';fd=os.open(sink,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd);py_env['PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE']=str(sink)
   self.e['stage']='python-start';self.write();ai=self.launch('ai',[str(self.release/'python/.venv/bin/python'),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log'],py_env)
   if 'post' not in self.health('/openapi.json',8000).get('paths',{}).get('/api/v1/chat',{}):raise Stop('Private chat route missing.')
   self.e['stage']='java-start';self.write();java=self.launch('java',java_args,java_env)
   if self.health('/api/v1/payments/health',18080).get('status')!='RUNNING' or self.health('/api/v1/auth/password/capabilities',18080).get('localDemoEnabled') is not False:raise Stop('Payment health or OTP safety gate failed.')
   if mode=='start' or frontend is None:
    self.e['stage']='frontend-start';self.write();frontend=self.launch('frontend',[self.m['frontendPython'],'-B',str(self.release/'frontend/dev_server.py')],dict(model_env,__PYVENV_LAUNCHER__=self.m['frontendPython'],PYTHONDONTWRITEBYTECODE='1'))
   if frontend is None:raise Stop('Frontend was not started; separate reviewed recovery required.')
   for path in ('/merchant/ai','/admin/ai'):
    with self.http.open('http://127.0.0.1:5500'+path,timeout=5) as r:
     if r.status!=200:raise Stop('Frontend route failed.')
   import urllib.error
   for role in ('merchant','admin'):
    path='/api/v1/'+role+'/ai/conversations?page=0&size=5'
    try:self.http.open('http://127.0.0.1:5500'+path,timeout=5);raise Stop('Unauthenticated conversation boundary unexpectedly open.')
    except urllib.error.HTTPError as error:
     if error.code not in (401,403):raise Stop('Conversation proxy/authorization check failed.')
   after=self.baseline(password);password=None;java_env.pop('PAYMESH_DB_PASSWORD',None)
   if after!=before:raise Stop('Database baseline changed; do not restore automatically.')
   for name,s in [('llm',llm),('ai',ai),('java',java),('frontend',frontend)]:
    if s:self.inspect(name,list(s.identity))
   self.e.update(success=True,stage='verified',databaseUnchanged=True,chatEnabled=mode=='start',llamaAvailable=llm is not None,privateAuthenticationConfigurationMatches=True,indexAfter=digest(Path.home()/'Developer/paymesh-ai/.git/index'))
   self.write();print('COLD_START_READY_NO_INFERENCE' if mode=='start' else 'NEW_RELEASE_CHAT_DISABLED_NOT_OLD_ROLLBACK')
  finally:self.write();print('Protected evidence: '+str(self.folder/'evidence.json'))

def main():
 try:
  if len(sys.argv) not in (3,4) or sys.argv[1] not in CONFIRM:raise Stop('Expected start|degrade and frozen release directory.')
  if (sys.argv[1]=='start')!=(len(sys.argv)==3):raise Stop('Degraded recovery requires explicit prior cold-start evidence.')
  Cold(sys.argv[2]).run_cold(sys.argv[1],sys.argv[3] if len(sys.argv)==4 else None);return 0
 except (Exception,KeyboardInterrupt):print('STOPPED_NO_RETRY_NO_RESTORE',file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
