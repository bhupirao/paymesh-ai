"""Operator-only, standard-library orchestration; not application code or an admin provisioning bypass.

Additional ADMIN creation uses only the authenticated administration REST adapter.
Deploy its reviewed artifact with recovery disabled before activation. Never bypass bootstrap guards.
"""
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
import uuid
import warnings
import zipfile

MERCHANT = 'otp-merchant-demo@example.test'
ADMIN = 'otp-admin-demo'
REVIEWER = 'demo-admin'
TARGET = 'jdbc:postgresql://127.0.0.1:5432/paymesh_demo'
PG = Path('/Library/PostgreSQL/16/bin')
BASELINE = [4, 3, 3, 1, 6, 4]

class Stop(Exception):
    """Fixed safe operator message only; never construct from exception/body/credential text."""


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def identifier(value):
    return str(uuid.UUID(str(value)))


def protected(path, mode=0o600):
    p = Path(path)
    info = p.lstat()
    if p.is_symlink() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode:
        raise Stop('Protected configuration ownership/mode check failed.')
    return p


def hidden(prompt):
    # Never fall back to echoed input if terminal echo control fails.
    with open('/dev/tty', 'w') as tty, warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        return getpass.getpass(prompt, stream=tty)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Ops:
    def __init__(self, mode):
        self.mode = mode
        self.stage = 'preflight'
        self.repo = Path(__file__).resolve().parents[2]
        if self.repo != Path.home() / 'Developer/paymesh-ai':
            raise Stop('Unexpected project checkout.')
        self.private = protected(Path.home() / '.config/paymesh-demo', 0o700)
        self.run_dir = Path(tempfile.mkdtemp(prefix='otp-step17-' + mode + '-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-', dir=self.private))
        os.chmod(self.run_dir, 0o700)
        self.report = self.repo / 'frontend/PHASE-6.7.3-SESSIONS-PASSWORD-RECOVERY-REPORT.md'
        self.evidence = {'mode': mode, 'startedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'recoveryRequestsSent': False}
        self.db_password = None
        self.env = dict(os.environ)
        self.env.pop('PGPASSWORD', None)
        self.env.pop('PAYMESH_DB_PASSWORD', None)
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.manifest = self.private / 'otp-step17-disposable-accounts.json'

    def command(self, args, *, data=None, env=None, allow_empty=False):
        result = subprocess.run([str(a) for a in args], input=data, capture_output=True, env=self.env if env is None else env)
        if result.returncode and not (allow_empty and result.returncode == 1 and not result.stdout):
            # Errors may contain operational detail: retain privately, never echo them.
            with (self.run_dir / 'errors.log').open('ab') as out:
                out.write(result.stderr)
            raise Stop('An operation failed at stage ' + self.stage + '; inspect private evidence before retrying.')
        return result.stdout.decode('utf-8').strip()

    def private_json(self, path, data, replace=False):
        text = json.dumps(data, indent=2) + '\n'
        if not replace:
            with Path(path).open('x', encoding='utf-8') as out:
                os.chmod(path, 0o600)
                out.write(text)
        else:
            if Path(path).exists():
                protected(path)
            fd, temporary = tempfile.mkstemp(prefix='.step17-state-', dir=self.private)
            with os.fdopen(fd, 'w') as out:
                out.write(text)
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)

    def sql(self, sql, write=False):
        env = dict(self.env, PGPASSWORD=self.db_password)
        env['PGOPTIONS'] = '-c default_transaction_read_only=' + ('off' if write else 'on')
        return self.command([PG / 'psql', '-X', '-w', '-h', '127.0.0.1', '-p', '5432', '-U', 'paymesh_demo_user', '-d', 'paymesh_demo', '-Atq', '-v', 'ON_ERROR_STOP=1'], data=sql.encode(), env=env)

    def counts(self):
        tables = ['app_users', 'merchants', 'merchant_memberships', 'merchant_registrations', 'payments', 'refunds']
        return [int(x) for x in self.sql('SELECT ' + ','.join('(SELECT count(*) FROM public.' + t + ')' for t in tables)).split('|')]

    def service(self, port, cwd, kind):
        pids = set(self.command(['/usr/sbin/lsof', '-t', '-nP', '-iTCP:' + str(port), '-sTCP:LISTEN']).split())
        if len(pids) != 1 or not next(iter(pids)).isdigit():
            raise Stop('Expected one service listener.')
        pid = next(iter(pids))
        command = self.command(['/bin/ps', '-p', pid, '-o', 'comm='])
        name = Path(command).name
        if (kind == 'java' and name != 'java') or (kind == 'python' and not (name == 'Python' or name.startswith('python3'))) or (kind == 'llm' and name != 'llama-server'):
            raise Stop('Service executable mismatch.')
        if 'n' + str(cwd) not in self.command(['/usr/sbin/lsof', '-a', '-p', pid, '-d', 'cwd', '-Fn']).splitlines():
            raise Stop('Service working directory mismatch.')
        names = [x for x in self.command(['/usr/sbin/lsof', '-nP', '-a', '-p', pid, '-iTCP', '-sTCP:LISTEN', '-Fn']).splitlines() if x.startswith('n')]
        if names != ['n127.0.0.1:' + str(port)]:
            raise Stop('Unexpected public/additional listener.')
        return {'pid': pid, 'start': self.command(['/bin/ps', '-p', pid, '-o', 'lstart='])}

    def unchanged_other_services(self):
        for key, port, cwd, kind in [('frontend', 5500, self.repo, 'python'), ('ai', 8000, self.repo / 'ai-service', 'python'), ('llm', 8082, Path.home() / 'Developer/paymesh-tools/llama.cpp', 'llm')]:
            if self.service(port, cwd, kind) != self.services[key]:
                raise Stop('A preserved service changed externally; no further operation is authorized.')

    def launch(self):
        # Capture privately, validate before persisting/using. Never print ps argv or read process environments.
        argv = shlex.split(self.command(['/bin/ps', '-p', self.services['java']['pid'], '-o', 'args=']))
        if len(argv) < 3 or argv[1] != '-jar':
            raise Stop('Unsupported Java launch layout; review privately.')
        jar = Path(argv[2]); jar = jar if jar.is_absolute() else self.repo / 'backend' / jar
        if jar.resolve() != self.repo / 'backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar':
            raise Stop('Unexpected Java artifact.')
        allowed = {'spring.config.location', 'spring.config.additional-location', 'spring.profiles.active', 'spring.profiles.include', 'spring.datasource.url', 'spring.datasource.username', 'spring.flyway.enabled', 'spring.flyway.validate-on-migrate', 'spring.flyway.default-schema', 'spring.flyway.schemas', 'spring.jpa.hibernate.ddl-auto', 'spring.jpa.properties.hibernate.default_schema', 'spring.sql.init.mode', 'server.address', 'server.port', 'server.forward-headers-strategy', 'server.ssl.enabled', 'paymesh.sessions.origin', 'paymesh.sessions.local-http', 'paymesh.sessions.remember-seconds', 'paymesh.sessions.short-seconds', 'paymesh.sessions.idle-seconds', 'paymesh.sessions.remember-idle-seconds', 'paymesh.demo.password-recovery.enabled', 'paymesh.demo.password-recovery.operator-confirmation', 'paymesh.demo.gateway-timeout.enabled', 'paymesh.settlement.scheduling-enabled', 'paymesh.ai.enabled', 'paymesh.ai.base-url', 'paymesh.ai.connect-timeout-ms', 'paymesh.ai.response-timeout-ms', 'paymesh.ai.max-response-bytes', 'paymesh.jwt.issuer', 'paymesh.jwt.audience', 'paymesh.jwt.private-key-file', 'paymesh.jwt.public-key-file'}
        flags = {}
        for item in argv[3:]:
            key, separator, value = item.removeprefix('--').partition('=')
            if not item.startswith('--') or not separator or key not in allowed or key in flags:
                raise Stop('Unreviewed Java launch flag; do not discard it or copy possible secrets.')
            flags[key] = value
        expected = {'spring.profiles.active': 'demo', 'spring.datasource.url': TARGET, 'spring.datasource.username': 'paymesh_demo_user', 'server.address': '127.0.0.1', 'server.port': '18080', 'server.forward-headers-strategy': 'none', 'paymesh.sessions.origin': 'http://127.0.0.1:5500', 'paymesh.sessions.local-http': 'true', 'paymesh.settlement.scheduling-enabled': 'false'}
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
            if versions != set(range(1, 11)):
                raise Stop('Artifact contains an unexpected migration set; no migration is authorized here.')
            if 'BOOT-INF/classes/com/paymesh/backend/security/auth/AdminAccountController.class' not in archive.namelist():
                raise Stop('Package the additional-Admin API before deployment/activation.')
            migration = 'V10__persistent_sessions_and_local_demo_recovery.sql'
            if archive.read('BOOT-INF/classes/db/migration/' + migration) != (self.repo / 'backend/src/main/resources/db/migration' / migration).read_bytes():
                raise Stop('Packaged V10 differs from reviewed source.')
        self.jar, self.flags = jar, flags
        self.jar_sha = hashlib.sha256(jar.read_bytes()).hexdigest()
        self.evidence['artifactSha256'] = self.jar_sha

    def http_json(self, path, body=None, bearer=None):
        headers = {'Accept': 'application/json'}
        if bearer is not None:
            headers['Authorization'] = 'Bearer ' + bearer
        data = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body).encode()
        request = urllib.request.Request('http://127.0.0.1:' + ('5500' if path.startswith('proxy:') else '18080') + path.removeprefix('proxy:'), data=data, headers=headers)
        try:
            with self.http.open(request, timeout=20) as response:
                return response.status, json.loads(response.read(524288))
        except urllib.error.HTTPError as failure:
            # Never expose or persist raw error bodies (including framework diagnostics).
            failure.close()
            return failure.code, {}
        except Exception:
            raise Stop('HTTP operation failed or outcome is unconfirmed; inspect authorized account state before any retry.') from None

    def preflight(self):
        for name in ('JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS', 'SPRING_APPLICATION_JSON', 'SPRING_CONFIG_LOCATION', 'SPRING_CONFIG_ADDITIONAL_LOCATION', 'SPRING_CONFIG_IMPORT'):
            if self.env.get(name):
                raise Stop('Unreviewed JVM/Spring override.')
        for name in self.env:
            if name.startswith(('SPRING_DATASOURCE_', 'SPRING_FLYWAY_', 'SPRING_JPA_', 'SPRING_MAIN_')) and self.env[name]:
                raise Stop('Unreviewed datasource/startup override.')
        for filename in ('demo.env', 'secrets.env', 'jwt-private.pem'):
            protected(self.private / filename)
        for name in ('PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN'):
            if not self.env.get(name):
                raise Stop('Required existing protected demo configuration is missing.')
        for name, filename in [('PAYMESH_JWT_PRIVATE_KEY_FILE','jwt-private.pem'),('PAYMESH_JWT_PUBLIC_KEY_FILE','jwt-public.pem')]:
            if self.env.get(name) and self.env[name] != str(self.private / filename):
                raise Stop('Unexpected existing JWT key path; do not rotate keys during this operation.')
            self.env[name] = str(self.private / filename)
        for tool in ('psql', 'pg_dump', 'pg_restore'):
            if ' 16.' not in self.command([PG / tool, '--version']):
                raise Stop('PostgreSQL 16 tools required.')
        for key, port, cwd, kind in [('java', 18080, self.repo / 'backend', 'java'), ('frontend', 5500, self.repo, 'python'), ('ai', 8000, self.repo / 'ai-service', 'python'), ('llm', 8082, Path.home() / 'Developer/paymesh-tools/llama.cpp', 'llm')]:
            if not hasattr(self, 'services'):
                self.services = {}
            self.services[key] = self.service(port, cwd, kind)
        self.launch()
        self.index_before = hashlib.sha256((self.repo / '.git/index').read_bytes()).hexdigest()
        self.staged_before = self.command(['/usr/bin/git', '-C', self.repo, 'diff', '--cached', '--binary'])
        self.stage = 'credential-and-database-preflight'
        self.db_password = hidden('Existing paymesh_demo_user database password (hidden): ')
        if not self.db_password:
            raise Stop('Empty database credential.')
        if self.sql('SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()') != 'paymesh_demo|paymesh_demo_user|127.0.0.1|5432':
            raise Stop('Actual database target mismatch.')
        history = self.sql("SELECT string_agg(version,',' ORDER BY installed_rank) FILTER(WHERE version IS NOT NULL)||'|'||CASE WHEN bool_and(success) THEN 'ok' ELSE 'failed' END FROM public.flyway_schema_history")
        if history != '1,2,3,4,5,6,7,8,9,10|ok':
            raise Stop('Successful V1-V10 history is required; no migration/repair is authorized.')
        columns = set(self.sql("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='demo_recovery_eligibility'").splitlines())
        if columns != {'user_id', 'portal', 'enabled', 'designated_by', 'review_reference', 'designated_at'}:
            raise Stop('Eligibility schema differs from inspected V10.')
        self.before = self.counts()
        if self.before[-2:] != [6, 4]:
            raise Stop('Financial counts differ from the approved baseline.')
        self.evidence['beforeCounts'] = self.before
        self.evidence['beforeServices'] = self.services
        self.enabled_before = self.http_json('/api/v1/auth/password/capabilities')[1].get('localDemoEnabled')
        if self.http_json('proxy:/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is not self.enabled_before:
            raise Stop('Direct/proxy capability mismatch.')

    def account(self, name):
        result = self.sql("SELECT json_build_object('id',u.user_id,'enabled',u.enabled,'status',u.account_status,'version',u.authorization_version,'roles',(SELECT json_agg(role_name ORDER BY role_name) FROM public.user_roles r WHERE r.user_id=u.user_id)) FROM public.app_users u WHERE login_normalized=" + literal(name))
        return json.loads(result) if result else None

    def check_account(self, account, role):
        if not account or account['roles'] != [role] or not account['enabled'] or account['status'] != ('ACTIVE' if role == 'ADMIN' else 'PENDING_APPROVAL'):
            raise Stop('Dedicated account role/enabled/status differs from the required single-role disposable account.')
        identifier(account['id'])

    def backup(self):
        self.stage = 'protected-backup'
        destination = self.private / 'backups'
        if not destination.exists():
            destination.mkdir(mode=0o700)
        protected(destination, 0o700)
        size = int(self.sql('SELECT pg_database_size(current_database())'))
        if shutil.disk_usage(destination).free < size * 3 + 1073741824:
            raise Stop('Insufficient backup/startup disk reserve.')
        fd, path = tempfile.mkstemp(prefix='paymesh_demo-pre-otp-' + self.mode + '-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-', dir=destination)
        os.close(fd); path = Path(path)
        env = dict(self.env, PGPASSWORD=self.db_password, PGOPTIONS='-c default_transaction_read_only=on')
        self.command([PG / 'pg_dump', '-w', '-h', '127.0.0.1', '-p', '5432', '-U', 'paymesh_demo_user', '-d', 'paymesh_demo', '-Fc', '-f', path], env=env)
        protected(path)
        if not path.stat().st_size:
            raise Stop('Empty backup.')
        listing = self.command([PG / 'pg_restore', '--list', path])
        (self.run_dir / 'archive-list.txt').write_text(listing)
        self.command([PG / 'pg_restore', '--file=/dev/null', path])
        digest = hashlib.sha256()
        with path.open('rb') as archive:
            for chunk in iter(lambda: archive.read(1024 * 1024), b''):
                digest.update(chunk)
        checksum = digest.hexdigest()
        with Path(str(path) + '.sha256').open('x') as out:
            out.write(checksum + '  ' + str(path) + '\n')
        self.evidence['backup'] = {'path': str(path), 'sha256': checksum, 'mode': '600', 'listVerified': True, 'extractionVerified': True, 'testRestorePerformed': False}
        if self.counts() != self.before:
            raise Stop('Counts changed during backup.')

    def reviewer(self):
        self.stage = 'authenticated-reviewer'
        expected = self.account(REVIEWER)
        self.check_account(expected, 'ADMIN')
        password = hidden('Existing demo-admin password for authorized designation (hidden): ')
        try:
            status, response = self.http_json('/api/v1/auth/login', {'login': REVIEWER, 'password': password})
            if status != 200 or response.get('tokenType') != 'Bearer':
                raise Stop('Administrator authentication failed.')
            raw = response['accessToken']; payload = raw.split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
            if claims.get('sub') != expected['id'] or claims.get('roles') != ['ADMIN'] or claims.get('account_status') != 'ACTIVE' or claims.get('authorization_version') != expected['version'] or claims.get('exp', 0) <= time.time():
                raise Stop('Authenticated reviewer does not match current ADMIN state.')
            return {'id': identifier(expected['id']), 'version': int(expected['version']), 'expires': int(claims['exp'])}, raw
        finally:
            password = ''
            # JWT/password remain only in this short-lived process; never persist/print them.

    def create_admin(self, token):
        self.stage = 'authenticated-admin-provisioning'
        if input('Create the disposable Admin through the authenticated API; type CREATE_OTP_ADMIN: ').strip() != 'CREATE_OTP_ADMIN':
            raise Stop('Admin creation was not confirmed.')
        password = hidden('New dedicated Admin password (hidden): ')
        confirmation = hidden('Confirm dedicated Admin password (hidden): ')
        try:
            if password != confirmation or len(password) < 12 or len(password.encode('utf-8')) > 72 or '\0' in password:
                raise Stop('Password confirmation/policy failed; no Admin creation submitted.')
            status, response = self.http_json('/api/v1/admin/accounts',
                {'login': ADMIN, 'password': password, 'confirmPassword': confirmation}, bearer=token)
            if status != 201:
                raise Stop('Admin API rejected creation or its outcome is unconfirmed. Deploy the new JAR with OTP disabled first; inspect the dedicated name before retrying. No automatic retry/reset.')
            account = self.account(ADMIN)
            self.check_account(account, 'ADMIN')
            if (response.get('userId') != account['id'] or response.get('login') != ADMIN
                    or response.get('roles') != ['ADMIN'] or response.get('enabled') is not True
                    or response.get('accountStatus') != 'ACTIVE'):
                raise Stop('Admin creation response/state mismatch; stop before eligibility and inspect authorized state.')
            return account
        finally:
            password = confirmation = ''

    def prepare_accounts(self):
        self.stage = 'dedicated-account-prerequisites'
        if self.enabled_before is not False:
            raise Stop('Activation requires recovery to be disabled initially.')
        merchant, admin = self.account(MERCHANT), self.account(ADMIN)
        self.evidence['dedicatedNamesAlreadyExist'] = {'merchant': merchant is not None, 'admin': admin is not None}
        expected = [4 + bool(admin) + bool(merchant), 3 + bool(merchant), 3 + bool(merchant), 1 + bool(merchant), 6, 4]
        if self.before != expected:
            raise Stop('Baseline counts are not explained solely by dedicated-account additions.')
        if admin:
            self.check_account(admin, 'ADMIN')
        if merchant:
            self.check_account(merchant, 'MERCHANT')
        if self.sql('SELECT count(*) FROM public.demo_recovery_eligibility WHERE enabled') != '0':
            raise Stop('Unexpected enabled eligibility; no broad changes are permitted.')
        if input('Confirm these exact dedicated names are disposable; type DISPOSABLE_OTP_ACCOUNTS_ONLY: ').strip() != 'DISPOSABLE_OTP_ACCOUNTS_ONLY':
            raise Stop('Disposable-account confirmation not supplied.')
        self.backup()
        reviewer, token = self.reviewer()
        try:
            if admin is None:
                admin = self.create_admin(token)
                self.evidence['adminCreatedByScript'] = True
            else:
                self.evidence['adminCreatedByScript'] = False
        finally:
            token = None
        if admin['id'] == reviewer['id']:
            raise Stop('Operational reviewer must never become eligible.')
        # Evidence of creation via the supported authenticated internal administration service.
        authorized_creation = self.sql("SELECT count(*) FROM public.security_audit_events e JOIN public.app_users a ON a.user_id=e.actor_user_id WHERE e.event_type='ACCOUNT_CREATED' AND e.outcome='SUCCESS' AND e.resource_type='ACCOUNT' AND e.resource_id=" + literal(admin['id']) + " AND e.metadata->>'role'='ADMIN' AND a.enabled AND a.account_status='ACTIVE' AND EXISTS(SELECT 1 FROM public.user_roles r WHERE r.user_id=a.user_id AND r.role_name='ADMIN')")
        if int(authorized_creation) < 1:
            raise Stop('Dedicated ADMIN has no matching authorized provisioning audit; never substitute bootstrap/hash SQL.')
        if merchant is None:
            self.stage = 'merchant-registration'
            if input('Create the synthetic pending Merchant and acknowledge demo terms; type REGISTER_OTP_MERCHANT: ').strip() != 'REGISTER_OTP_MERCHANT':
                raise Stop('Registration not confirmed.')
            password = hidden('New dedicated Merchant password (hidden): ')
            confirmation = hidden('Confirm dedicated Merchant password (hidden): ')
            try:
                if password != confirmation or len(password) < 12 or len(password.encode('utf-8')) > 72 or '\0' in password:
                    raise Stop('Password confirmation/policy failed; no registration submitted.')
                status, response = self.http_json('/api/v1/auth/register', {'firstName': 'OTP', 'lastName': 'Merchant', 'businessName': 'PayMesh disposable OTP demonstration', 'email': MERCHANT, 'mobile': '9999999999', 'businessType': 'OTHER', 'country': 'IN', 'password': password, 'confirmPassword': confirmation, 'terms': True})
                if status != 201 or response.get('accountStatus') != 'PENDING_APPROVAL':
                    raise Stop('Registration outcome unconfirmed; inspect the account before any retry.')
            finally:
                password = confirmation = ''
            merchant = self.account(MERCHANT)
            self.check_account(merchant, 'MERCHANT')
            self.evidence['merchantCreatedByScript'] = True
        else:
            self.evidence['merchantCreatedByScript'] = False
        if self.sql('SELECT count(*) FROM public.merchant_registrations WHERE user_id=' + literal(merchant['id']) + '::uuid AND email=' + literal(MERCHANT)) != '1':
            raise Stop('Dedicated Merchant is not the expected pending registration.')
        if self.counts() != [6, 4, 4, 2, 6, 4]:
            raise Stop('Post-provisioning counts differ; no eligibility will be enabled.')
        state = {'admin': identifier(admin['id']), 'merchant': identifier(merchant['id']), 'reviewer': reviewer, 'reference': 'phase673-step17-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}
        if self.manifest.exists():
            previous = json.loads(protected(self.manifest).read_text())
            if any(previous.get(k) != state[k] for k in ('admin', 'merchant')):
                raise Stop('Existing private target manifest refers to different accounts.')
        self.private_json(self.manifest, state, replace=True)
        return state

    def eligibility(self, state, enable):
        # All substituted data are canonical UUIDs, generated review metadata or integers, never passwords.
        admin, merchant = identifier(state['admin']), identifier(state['merchant'])
        targets = literal(admin) + '::uuid,' + literal(merchant) + '::uuid'
        checks = """DO $$ BEGIN
IF NOT EXISTS(SELECT 1 FROM public.app_users u WHERE u.user_id=ADMIN_ID::uuid AND u.login_normalized='otp-admin-demo' AND u.enabled AND u.account_status='ACTIVE' AND (SELECT array_agg(r.role_name ORDER BY r.role_name) FROM public.user_roles r WHERE r.user_id=u.user_id)=ARRAY['ADMIN']::varchar[]) THEN RAISE EXCEPTION 'Dedicated admin mismatch'; END IF;
IF NOT EXISTS(SELECT 1 FROM public.app_users u WHERE u.user_id=MERCHANT_ID::uuid AND u.login_normalized='otp-merchant-demo@example.test' AND u.enabled AND u.account_status='PENDING_APPROVAL' AND (SELECT array_agg(r.role_name ORDER BY r.role_name) FROM public.user_roles r WHERE r.user_id=u.user_id)=ARRAY['MERCHANT']::varchar[]) THEN RAISE EXCEPTION 'Dedicated merchant mismatch'; END IF;
IF EXISTS(SELECT 1 FROM public.demo_recovery_eligibility WHERE enabled AND user_id NOT IN (TARGETS)) THEN RAISE EXCEPTION 'Unexpected eligibility'; END IF;
END $$;""".replace('ADMIN_ID', literal(admin)).replace('MERCHANT_ID', literal(merchant)).replace('TARGETS', targets)
        if not enable:
            # Deactivation must still contain the feature if a disposable account was disabled/changed.
            checks = "DO $$ BEGIN IF (SELECT count(*) FROM public.app_users WHERE (user_id=" + literal(admin) + "::uuid AND login_normalized='otp-admin-demo') OR (user_id=" + literal(merchant) + "::uuid AND login_normalized='otp-merchant-demo@example.test'))<>2 THEN RAISE EXCEPTION 'Disposable target identity changed'; END IF; END $$;"
        sql = "BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('paymesh:account-administration',0));\n" + checks
        if enable:
            reviewer = state['reviewer']; reviewer_id = identifier(reviewer['id'])
            sql += "\nDO $$ BEGIN IF clock_timestamp()>=to_timestamp(" + str(int(reviewer['expires'])) + ") OR NOT EXISTS(SELECT 1 FROM public.app_users u WHERE u.user_id=" + literal(reviewer_id) + "::uuid AND u.enabled AND u.account_status='ACTIVE' AND u.authorization_version=" + str(int(reviewer['version'])) + " AND EXISTS(SELECT 1 FROM public.user_roles r WHERE r.user_id=u.user_id AND r.role_name='ADMIN') AND NOT EXISTS(SELECT 1 FROM public.user_roles r WHERE r.user_id=u.user_id AND r.role_name<>'ADMIN')) THEN RAISE EXCEPTION 'Reviewer authorization expired'; END IF; END $$;"
            reference = state['reference']
            if not re.fullmatch(r'phase673-step17-[0-9TZ]+', reference):
                raise Stop('Invalid generated review reference.')
            for account, portal in ((admin, 'ADMIN'), (merchant, 'MERCHANT')):
                sql += '\nINSERT INTO public.demo_recovery_eligibility(user_id,portal,enabled,designated_by,review_reference) VALUES (' + literal(account) + '::uuid,' + literal(portal) + ',true,' + literal(reviewer_id) + '::uuid,' + literal(reference) + ') ON CONFLICT(user_id) DO UPDATE SET portal=EXCLUDED.portal,enabled=true,designated_by=EXCLUDED.designated_by,review_reference=EXCLUDED.review_reference,designated_at=CURRENT_TIMESTAMP;'
        else:
            sql += '\nUPDATE public.demo_recovery_eligibility SET enabled=false WHERE user_id IN (' + targets + ');'
        # Same consumed_at invalidation semantics as LocalPasswordRecovery.invalidate(), under the same lock.
        sql += '\nUPDATE public.password_recovery_challenges SET consumed_at=COALESCE(consumed_at,CURRENT_TIMESTAMP) WHERE user_id IN (' + targets + ');'
        sql += '\nUPDATE public.password_reset_authorizations SET consumed_at=COALESCE(consumed_at,CURRENT_TIMESTAMP) WHERE challenge_id IN (SELECT challenge_id FROM public.password_recovery_challenges WHERE user_id IN (' + targets + ')); COMMIT;'
        self.stage = 'eligibility-and-invalidation'
        self.sql(sql, write=True)

    def configuration(self, enable):
        self.stage = 'private-configuration'
        config = self.run_dir / 'otp.properties'
        with config.open('x') as out:
            os.chmod(config, 0o600)
            out.write('paymesh.demo.password-recovery.enabled=' + str(enable).lower() + '\n')
            if enable:
                out.write('paymesh.demo.password-recovery.operator-confirmation=NO_PUBLIC_PROXY_OR_TUNNEL\n')
                out.write('paymesh.demo.password-recovery.key=' + secrets.token_hex(32) + '\n')
        self.config = config
        self.evidence['privateConfig'] = str(config)

    def restart(self, enable):
        if not hasattr(self, 'config'):
            self.configuration(enable)
        config = self.config
        self.unchanged_other_services()
        if self.service(18080, self.repo / 'backend', 'java') != self.services['java']:
            raise Stop('Java identity changed before stop.')
        flags = dict(self.flags)
        locations = [x for x in flags.get('spring.config.additional-location', '').split(',') if x]
        flags['spring.config.additional-location'] = ','.join(locations + ['file:' + str(config)])
        flags['paymesh.demo.password-recovery.enabled'] = str(enable).lower()
        flags['paymesh.demo.password-recovery.operator-confirmation'] = 'NO_PUBLIC_PROXY_OR_TUNNEL'
        if hashlib.sha256(self.jar.read_bytes()).hexdigest() != self.jar_sha:
            raise Stop('Artifact changed during preparation; no restart is authorized.')
        self.stage = 'java-restart'
        self.evidence['javaStopRequested'] = True
        os.kill(int(self.services['java']['pid']), 15)
        for _ in range(30):
            try:
                os.kill(int(self.services['java']['pid']), 0)
            except ProcessLookupError:
                break
            time.sleep(1)
        else:
            raise Stop('Java did not stop; no force-kill or duplicate startup.')
        self.evidence['javaStopConfirmed'] = True
        occupied = self.command(['/usr/sbin/lsof', '-t', '-nP', '-iTCP:18080', '-sTCP:LISTEN'], allow_empty=True)
        if occupied:
            raise Stop('Port18080 was claimed by another process.')
        env = dict(self.env, PAYMESH_DB_PASSWORD=self.db_password, PAYMESH_DB_URL=TARGET, PAYMESH_DEMO_DB_URL=TARGET, PAYMESH_DB_USER='paymesh_demo_user')
        for key in list(env):
            if re.sub(r'[^A-Za-z0-9]', '', key).upper() == 'PAYMESHDEMOPASSWORDRECOVERYKEY':
                env.pop(key)  # Fresh protected file is authoritative; no stale environment key may override it.
        with (self.run_dir / 'java.log').open('xb') as log:
            process = subprocess.Popen([self.command(['/usr/libexec/java_home', '-v', '21']) + '/bin/java', '-jar', str(self.jar)] + ['--' + k + '=' + v for k, v in flags.items()], cwd=self.repo / 'backend', env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        self.evidence['newJavaPid'] = process.pid
        for _ in range(120):
            if process.poll() is not None:
                raise Stop('Java startup failed; inspect the private log. No automatic retry/rollback.')
            try:
                if self.http_json('/actuator/health/readiness')[1].get('status') == 'UP':
                    break
            except Stop:
                pass
            time.sleep(1)
        else:
            raise Stop('Readiness timeout; do not repeatedly restart blindly.')
        if self.service(18080, self.repo / 'backend', 'java')['pid'] != str(process.pid):
            raise Stop('Unexpected new Java listener.')
        for prefix in ('', 'proxy:'):
            if self.http_json(prefix + '/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is not enable:
                raise Stop('Recovery capability does not match the requested state.')
        self.unchanged_other_services()
        self.evidence['recoveryEnabled'] = enable
        self.evidence['privateConfig'] = str(config)

    def run(self):
        self.preflight()
        if self.mode == 'deploy':
            if self.enabled_before is not False or self.sql('SELECT count(*) FROM public.demo_recovery_eligibility WHERE enabled') != '0':
                raise Stop('Deploy requires OTP disabled and no enabled eligibility.')
            if self.before != BASELINE:
                raise Stop('Deploy expects the approved four-user baseline; review changed counts before deploying.')
            if input('Deploy reviewed additional-Admin API with OTP DISABLED; type DEPLOY_ADMIN_API_OTP_DISABLED: ').strip() != 'DEPLOY_ADMIN_API_OTP_DISABLED':
                raise Stop('Deployment confirmation not supplied.')
            self.backup()
            self.restart(False)
            if self.counts() != self.before:
                raise Stop('Deployment counts changed; inspect private evidence.')
            if self.http_json('/api/v1/payments/health')[0] != 200:
                raise Stop('Payment health verification failed.')
            self.evidence['afterCounts'] = self.counts()
            self.evidence['result'] = 'Verified deployment; OTP remains disabled; no accounts created.'
            return
        if self.mode == 'activate':
            if input('Confirm PRIVATE loopback-only deployment, no public proxy/tunnel. Type NO_PUBLIC_PROXY_OR_TUNNEL: ').strip() != 'NO_PUBLIC_PROXY_OR_TUNNEL':
                raise Stop('Private deployment attestation was not supplied.')
            state = self.prepare_accounts()  # Authenticated API only, after fresh backup.
            self.configuration(True)
            self.eligibility(state, True)
            self.restart(True)
            expected_count = '2'
        else:
            self.stage = 'deactivation-targets'
            if not self.manifest.exists():
                if self.enabled_before is False and self.flags.get('paymesh.demo.password-recovery.enabled') == 'false' and self.sql('SELECT count(*) FROM public.demo_recovery_eligibility WHERE enabled') == '0':
                    self.evidence['result'] = 'Already disabled; no mutation or restart needed.'
                    return
                raise Stop('No private target manifest; do not guess accounts or perform a broad eligibility update.')
            state = json.loads(protected(self.manifest).read_text())
            self.backup()
            # Disable the global gate first, so a subsequent scoped SQL failure cannot leave recovery exposed.
            if self.enabled_before is True or self.flags.get('paymesh.demo.password-recovery.enabled') != 'false':
                self.restart(False)
            self.eligibility(state, False)
            expected_count = '0'
        admin, merchant = identifier(state['admin']), identifier(state['merchant'])
        actual = self.sql('SELECT count(*) FROM public.demo_recovery_eligibility WHERE enabled')
        exact = self.sql('SELECT count(*) FROM public.demo_recovery_eligibility WHERE enabled AND ((user_id=' + literal(admin) + "::uuid AND portal='ADMIN') OR (user_id=" + literal(merchant) + "::uuid AND portal='MERCHANT'))")
        if actual != expected_count or exact != expected_count:
            raise Stop('Only the two intended target eligibilities may be enabled.')
        after = self.counts()
        if after[-2:] != [6, 4] or (self.mode == 'activate' and after != [6, 4, 4, 2, 6, 4]) or (self.mode == 'disable' and after != self.before):
            raise Stop('Post-operation counts mismatch.')
        if self.http_json('proxy:/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is not (self.mode == 'activate'):
            raise Stop('Final proxy capability mismatch.')
        self.unchanged_other_services()
        self.evidence['afterCounts'] = after
        self.evidence['dedicatedTargets'] = {'admin': admin, 'merchant': merchant}
        self.evidence['result'] = 'Verified ' + self.mode

    def closeout(self, success):
        self.evidence.update({'stage': self.stage, 'success': success})
        if hasattr(self, 'index_before'):
            after = hashlib.sha256((self.repo / '.git/index').read_bytes()).hexdigest()
            current = self.command(['/usr/bin/git', '-C', self.repo, 'diff', '--cached', '--binary'])
            self.evidence['indexPreserved'] = after == self.index_before
            self.evidence['stagedPreserved'] = current == self.staged_before
        self.private_json(self.run_dir / 'evidence.json', self.evidence)
        with self.report.open('a') as out:
            out.write('\n## Operator Step17 ' + self.mode + ' evidence\n\n')
            out.write('Outcome: ' + ('verified' if success else 'stopped; no automatic retry/restore') + '. Stage: ' + self.stage + '. Private evidence: `' + str(self.run_dir / 'evidence.json') + '`.\n')
            out.write('No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.\n')
        self.db_password = None
        print(('Verified.' if success else 'Stopped safely; review private evidence.') + ' Evidence: ' + str(self.run_dir / 'evidence.json'))


def main():
    os.umask(0o077)
    if len(sys.argv) != 2 or sys.argv[1] not in ('activate', 'disable', 'deploy') or not sys.stdin.isatty() or not sys.stdout.isatty():
        print('Operator-only interactive activation/deactivation; no passwords in arguments.', file=sys.stderr)
        return 1
    ops = None
    try:
        ops = Ops(sys.argv[1]); ops.run(); ops.closeout(True); return 0
    except Stop as failure:
        print(str(failure), file=sys.stderr)  # Stop messages are fixed; never raw underlying exceptions.
    except (Exception, KeyboardInterrupt):
        print('Operation failed or was interrupted; inspect protected evidence, not raw credentials.', file=sys.stderr)
    if ops:
        try:
            ops.closeout(False)
        except Exception:
            print('Could not complete the private evidence record. No automatic retry.', file=sys.stderr)
    return 1

if __name__ == '__main__':
    sys.exit(main())
