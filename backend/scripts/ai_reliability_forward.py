"""Operator-only forward deployment. New release only; never claims exact rollback.

Inert on import. Separate backup/activation/degraded gates. No inference, login,
financial writes, migrations, destructive restore, force kill or restart retry.
"""
import hashlib,hmac,json,os,signal,stat,subprocess,sys,tempfile,time,urllib.request,zipfile,zlib
from pathlib import Path
from phase673_otp_ops import Stop,protected,NoRedirect
from phase697a_process import MacOS,snapshot,assert_same,Snapshot
from phase697a_diagnostic import credentials,properties
from ai_reliability_python_launch import python_spec

CONFIRM={'backup':'BACKUP_ONLY_PAYMESH_DEMO_NO_RESTORE','activate':'ACTIVATE_FORWARD_ONLY_AI_RELEASE_NO_OLD_ROLLBACK','degrade':'USE_NEW_RELEASE_WITH_CHAT_DISABLED_NO_ROLLBACK'}
FINANCIAL=('payments','refunds','payment_gateway_transactions','idempotency_keys','simulated_gateway_outcomes','webhook_events','reconciliation_jobs','reconciliation_attempts')
TABLES=FINANCIAL+('app_users','roles','security_audit_events','user_roles','merchants','merchant_memberships','merchant_registrations','merchant_administration','auth_sessions','auth_refresh_tokens','demo_recovery_eligibility','password_recovery_challenges','password_reset_authorizations','payment_links','checkout_attempts','ai_conversations','ai_conversation_creations','ai_conversation_requests','ai_conversation_messages')
PG=Path('/Library/PostgreSQL/16/bin')

def digest(path):
    with open(path,'rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
def env_digest(env):return hashlib.sha256(json.dumps(env,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run(args,env=None,data=None):
    r=subprocess.run([str(a) for a in args],env=env,input=data,capture_output=True)
    if r.returncode:raise Stop('A guarded operation failed; no automatic retry. Preserve protected evidence.')
    return r.stdout

def java_spec(saved,jar,enabled):
    if saved.argv[1]!='-jar':raise Stop('Unexpected Java command.')
    flags={}
    for arg in saved.argv[3:]:
        k,sep,v=arg.partition('=')
        if not sep or not k.startswith('--') or k in flags:raise Stop('Unexpected Java flags.')
        flags[k]=v
    if flags.get('--spring.datasource.url')!='jdbc:postgresql://127.0.0.1:5432/paymesh_demo' or flags.get('--spring.datasource.username')!='paymesh_demo_user' or flags.get('--server.address')!='127.0.0.1' or flags.get('--server.port')!='18080':raise Stop('Java demo identity differs.')
    flags.update({'--paymesh.ai.chat.enabled':'true' if enabled else 'false','--spring.flyway.enabled':'false','--spring.sql.init.mode':'never','--spring.jpa.hibernate.ddl-auto':'validate','--paymesh.conversations.cleanup-enabled':'false','--paymesh.demo.password-recovery.enabled':'false','--paymesh.demo.checkout-controls.enabled':'false'})
    return [saved.executable,'-jar',str(jar),*(k+'='+v for k,v in flags.items())]

class Forward:
    def __init__(self,path):
        self.release=Path(path).resolve();self.private=Path.home()/'.config/paymesh-demo'
        if not self.release.is_relative_to(self.private):raise Stop('Release must remain protected.')
        protected(self.private,0o700);protected(self.release,0o500);protected(self.release/'release-manifest.json',0o400)
        self.m=json.loads((self.release/'release-manifest.json').read_text());self.native=MacOS()
        self.e={'success':False,'inferencePerformed':False,'databaseWrites':False,'trueRollbackAvailable':False,'stage':'preflight'};self.folder=None
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def write(self):
        p=self.folder/'evidence.json'
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:json.dump(self.e,f,indent=2)
    def check(self):
        if not self.release.stat().st_flags&stat.UF_IMMUTABLE or not (self.release/'release-manifest.json').stat().st_flags&stat.UF_IMMUTABLE:raise Stop('Release directory is not user-immutable.')
        for name,sha in self.m['filePins'].items():
            p=self.release/name
            if p.is_symlink() or not p.is_file() or not p.stat().st_flags&stat.UF_IMMUTABLE or digest(p)!=sha:raise Stop('Release file pin differs.')
        for name,target in self.m['symlinks'].items():
            p=self.release/name
            if not p.is_symlink() or os.readlink(p)!=target:raise Stop('Release symlink differs.')
        for name,sha in self.m['externalPins'].items():
            if digest(Path(name))!=sha:raise Stop('External runtime changed.')
        for name,entry in self.m.get('publicConfigPins',{}).items():
            p=Path(name);info=p.lstat()
            if p.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=entry['mode'] or info.st_mode&0o022 or digest(p)!=entry['sha256']:raise Stop('Public key identity/permissions changed.')
        for name,sha in self.m['protectedConfigPins'].items():
            if digest(protected(Path(name)))!=sha:raise Stop('Protected configuration changed.')
    def listeners(self,port):
        r=subprocess.run(['/usr/sbin/lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-Fpn'],capture_output=True,text=True)
        if r.returncode not in (0,1):raise Stop('Listener inspection failed.')
        return r.stdout
    def fence(self,name,identity=None):
        identity=identity or self.m['services'][name]['identity'];s=snapshot(identity[0],self.native)
        if list(s.identity)!=identity:raise Stop('Native process identity changed.')
        port=self.m['services'][name]['port'];lines=self.listeners(port).splitlines()
        if [l for l in lines if l.startswith('p')]!=['p'+str(s.identity[0])] or [l for l in lines if l.startswith('n')]!=['n127.0.0.1:'+str(port)]:raise Stop('Service is not the exact loopback listener.')
        cwd=run(['/usr/sbin/lsof','-a','-p',str(s.identity[0]),'-d','cwd','-Fn']).decode().splitlines()
        if identity==self.m['services'][name]['identity']:
            if hashlib.sha256(json.dumps(s.argv).encode()).hexdigest()!=self.m['services'][name]['argvDigest']:raise Stop('Launch command changed.')
            if [x[1:] for x in cwd if x.startswith('n')]!=[self.m['services'][name]['cwd']]:raise Stop('Working directory changed.')
        return s
    def preserved(self):
        for n in ('frontend','llm'):self.fence(n)
        current=run(['/bin/ps','-p','148','-o','pid=,ppid=,uid=,lstart=,comm=']).decode().strip()
        if current!=self.m['postgresOsIdentity']:raise Stop('PostgreSQL OS identity changed.')
    def config(self,java,python):
        sink=Path(python.environment['PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE'])
        credentials(python,java,self.private,sink)
        if env_digest(java.environment)!=self.m['services']['java']['environmentDigest'] or env_digest(python.environment)!=self.m['services']['ai']['environmentDigest']:raise Stop('Launch environment changed.')
    def db(self,sql):
        env={'PATH':'/usr/bin:/bin','PGPASSWORD':self.java.environment['PAYMESH_DB_PASSWORD'],'PGCONNECT_TIMEOUT':'5','PGCLIENTENCODING':'UTF8','PGOPTIONS':'-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000'}
        guard="DO $$BEGIN IF current_database()<>'paymesh_demo' OR current_user<>'paymesh_demo_user' OR inet_server_addr()<>'127.0.0.1'::inet OR inet_server_port()<>5432 OR current_setting('transaction_read_only')<>'on' THEN RAISE EXCEPTION 'identity'; END IF; END$$;"
        return run([PG/'psql','-X','-w','-h','127.0.0.1','-p','5432','-U','paymesh_demo_user','-d','paymesh_demo','-Atq','-v','ON_ERROR_STOP=1'],env=env,data=("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SET LOCAL TIME ZONE 'UTC';SET LOCAL datestyle='ISO,YMD';"+guard+sql+';ROLLBACK;').encode()).decode().strip()
    def integrity(self):
        history=json.loads(self.db("SELECT json_agg(json_build_object('version',version,'checksum',checksum,'success',success) ORDER BY installed_rank) FROM public.flyway_schema_history"))
        if history!=self.m['migrationHistory']:raise Stop('V14 history/checksums differ; migrations are forbidden.')
        return {t:hashlib.sha256(self.db('SELECT row_to_json(t)::text FROM public.'+t+' t ORDER BY row_to_json(t)::text').encode()).hexdigest() for t in TABLES}
    def backup(self):
        import shutil
        required=int(self.db('SELECT pg_database_size(current_database())'))*3+1073741824
        if shutil.disk_usage(self.private).free<required:raise Stop('Insufficient backup reserve.')
        before=self.integrity();archive=self.folder/'paymesh_demo.dump'
        env={'PATH':'/usr/bin:/bin','PGPASSWORD':self.java.environment['PAYMESH_DB_PASSWORD'],'PGCONNECT_TIMEOUT':'5','PGOPTIONS':'-c default_transaction_read_only=on'}
        for tool in ('pg_dump','pg_restore','psql'):
            if b' 16.' not in run([PG/tool,'--version']):raise Stop('PostgreSQL16 tool required.')
        run([PG/'pg_dump','-w','-h','127.0.0.1','-p','5432','-U','paymesh_demo_user','-d','paymesh_demo','-Fc','-f',archive],env=env)
        os.chmod(archive,0o600);run([PG/'pg_restore','--list',archive]);run([PG/'pg_restore','--file=/dev/null',archive])
        if before!=self.integrity():raise Stop('Database changed during backup; stop for review.')
        self.e.update(backup={'path':str(archive),'sha256':digest(archive),'readable':True,'testRestorePerformed':False},integrity=before)
    def stop(self,s,port):
        if getattr(self,'allow_absent',False):
            alive=subprocess.run(['/bin/ps','-p',str(s.identity[0]),'-o','stat='],capture_output=True,text=True).stdout.strip()
            if not alive or alive.startswith('Z'):
                if self.listeners(port):raise Stop('Unexpected occupied port during degraded recovery.')
                return
        assert_same(s,self.native);os.kill(s.identity[0],signal.SIGTERM)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            status=subprocess.run(['/bin/ps','-p',str(s.identity[0]),'-o','stat='],capture_output=True,text=True).stdout.strip()
            if not status or status.startswith('Z'):
                if self.listeners(port):raise Stop('Listener still occupied.')
                return
            assert_same(s,self.native);time.sleep(.25)
        raise Stop('Graceful stop timed out; no force kill or retry.')
    def start(self,name,args,cwd,env):
        port=self.m['services'][name]['port']
        if self.listeners(port):raise Stop('Port occupied; replacement not started.')
        with os.fdopen(os.open(self.folder/(name+'.log'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as log:
            child=subprocess.Popen(args,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        self.e[name+'Pid']=child.pid;self.write()
        identity=snapshot(child.pid,self.native);self.e[name+'Identity']=list(identity.identity);self.write()
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if child.poll() is not None:raise Stop('New process exited; no automatic recovery.')
            if self.listeners(port):
                s=snapshot(child.pid,self.native);self.e[name+'Identity']=list(s.identity);self.write()
                self.fence(name,list(s.identity))
                if s.environment!=env or s.argv[1:]!=tuple(args[1:]):raise Stop('Replacement launch state differs.')
                return s
            time.sleep(.25)
        raise Stop('Startup timeout; no automatic retry or recovery.')
    def health(self,path,port):
        try:
            with self.http.open('http://127.0.0.1:'+str(port)+path,timeout=10) as r:
                raw=r.read(1048577)
                if r.status!=200 or len(raw)>1048576:raise Stop('Metadata check failed.')
                return json.loads(raw)
        except Exception:raise Stop('Metadata check failed; no automatic retry.') from None
    def deploy(self,enabled,prior):
        archive=Path(prior['backup']['path'])
        if (enabled and not prior.get('success')) or not prior['backup'].get('readable') or digest(protected(archive))!=prior['backup']['sha256']:raise Stop('Verified protected backup required.')
        if prior.get('releaseManifestSha256')!=digest(self.release/'release-manifest.json'):raise Stop('Backup belongs to another release.')
        if prior['integrity']!=self.integrity():raise Stop('Database differs from backup; stop before restart.')
        self.e.update(backup=prior['backup'],integrity=prior['integrity'])
        # Stop Java first: there is never an old Java client against new Python during rollout.
        self.e['stage']='java-stop';self.write();self.stop(self.java,18080);self.e['javaStopped']=True;self.write()
        self.e['stage']='python-stop';self.write();self.stop(self.python,8000);self.e['pythonStopped']=True;self.write()
        self.preserved();self.check()
        sink=self.folder/'chat-validation-diagnostics.jsonl';fd=os.open(sink,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        args,cwd,env=python_spec(self.release,self.python,sink,enabled)
        self.e['stage']='python-start';self.write();new_python=self.start('ai',args,cwd,env)
        if self.health('/health',8000).get('status')!='UP' or 'post' not in self.health('/openapi.json',8000).get('paths',{}).get('/api/v1/chat',{}):raise Stop('Python health or route registration failed.')
        self.e['stage']='java-start';self.write();args=java_spec(self.java,self.release/'java/paymesh.jar',enabled)
        new_java=self.start('java',args,Path(self.m['services']['java']['cwd']),dict(self.java.environment))
        if self.health('/actuator/health/readiness',18080).get('status')!='UP':raise Stop('Java readiness failed.')
        if self.health('/api/v1/payments/health',18080).get('status')!='RUNNING':raise Stop('Payment health failed.')
        if self.health('/api/v1/auth/password/capabilities',18080).get('localDemoEnabled') is not False:raise Stop('OTP capability unexpectedly enabled.')
        if prior['integrity']!=self.integrity():raise Stop('Database content changed; do not restore automatically.')
        if enabled:credentials(new_python,new_java,self.private,sink)
        else:
            if new_python.environment.get('PAYMESH_AI_CHAT_API_ENABLED')!='false' or '--paymesh.ai.chat.enabled=false' not in new_java.argv:raise Stop('Degraded chat gates differ.')
            if not hmac.compare_digest(new_python.environment.get('PAYMESH_AI_CHAT_SERVICE_TOKEN',''),self.python.environment.get('PAYMESH_AI_CHAT_SERVICE_TOKEN','')):raise Stop('Service credential changed.')
        self.preserved();assert_same(new_python,self.native);assert_same(new_java,self.native)
        self.e.update(chatEnabled=enabled,privateAuthenticationConfigurationPreserved=True,diagnosticFile=str(sink),stage='verified')
    def execute(self,mode,evidence=None):
        self.check();self.preserved()
        prior=json.loads(protected(Path(evidence)).read_text()) if evidence else None
        self.allow_absent=mode=='degrade'
        if mode=='degrade':
            if prior.get('mode')!='activate' or prior.get('releaseManifestSha256')!=digest(self.release/'release-manifest.json'):raise Stop('Degraded recovery requires this release activation evidence.')
            state_path=protected(Path(prior['launchStateFile']))
            if not state_path.resolve().is_relative_to(self.private) or digest(state_path)!=prior['launchStateSha256']:raise Stop('Protected recovery launch state differs.')
            state=json.loads(state_path.read_text())
            values={}
            for name,stopped_key in [('java','javaStopped'),('ai','pythonStopped')]:
                raw=state[name];identity=prior.get(name+'Identity')
                if identity:
                    alive=subprocess.run(['/bin/ps','-p',str(identity[0]),'-o','stat='],capture_output=True,text=True).stdout.strip()
                    if not alive or alive.startswith('Z'):
                        if self.listeners(self.m['services'][name]['port']):raise Stop('Unexpected replacement listener.')
                        values[name]=Snapshot(tuple(identity),raw['executable'],tuple(raw['argv']),raw['environment'])
                    else:values[name]=self.fence(name,identity)
                elif prior.get(name+'Pid'):
                    raise Stop('Replacement native identity was not captured; explicit recovery review required.')
                elif prior.get(stopped_key) and not self.listeners(self.m['services'][name]['port']):values[name]=Snapshot(tuple(raw['identity']),raw['executable'],tuple(raw['argv']),raw['environment'])
                else:values[name]=self.fence(name)
            self.java=values['java'];self.python=values['ai']
        else:
            self.java=self.fence('java');self.python=self.fence('ai');self.config(self.java,self.python)
        if not sys.stdin.isatty() or not sys.stdout.isatty():raise Stop('Interactive operator terminal required.')
        if input('Type NO_PUBLIC_PROXY_OR_TUNNEL: ').strip()!='NO_PUBLIC_PROXY_OR_TUNNEL':raise Stop('Private deployment attestation missing.')
        if input('Type '+CONFIRM[mode]+': ').strip()!=CONFIRM[mode]:raise Stop('Operation not approved.')
        self.folder=Path(tempfile.mkdtemp(prefix='ai-forward-'+mode+'-',dir=self.private));os.chmod(self.folder,0o700)
        self.e.update(releaseManifestSha256=digest(self.release/'release-manifest.json'),mode=mode);self.write()
        try:
            if mode!='backup':
                state_path=self.folder/'protected-launch-state.json'
                state={name:{'identity':s.identity,'executable':s.executable,'argv':s.argv,'environment':s.environment} for name,s in [('java',self.java),('ai',self.python)]}
                with os.fdopen(os.open(state_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w') as stream:json.dump(state,stream)
                self.e.update(launchStateFile=str(state_path),launchStateSha256=digest(state_path));self.write()
            if mode=='backup':self.backup()
            else:self.deploy(mode=='activate',prior)
            self.e['success']=True;self.write();print('BACKUP_VERIFIED_NO_RESTORE' if mode=='backup' else 'FORWARD_SERVICES_READY_INFERENCE_NOT_TESTED' if mode=='activate' else 'NEW_RELEASE_CHAT_DISABLED_NOT_A_ROLLBACK')
        finally:
            self.write();print('Protected evidence: '+str(self.folder/'evidence.json'))

def main():
    try:
        if len(sys.argv) not in (3,4) or sys.argv[1] not in CONFIRM:raise Stop('Expected backup|activate|degrade and protected release directory; activation requires evidence.')
        mode=sys.argv[1]
        if (mode=='backup')!=(len(sys.argv)==3):raise Stop('Provide exactly the required evidence argument.')
        Forward(sys.argv[2]).execute(mode,sys.argv[3] if len(sys.argv)==4 else None);return 0
    except (Exception,KeyboardInterrupt):print('STOPPED_NO_AUTOMATIC_RETRY_OR_RESTORE',file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
