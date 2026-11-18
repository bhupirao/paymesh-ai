"""Prepared V11 -> V14 operator procedure. Never imported for live execution by tests."""
import copy,hashlib,json,os,re,shlex,signal,subprocess,sys,time,zipfile,zlib
from pathlib import Path
from phase673_otp_ops import Ops,Stop,PG,TARGET,protected,hidden
from phase683_deployment import FINANCIAL

CONFIRM='ACTIVATE_PHASE697_SCHEMA_V11_TO_V14_CHAT_OTP_DISABLED'
PRIVATE='NO_PUBLIC_PROXY_OR_TUNNEL'
TABLES=('payment_links','checkout_attempts','ai_conversations','ai_conversation_creations','ai_conversation_requests','ai_conversation_messages')
BASELINE=[6,4,4,2,6,4]
# Explicit review of preserved non-secret argv only. Service credentials on argv are forbidden.
ALLOWED=set('spring.config.location spring.config.additional-location spring.profiles.active spring.profiles.include spring.datasource.url spring.datasource.username spring.flyway.enabled spring.flyway.validate-on-migrate spring.flyway.default-schema spring.flyway.schemas spring.flyway.target spring.jpa.hibernate.ddl-auto spring.jpa.properties.hibernate.default_schema spring.sql.init.mode server.address server.port server.forward-headers-strategy server.ssl.enabled paymesh.sessions.origin paymesh.sessions.local-http paymesh.sessions.remember-seconds paymesh.sessions.short-seconds paymesh.sessions.idle-seconds paymesh.sessions.remember-idle-seconds paymesh.demo.password-recovery.enabled paymesh.demo.password-recovery.operator-confirmation paymesh.demo.checkout-controls.enabled paymesh.demo.checkout-controls.operator-confirmation paymesh.demo.gateway-timeout.enabled paymesh.settlement.scheduling-enabled paymesh.ai.enabled paymesh.ai.base-url paymesh.ai.connect-timeout-ms paymesh.ai.response-timeout-ms paymesh.ai.max-response-bytes paymesh.ai.chat.enabled paymesh.ai.chat.response-timeout-ms paymesh.ai.chat.max-response-bytes paymesh.conversations.cleanup-enabled paymesh.conversations.cleanup-delay-ms paymesh.jwt.issuer paymesh.jwt.audience paymesh.jwt.private-key-file paymesh.jwt.public-key-file'.split())
EXPECTED={'spring.profiles.active':'demo','spring.datasource.url':TARGET,'spring.datasource.username':'paymesh_demo_user','spring.flyway.enabled':'true','spring.jpa.hibernate.ddl-auto':'validate','server.address':'127.0.0.1','server.port':'18080','server.forward-headers-strategy':'none','paymesh.sessions.origin':'http://127.0.0.1:5500','paymesh.sessions.local-http':'true','paymesh.settlement.scheduling-enabled':'false','paymesh.demo.password-recovery.enabled':'false'}

def checksum(path):
    crc=0
    for line in path.read_text(encoding='utf-8-sig').splitlines():crc=zlib.crc32(line.encode('utf-8'),crc)
    return crc if crc<2**31 else crc-2**32

def migrations(repo):
    found={}
    for path in (repo/'backend/src/main/resources/db/migration').glob('V*__*.sql'):
        match=re.fullmatch(r'V(\d+)__.+\.sql',path.name)
        if not match or int(match[1]) in found:raise Stop('Unexpected migration inventory.')
        found[int(match[1])]=path
    if set(found)!=set(range(1,15)):raise Stop('Only reviewed V1 through V14 are supported.')
    return found

def validate_history(raw,repo,last):
    rows=json.loads(raw)
    if not isinstance(rows,list) or [r.get('version') for r in rows]!=[str(n) for n in range(1,last+1)]:raise Stop('Migration history differs; no repair/baseline is authorized.')
    source=migrations(repo)
    for row in rows:
        if row.get('success') is not True or row.get('checksum')!=checksum(source[int(row['version'])]):raise Stop('Migration checksum/success differs from reviewed source.')

def flags_from(argv,private):
    if len(argv)<3 or argv[1]!='-jar':raise Stop('Unsupported Java launch layout.')
    flags={}
    for value in argv[3:]:
        k,sep,v=value.removeprefix('--').partition('=')
        if not value.startswith('--') or not sep or k not in ALLOWED or k in flags:raise Stop('Unreviewed/secret Java argv; do not copy or discard it.')
        flags[k]=v
    if any(flags.get(k)!=v for k,v in EXPECTED.items()):raise Stop('Demo launch identity/gates differ.')
    if flags.get('spring.profiles.include','') or flags.get('server.ssl.enabled','false')!='false':raise Stop('Unreviewed profile/connector.')
    for key in ('paymesh.ai.chat.enabled','paymesh.demo.checkout-controls.enabled'):
        if flags.get(key,'false')!='false':raise Stop('Chat/checkout controls must already be disabled.')
    for key in ('spring.flyway.default-schema','spring.flyway.schemas','spring.jpa.properties.hibernate.default_schema'):
        if flags.get(key,'public')!='public':raise Stop('Only public demo schema is supported.')
        flags[key]='public'
    if flags.get('spring.sql.init.mode','never')!='never':raise Stop('Unexpected SQL initializer.')
    if flags.get('paymesh.ai.base-url','http://127.0.0.1:8000')!='http://127.0.0.1:8000':raise Stop('Unexpected AI service origin.')
    for key in ('spring.config.location','spring.config.additional-location'):
        # Sole classpath exception: the complete reviewed main location, never an additional/mixed entry.
        if key=='spring.config.location' and flags.get(key)=='classpath:/application.properties':continue
        for location in flags.get(key,'').split(','):
            if not location:continue
            if not location.startswith('file:'):raise Stop('Unreviewed configuration location.')
            p=Path(location[5:])
            if not p.is_absolute() or not p.resolve().is_relative_to(private.resolve()):raise Stop('Configuration must remain private.')
            protected(p)
    flags.update({'spring.flyway.target':'14','spring.flyway.validate-on-migrate':'true','spring.sql.init.mode':'never','paymesh.ai.chat.enabled':'false','paymesh.demo.checkout-controls.enabled':'false'})
    return flags

class Deployment(Ops):
    def __init__(self):
        super().__init__('phase697a-v14')
        self.report=self.repo/'frontend/PHASE-6.9.7A-AI-INTEGRATION-READINESS-REPORT.md'
    def launch(self):
        argv=shlex.split(self.command(['/bin/ps','-p',self.services['java']['pid'],'-o','args=']))
        self.flags=flags_from(argv,self.private)
        jar=Path(argv[2]);jar=jar if jar.is_absolute() else self.repo/'backend'/jar
        if jar.resolve()!=self.repo/'backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar':raise Stop('Unexpected Java artifact.')
        with zipfile.ZipFile(jar) as archive:
            if 'BOOT-INF/classes/application.properties' not in archive.namelist():raise Stop('Reviewed classpath application.properties missing from artifact.')
            names=[n for n in archive.namelist() if re.fullmatch(r'BOOT-INF/classes/db/migration/V(\d+)__.+\.sql',n)]
            if len(names)!=14:raise Stop('Duplicate or missing packaged migrations.')
            packaged={int(m[1]):n for n in archive.namelist() if (m:=re.fullmatch(r'BOOT-INF/classes/db/migration/V(\d+)__.+\.sql',n))}
            if set(packaged)!=set(range(1,15)):raise Stop('Packaged migration inventory differs.')
            for version,source in migrations(self.repo).items():
                if archive.read(packaged[version])!=source.read_bytes():raise Stop('Packaged migration differs from source.')
            for name in ('chat/AiChatClient','chat/conversations/ConversationController','chat/conversations/ConversationService','security/accounts/ConversationRetention'):
                if 'BOOT-INF/classes/com/paymesh/backend/'+name+'.class' not in archive.namelist():raise Stop('Reviewed AI implementation missing from artifact.')
        self.jar=jar;self.jar_sha=hashlib.sha256(jar.read_bytes()).hexdigest();self.evidence['artifactSha256']=self.jar_sha
    def history(self,last):
        raw=self.sql("SELECT json_agg(json_build_object('version',version,'checksum',checksum,'success',success) ORDER BY installed_rank) FROM public.flyway_schema_history")
        validate_history(raw,self.repo,last)
    def integrity(self):
        # Content comparison, not merely row counts. Only private digests are retained.
        result={}
        for table in FINANCIAL+('app_users','user_roles','merchants','merchant_memberships','merchant_registrations','merchant_administration'):
            raw=self.sql('SELECT row_to_json(t)::text FROM public.'+table+' t ORDER BY row_to_json(t)::text')
            result[table]=hashlib.sha256(raw.encode()).hexdigest()
        return result
    def frontend_restart(self):
        old=self.services['frontend']
        if self.service(5500,self.repo,'python')!=old:raise Stop('Frontend identity changed before stop.')
        os.kill(int(old['pid']),signal.SIGTERM)
        for _ in range(30):
            try:os.kill(int(old['pid']),0)
            except ProcessLookupError:break
            time.sleep(1)
        else:raise Stop('Frontend did not stop; no forced kill.')
        if self.command(['/usr/sbin/lsof','-t','-nP','-iTCP:5500','-sTCP:LISTEN'],allow_empty=True):raise Stop('Frontend port was claimed externally.')
        with (self.run_dir/'frontend.log').open('xb') as log:
            process=subprocess.Popen([sys.executable,'frontend/dev_server.py'],cwd=self.repo,env=self.env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        for _ in range(30):
            if process.poll() is not None:raise Stop('Frontend startup failed; do not restart blindly.')
            try:
                current=self.service(5500,self.repo,'python')
                if current['pid']!=str(process.pid):raise Stop('Unexpected new frontend PID.')
                self.services['frontend']=current;self.evidence['newFrontendPid']=process.pid;return
            except Stop:time.sleep(1)
        raise Stop('Frontend readiness timeout.')
    def run(self):
        self.stage='preflight'
        for k,v in self.env.items():
            if v and (k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','SPRING_APPLICATION_JSON','SPRING_CONFIG_LOCATION','SPRING_CONFIG_ADDITIONAL_LOCATION','SPRING_CONFIG_IMPORT') or k.startswith(('SPRING_DATASOURCE_','SPRING_FLYWAY_','SPRING_JPA_','SPRING_MAIN_'))):raise Stop('Unreviewed startup override.')
        for name in ('demo.env','secrets.env','jwt-private.pem'):protected(self.private/name)
        for k in ('PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN'):
            if not self.env.get(k):raise Stop('Required existing protected configuration missing.')
        for k,name in (('PAYMESH_JWT_PRIVATE_KEY_FILE','jwt-private.pem'),('PAYMESH_JWT_PUBLIC_KEY_FILE','jwt-public.pem')):
            if self.env.get(k) and self.env[k]!=str(self.private/name):raise Stop('Unexpected JWT key path.')
            self.env[k]=str(self.private/name)
        self.services={}
        for key,port,cwd,kind in [('java',18080,self.repo/'backend','java'),('frontend',5500,self.repo,'python'),('ai',8000,self.repo/'ai-service','python'),('llm',8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm')]:self.services[key]=self.service(port,cwd,kind)
        self.launch();self.evidence['beforeServices']=copy.deepcopy(self.services)
        for name in ('psql','pg_dump','pg_restore'):
            if ' 16.' not in self.command([PG/name,'--version']):raise Stop('PostgreSQL16 tools required.')
        self.db_password=hidden('Existing paymesh_demo_user database password (hidden): ')
        if not self.db_password:raise Stop('Empty credential.')
        if self.sql('SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()')!='paymesh_demo|paymesh_demo_user|127.0.0.1|5432':raise Stop('Database identity differs.')
        if not 160000<=int(self.sql('SHOW server_version_num'))<170000:raise Stop('Reviewed PostgreSQL16 server required.')
        self.history(11)
        if self.http_json('proxy:/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is not False:raise Stop('OTP must already be disabled.')
        if self.sql('SELECT count(*) FROM public.demo_recovery_eligibility WHERE enabled')!='0':raise Stop('Enabled recovery eligibility exists.')
        for table in TABLES:
            if self.sql("SELECT to_regclass('public."+table+"') IS NULL")!='t':raise Stop('New tables already exist; require a new reviewed baseline.')
        self.before=self.counts()
        if self.before!=BASELINE:raise Stop('Entity counts differ from the approved baseline.')
        before=self.integrity();self.evidence.update(beforeCounts=self.before,beforeIntegrity=before)
        self.index_before=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest()
        if input('Attest private deployment. Type '+PRIVATE+': ').strip()!=PRIVATE:raise Stop('Private attestation not supplied.')
        if input('Approve migration and Java/frontend restart, with chat/OTP disabled. Type '+CONFIRM+': ').strip()!=CONFIRM:raise Stop('Activation not confirmed.')
        self.backup()
        if self.integrity()!=before:raise Stop('Account/financial data changed during backup.')
        self.restart(False) # Existing guarded launcher; chat=false is an explicit authoritative argv flag.
        java_after=self.service(18080,self.repo/'backend','java')
        if java_after['pid']!=str(self.evidence.get('newJavaPid')):raise Stop('Unexpected new Java identity.')
        self.history(14)
        if self.counts()!=self.before or self.integrity()!=before:raise Stop('Account/financial content changed.')
        if any(self.sql('SELECT count(*) FROM public.'+table)!='0' for table in TABLES):raise Stop('New tables must initially be empty.')
        expected={'checkout_attempt_insert','checkout_payment_outcome','ai_conversation_scope_immutable'}
        actual=set(self.sql("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O' AND tgrelid IN ('public.checkout_attempts'::regclass,'public.payments'::regclass,'public.ai_conversations'::regclass)").splitlines())
        if not expected.issubset(actual):raise Stop('New required triggers not enabled.')
        self.frontend_restart()
        for path in ('/','/merchant/ai','/admin/ai','/merchant/payment-links','/merchant/payment-links/create','/checkout/'+'a'*43):
            with self.http.open('http://127.0.0.1:5500'+path,timeout=10) as r:
                if r.status!=200:raise Stop('Frontend route failed.')
                r.read(1024)
        if self.http_json('proxy:/api/v1/payments/health')[0]!=200:raise Stop('Payment health failed.')
        if self.http_json('proxy:/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is not False:raise Stop('OTP capability differs.')
        self.unchanged_other_services()
        if self.counts()!=self.before or self.integrity()!=before:raise Stop('Final integrity comparison failed.')
        if self.service(18080,self.repo/'backend','java')!=java_after:raise Stop('Java identity changed during final verification.')
        self.evidence.update(schemaVersion=14,afterCounts=self.before,afterIntegrity=before,newTablesInitiallyEmpty=True,chatEnabled=False,chatStateEvidence='explicit reviewed Java launch flag; no inference issued',otpEnabled=False,result='V14 schema activation verified; AI activation and browser verification pending')
    def closeout(self,success):
        self.evidence.update(stage=self.stage,success=success)
        if hasattr(self,'index_before'):self.evidence['indexUnchanged']=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest()==self.index_before
        self.private_json(self.run_dir/'evidence.json',self.evidence);self.db_password=None
        print(('SCHEMA_VERIFIED_CHAT_OTP_DISABLED' if success else 'STOPPED_NO_AUTOMATIC_RESTORE')+'; protected evidence: '+str(self.run_dir/'evidence.json'))

def main():
    os.umask(0o077);operation=None
    if len(sys.argv)!=1 or not sys.stdin.isatty() or not sys.stdout.isatty():print('Run only the interactive wrapper without arguments.');return 1
    try:operation=Deployment();operation.run();operation.closeout(True);return 0
    except Stop as e:print(str(e),file=sys.stderr)
    except (Exception,KeyboardInterrupt):print('Operation failed/interrupted; inspect protected evidence. No automatic retry/restore.',file=sys.stderr)
    if operation:
        try:operation.closeout(False)
        except Exception:print('Evidence could not be completed.',file=sys.stderr)
    return 1
if __name__=='__main__':sys.exit(main())
