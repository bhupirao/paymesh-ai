"""Operator-only combined Phase682/683 deployment on existing V11. Never executed during preparation."""
import copy,hashlib,json,os,shlex,signal,subprocess,sys,time,zipfile,re
from pathlib import Path
from phase673_otp_ops import Ops,Stop,PG,TARGET,protected,hidden

FINANCIAL=('payments','refunds','payment_gateway_transactions','idempotency_keys','simulated_gateway_outcomes','webhook_events','reconciliation_jobs','reconciliation_attempts')
class Deployment(Ops):
    def __init__(self):
        super().__init__('activate-phase682-683')
        self.report=self.repo/'frontend/PHASE-6.8.3-CUSTOMER-CHECKOUT-REPORT.md'
    def launch(self):
        # Capture privately, validate before persisting/using. Never print ps argv or read process environments.
        argv = shlex.split(self.command(['/bin/ps', '-p', self.services['java']['pid'], '-o', 'args=']))
        if len(argv) < 3 or argv[1] != '-jar':
            raise Stop('Unsupported Java launch layout; review privately.')
        jar = Path(argv[2]); jar = jar if jar.is_absolute() else self.repo / 'backend' / jar
        if jar.resolve() != self.repo / 'backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar':
            raise Stop('Unexpected Java artifact.')
        allowed = {'spring.config.location', 'spring.config.additional-location', 'spring.profiles.active', 'spring.profiles.include', 'spring.datasource.url', 'spring.datasource.username', 'spring.flyway.enabled', 'spring.flyway.validate-on-migrate', 'spring.flyway.default-schema', 'spring.flyway.schemas', 'spring.jpa.hibernate.ddl-auto', 'spring.jpa.properties.hibernate.default_schema', 'spring.sql.init.mode', 'server.address', 'server.port', 'server.forward-headers-strategy', 'server.ssl.enabled', 'paymesh.sessions.origin', 'paymesh.sessions.local-http', 'paymesh.sessions.remember-seconds', 'paymesh.sessions.short-seconds', 'paymesh.sessions.idle-seconds', 'paymesh.sessions.remember-idle-seconds', 'paymesh.demo.password-recovery.enabled', 'paymesh.demo.password-recovery.operator-confirmation', 'paymesh.demo.checkout-controls.enabled','paymesh.demo.checkout-controls.operator-confirmation','paymesh.demo.gateway-timeout.enabled', 'paymesh.settlement.scheduling-enabled', 'paymesh.ai.enabled', 'paymesh.ai.base-url', 'paymesh.ai.connect-timeout-ms', 'paymesh.ai.response-timeout-ms', 'paymesh.ai.max-response-bytes', 'paymesh.jwt.issuer', 'paymesh.jwt.audience', 'paymesh.jwt.private-key-file', 'paymesh.jwt.public-key-file'}
        flags = {}
        for item in argv[3:]:
            key, separator, value = item.removeprefix('--').partition('=')
            if not item.startswith('--') or not separator or key not in allowed or key in flags:
                raise Stop('Unreviewed Java launch flag; do not discard it or copy possible secrets.')
            flags[key] = value
        expected = {'spring.flyway.enabled':'true','spring.jpa.hibernate.ddl-auto':'validate','spring.profiles.active': 'demo', 'spring.datasource.url': TARGET, 'spring.datasource.username': 'paymesh_demo_user', 'server.address': '127.0.0.1', 'server.port': '18080', 'server.forward-headers-strategy': 'none', 'paymesh.sessions.origin': 'http://127.0.0.1:5500', 'paymesh.sessions.local-http': 'true', 'paymesh.settlement.scheduling-enabled': 'false'}
        if any(flags.get(k) != v for k, v in expected.items()) or flags.get('spring.profiles.include', '') or flags.get('server.ssl.enabled', 'false') != 'false':
            raise Stop('Current launch does not satisfy the unchanged local demo gate.')
        for location in flags.get('spring.config.additional-location', '').split(','):
            if not location:
                continue
            if not location.startswith('file:'):
                raise Stop('Unsupported additional configuration location.')
            path = Path(location[5:])
            if not path.resolve().is_relative_to(self.private):
                raise Stop('Additional configuration must remain private.')
            protected(path)
        with zipfile.ZipFile(jar) as archive:
            versions = {int(re.match(r'BOOT-INF/classes/db/migration/V(\d+)__', x)[1]) for x in archive.namelist() if re.match(r'BOOT-INF/classes/db/migration/V(\d+)__', x)}
            if versions != set(range(1, 14)):
                raise Stop('Artifact contains an unexpected migration set; only reviewed V12/V13 are authorized here.')
            if 'BOOT-INF/classes/com/paymesh/backend/security/accounts/DashboardAnalytics.class' not in archive.namelist():
                raise Stop('Package the reviewed Merchant portal before deployment.')
            migration = 'V11__merchant_administration.sql'
            if archive.read('BOOT-INF/classes/db/migration/' + migration) != (self.repo / 'backend/src/main/resources/db/migration' / migration).read_bytes():
                raise Stop('Packaged V11 differs from reviewed source.')
        with zipfile.ZipFile(jar) as archive:
            for version in (12,13):
                source=next((self.repo/'backend/src/main/resources/db/migration').glob('V'+str(version)+'__*.sql'))
                if archive.read('BOOT-INF/classes/db/migration/'+source.name)!=source.read_bytes():raise Stop('Packaged checkout migration differs from reviewed source.')
            if 'BOOT-INF/classes/com/paymesh/backend/security/auth/CheckoutController.class' not in archive.namelist():raise Stop('Checkout implementation missing.')
        for key in ('spring.flyway.default-schema','spring.flyway.schemas','spring.jpa.properties.hibernate.default_schema'):
            if flags.get(key,'public')!='public':raise Stop('Only the reviewed public demo schema is allowed.')
            flags[key]='public'
        if flags.get('spring.sql.init.mode','never')!='never':raise Stop('Unrelated SQL initialization is not authorized.')
        flags['spring.sql.init.mode']='never'
        flags['spring.flyway.validate-on-migrate']='true'
        self.jar, self.flags = jar, flags
        self.jar_sha = hashlib.sha256(jar.read_bytes()).hexdigest()
        self.evidence['artifactSha256'] = self.jar_sha


    def integrity(self):
        result={}
        for table in FINANCIAL+('app_users','merchant_administration','merchants','merchant_memberships','merchant_registrations','user_roles'):
            raw=self.sql('SELECT row_to_json(t)::text FROM public.'+table+' t ORDER BY row_to_json(t)::text')
            result[table]=hashlib.sha256(raw.encode()).hexdigest()
        raw=self.sql('SELECT user_id,login_normalized,enabled,account_status,authorization_version,created_at,updated_at FROM public.app_users ORDER BY user_id')
        result['accountMetadata']=hashlib.sha256(raw.encode()).hexdigest()
        return result
    def run(self):
        self.stage='preflight'
        for key in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','SPRING_APPLICATION_JSON','SPRING_CONFIG_LOCATION','SPRING_CONFIG_ADDITIONAL_LOCATION','SPRING_CONFIG_IMPORT'):
            if self.env.get(key):raise Stop('Unreviewed startup override.')
        if any(self.env.get(k) for k in self.env if k.startswith(('SPRING_DATASOURCE_','SPRING_FLYWAY_','SPRING_JPA_','SPRING_MAIN_'))):raise Stop('Unreviewed database override.')
        for name in ('demo.env','secrets.env','jwt-private.pem'):protected(self.private/name)
        for key,name in (('PAYMESH_JWT_PRIVATE_KEY_FILE','jwt-private.pem'),('PAYMESH_JWT_PUBLIC_KEY_FILE','jwt-public.pem')):
            if self.env.get(key) and self.env[key]!=str(self.private/name):raise Stop('Unexpected existing JWT key path.')
            self.env[key]=str(self.private/name)
        for key in ('PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN'):
            if not self.env.get(key):raise Stop('Required protected configuration missing.')
        self.services={}
        for key,port,cwd,kind in [('java',18080,self.repo/'backend','java'),('frontend',5500,self.repo,'python'),('ai',8000,self.repo/'ai-service','python'),('llm',8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm')]:self.services[key]=self.service(port,cwd,kind)
        self.launch();self.evidence['beforeServices']=copy.deepcopy(self.services)
        self.index_before=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest();self.staged_before=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])
        for name in ('psql','pg_dump','pg_restore'):
            if ' 16.' not in self.command([PG/name,'--version']):raise Stop('PostgreSQL16 tools required.')
        self.db_password=hidden('Existing paymesh_demo_user database password (hidden): ')
        if not self.db_password:raise Stop('Empty database credential.')
        if self.sql('SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()')!='paymesh_demo|paymesh_demo_user|127.0.0.1|5432':raise Stop('Actual demo database identity mismatch.')
        history=self.sql("SELECT string_agg(version,',' ORDER BY installed_rank) FILTER(WHERE version IS NOT NULL)||'|'||bool_and(success)::text FROM public.flyway_schema_history")
        if history!='1,2,3,4,5,6,7,8,9,10,11|true':raise Stop('Require successful V1–V11 only; no migrations or repair authorized.')
        if self.http_json('proxy:/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is not False:raise Stop('OTP must already be disabled.')
        if self.flags.get('paymesh.demo.password-recovery.enabled')!='false':raise Stop('OTP launch flag must be false.')
        if self.sql('SELECT count(*) FROM public.demo_recovery_eligibility WHERE enabled')!='0':raise Stop('Unexpected recovery eligibility.')
        if self.sql("SELECT to_regclass('public.payment_links') IS NULL AND to_regclass('public.checkout_attempts') IS NULL")!='t':raise Stop('Checkout tables already exist; require a fresh reviewed V11 activation baseline.')
        self.before=self.counts();self.evidence['beforeCounts']=self.before
        if self.before!=[6,4,4,2,6,4]:raise Stop('Counts differ from approved baseline.')
        before=self.integrity();self.evidence['beforeIntegrity']=before
        if input('Approve private combined Phase682/683 deployment (V11 to V12/V13) with OTP disabled. Type ACTIVATE_PHASE682_683_V12_V13_OTP_DISABLED: ').strip()!='ACTIVATE_PHASE682_683_V12_V13_OTP_DISABLED':raise Stop('Activation not confirmed.')
        choice=input('Outcome controls remain disabled unless you type ENABLE_PRIVATE_CHECKOUT_CONTROLS (blank keeps disabled): ').strip()
        if choice not in ('','ENABLE_PRIVATE_CHECKOUT_CONTROLS'):raise Stop('Unknown controls choice.')
        self.flags['paymesh.demo.checkout-controls.enabled']=str(bool(choice)).lower()
        if choice:
            if input('Attest private loopback deployment; type NO_PUBLIC_PROXY_OR_TUNNEL: ').strip()!='NO_PUBLIC_PROXY_OR_TUNNEL':raise Stop('Private deployment not attested.')
            self.flags['paymesh.demo.checkout-controls.operator-confirmation']='NO_PUBLIC_PROXY_OR_TUNNEL'
        self.evidence['checkoutDemoControls']=bool(choice)
        self.backup()
        if self.integrity()!=before:raise Stop('Database changed during backup.')
        self.restart(False) # Only verified Java; normal Flyway applies only V12/V13.
        if self.sql("SELECT count(*) FROM public.flyway_schema_history WHERE version='11' AND success")!='1':raise Stop('V11 success not verified. Do not repair or downgrade.')
        if self.counts()!=self.before or self.integrity()!=before:raise Stop('Account/financial integrity changed; inspect private evidence.')
        history_after=self.sql("SELECT string_agg(version,',' ORDER BY installed_rank) FILTER(WHERE version IS NOT NULL)||'|'||bool_and(success)::text FROM public.flyway_schema_history")
        if history_after!='1,2,3,4,5,6,7,8,9,10,11,12,13|true':raise Stop('V12/V13 migration not verified; stop without repair/restore/downgrade.')
        if self.sql("SELECT (SELECT count(*) FROM public.payment_links),(SELECT count(*) FROM public.checkout_attempts)")!='0|0':raise Stop('Checkout tables must initially be empty.')
        java_after=self.service(18080,self.repo/'backend','java')
        self.stage='frontend-restart'
        old=self.services['frontend']
        if self.service(5500,self.repo,'python')!=old:raise Stop('Frontend identity changed.')
        os.kill(int(old['pid']),signal.SIGTERM)
        for _ in range(30):
            try:os.kill(int(old['pid']),0)
            except ProcessLookupError:break
            time.sleep(1)
        else:raise Stop('Frontend did not stop; no force-kill or duplicate listener.')
        if self.command(['/usr/sbin/lsof','-t','-nP','-iTCP:5500','-sTCP:LISTEN'],allow_empty=True):raise Stop('Frontend port was claimed externally.')
        with (self.run_dir/'frontend.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,'frontend/dev_server.py'],cwd=self.repo,env=self.env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        self.evidence['newFrontendPid']=child.pid
        for _ in range(30):
            if child.poll() is not None:raise Stop('Frontend startup failed; no automatic retry.')
            try:
                self.services['frontend']=self.service(5500,self.repo,'python');break
            except Stop:time.sleep(1)
        else:raise Stop('Frontend readiness timeout.')
        if self.services['frontend']['pid']!=str(child.pid):raise Stop('Unexpected new frontend identity.')
        if self.http_json('proxy:/api/v1/payments/health')[0]!=200:raise Stop('Proxy health failed.')
        if self.http_json('proxy:/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is not False:raise Stop('OTP disabled verification failed.')
        import urllib.request
        for path in ('/','/admin/login','/admin/dashboard','/admin/merchants','/admin/merchant','/admin/pending','/admin/payments','/admin/refunds','/admin/audit','/admin/accounts','/admin/profile','/merchant/dashboard','/merchant/payments','/merchant/refunds','/merchant/profile','/merchant/security','/admin/forgot-password','/merchant/payment-links','/merchant/payment-links/create','/checkout/'+'a'*43):
            with self.http.open(urllib.request.Request('http://127.0.0.1:5500'+path),timeout=10) as response:
                if response.status!=200:raise Stop('Frontend route failed.')
                response.read(1024)
        self.unchanged_other_services()
        if self.counts()!=self.before or self.integrity()!=before:raise Stop('Final database integrity verification failed.')
        if self.service(18080,self.repo/'backend','java')!=java_after:raise Stop('Java identity changed during frontend activation.')
        if self.sql("SELECT count(*) FROM public.merchant_administration")!='4':raise Stop('Merchant lifecycle backfill count mismatch.')
        if self.sql("SELECT count(*) FROM public.merchant_administration a JOIN public.merchants m ON m.merchant_id=a.merchant_id WHERE a.status<>CASE WHEN m.verified AND m.active THEN 'ACTIVE' WHEN m.verified THEN 'SUSPENDED' ELSE 'PENDING_APPROVAL' END")!='0':raise Stop('Merchant backfill state mismatch; no approval or repair is authorized.')
        self.evidence.update(schemaVersion=13,newTablesInitiallyEmpty=True,afterCounts=self.counts(),afterIntegrity=before,result='Combined Phase682/683 activated; V12/V13 applied; OTP disabled; no checkout execution or financial mutation issued.')


def main():
    os.umask(0o077)
    if len(sys.argv)!=1 or not sys.stdin.isatty() or not sys.stdout.isatty():print('Run only the interactive activation wrapper without arguments.');return 1
    operation=None
    try:operation=Deployment();operation.run();operation.closeout(True);return 0
    except Stop as ex:print(str(ex),file=sys.stderr)
    except (Exception,KeyboardInterrupt):print('Activation failed/interrupted. Inspect protected evidence; no automatic rollback/retry.',file=sys.stderr)
    if operation:
        try:operation.closeout(False)
        except Exception:print('Private evidence could not be completed.',file=sys.stderr)
    return 1
if __name__=='__main__':sys.exit(main())
