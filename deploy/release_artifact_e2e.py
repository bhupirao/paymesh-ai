"""Published v1 artifacts only. Inert on import; execution is hosted-runner guarded.
No credentials, HTTP bodies, generated content or raw exceptions enter evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from ci_fixture_setup import prepare, runner_project
from container_e2e import Suite, Session, Failure, require

COMPOSE = 'deploy/compose.release-verify.yaml'
LOCK = Path(__file__).with_name('release-v1.0.0-images.json')
SOURCE = 'cefa7df83a5bf16d011e82041c95e2d93b9c637b'


def guard():
    project = runner_project()
    require(os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted', 'HOSTED_RUNNER_REQUIRED')
    require(os.environ.get('GITHUB_REPOSITORY') == 'bhupirao/paymesh-ai', 'REPOSITORY_REQUIRED')
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'MANUAL_DISPATCH_REQUIRED')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/main', 'MAIN_REQUIRED')
    require(os.environ.get('E2E_VERIFY_QWEN') == 'true', 'REAL_MODEL_REQUIRED')
    return project


def release_lock():
    value = json.loads(LOCK.read_text())
    require(value['applicationSource'] == SOURCE and value['platform'] == 'linux/amd64'
            and value['sourceE2ERun'] == 44652430877, 'RELEASE_METADATA_MISMATCH')
    require(set(value['images']) == {'java', 'python', 'frontend', 'llama'}, 'RELEASE_IMAGES_MISMATCH')
    for service, ref in value['images'].items():
        require(re.fullmatch('bhupirao/paymesh-' + service + r'@sha256:[a-f0-9]{64}', ref), 'IMMUTABLE_IMAGE_REQUIRED')
    return value


def validate_image(container, image, service, lock):
    ref = lock['images'][service]
    require(container['Config']['Image'] == ref, 'CONTAINER_DIGEST_MISMATCH')
    # Container Image is the image CONFIG hash, not the manifest/index digest.
    require(container['Image'] == image['Id'] and ref in image.get('RepoDigests', []), 'LOCAL_IMAGE_IDENTITY_MISMATCH')
    require(image['Os'] == 'linux' and image['Architecture'] == 'amd64', 'IMAGE_PLATFORM_MISMATCH')
    require(image['Config'].get('Labels', {}).get('org.opencontainers.image.revision') == SOURCE,
            'IMAGE_SOURCE_MISMATCH')


# Fixed private target; executes in the existing Python container, not a sixth
# service. HMAC secret travels via subprocess stdin only, never argv or evidence.
WEBHOOK_CLIENT = r'''
import hashlib,hmac,json,sys,time,urllib.request,urllib.error
v=json.load(sys.stdin)
raw=json.dumps(v['payload'],separators=(',',':')).encode()
stamp=str(int(time.time()))
sig=hmac.new(v['secret'].encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
if v['invalid']:sig='0'*64
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None
client=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
req=urllib.request.Request('http://127.0.0.1:18080/api/v1/webhooks/mock-razorpay',data=raw,method='POST',headers={'Content-Type':'application/json','X-Paymesh-Timestamp':stamp,'X-Paymesh-Signature':sig})
try:
 with client.open(req,timeout=15) as response:code=response.status;body=response.read(8193)
except urllib.error.HTTPError as error:code=error.code;body=error.read(8193)
if len(body)>8192:sys.exit(2)
out={'http':code}
if code==200:
 receipt=json.loads(body)
 import uuid
 out.update(id=str(uuid.UUID(receipt['id'])),status=receipt['status'])
print(json.dumps(out))
'''


class ReleaseSession(Session):
    def call(self, method, path, body=None, expected=(200,), key=None):
        value = super().call(method, path, body, expected, key)
        if method == 'POST' and (path.endswith('/ai/chat') or path.endswith('/messages')):
            result = value.get('turn', {}).get('response', {}) if path.endswith('/messages') else value
            require(result.get('analysisMode') == 'RAG_LLM' and result.get('generationStatus') == 'SUCCEEDED'
                    and bool(result.get('knowledgeReferences')), 'REAL_MODEL_RESPONSE_REQUIRED')
        return value


class ReleaseSuite(Suite):
    def __init__(self):
        guard()
        super().__init__()
        require(Path(os.environ.get('E2E_DIR', '')).resolve() == self.folder
                and Path(os.environ.get('E2E_ENV', '')).resolve() == self.folder/'container.env',
                'FIXTURE_PATH_MISMATCH')
        self.compose[-1] = COMPOSE
        self.lock = release_lock()

    def session(self, actor):
        return ReleaseSession(actor, self.observe_request)

    def identity(self):
        super().identity()
        ids = self.command(self.compose + ['ps', '-q']).decode().split()
        states = json.loads(self.command(['docker', 'inspect', *ids]))
        require({c['Config']['Labels']['com.docker.compose.service'] for c in states}
                == {'java', 'python', 'frontend', 'llama', 'postgres'}, 'SERVICE_SET_MISMATCH')
        for container in states:
            service = container['Config']['Labels']['com.docker.compose.service']
            if service == 'postgres':
                require(container['Config']['Image'] == 'postgres:16.16-bookworm', 'POSTGRES_VERSION_MISMATCH')
                require(not container['HostConfig'].get('PortBindings'), 'DATABASE_PORT_EXPOSED')
                continue
            image = json.loads(self.command(['docker', 'image', 'inspect', self.lock['images'][service]]))
            require(len(image) == 1, 'IMAGE_INSPECT_MISMATCH')
            validate_image(container, image[0], service, self.lock)

    def seed(self):
        require(self.sql("SELECT count(*) FROM flyway_schema_history WHERE success AND version IS NOT NULL;") == '14', 'EXACT_V14_REQUIRED')
        require(self.sql("SELECT count(*) FROM flyway_schema_history WHERE NOT success;") == '0', 'FAILED_MIGRATION')
        for table in ('ai_conversations', 'ai_conversation_messages', 'ai_conversation_requests', 'ai_conversation_creations', 'payment_gateway_transactions', 'webhook_events'):
            require(self.sql('SELECT count(*) FROM '+table+';') == '0', 'EMPTY_RELEASE_DATABASE_REQUIRED')
        # V8 intentionally seeds reference roles, not accounts or assignments.
        # Validate that exact baseline before excluding it from business rows.
        require(self.sql("SELECT role_name FROM roles ORDER BY role_name;") == 'ADMIN\nMERCHANT',
                'REFERENCE_ROLE_BASELINE_MISMATCH')
        self.sql("""BEGIN READ ONLY;
DO $$ DECLARE t record; populated boolean; BEGIN
  FOR t IN SELECT table_schema,table_name FROM information_schema.tables
           WHERE table_schema='public' AND table_type='BASE TABLE'
             AND table_name NOT IN ('flyway_schema_history','roles')
  LOOP
    EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I.%I)',t.table_schema,t.table_name) INTO populated;
    IF populated THEN RAISE EXCEPTION 'CI_EMPTY_DATABASE_REQUIRED'; END IF;
  END LOOP;
END $$; ROLLBACK;""")
        super().seed()

    def webhook(self):
        # A signed terminal-state event must be safely ignored, not re-execute a
        # successful payment. This does not claim timeout-recovery coverage.
        require(re.fullmatch(r'[a-f0-9-]{36}', self.payment_id), 'PAYMENT_UUID_REQUIRED')
        payload = {'eventId': 'release-'+str(uuid.uuid4()), 'paymentId': self.payment_id,
                   'gatewayTransactionId': str(uuid.uuid4()), 'status': 'SUCCESS',
                   'occurredAt': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
        secret = (self.folder/'secrets/razorpay_secret').read_text()
        def send(invalid):
            data = json.dumps({'payload': payload, 'secret': secret, 'invalid': invalid}).encode()
            return json.loads(self.command(self.compose+['exec', '-T', 'python', 'python', '-B', '-c', WEBHOOK_CLIENT], data))
        require(send(True) == {'http': 401}, 'INVALID_WEBHOOK_SIGNATURE_ACCEPTED')
        require(self.sql('SELECT count(*) FROM webhook_events;') == '0', 'INVALID_WEBHOOK_PERSISTED')
        first, duplicate = send(False), send(False)
        require(first == duplicate and first['http'] == 200 and first['status'] == 'IGNORED', 'WEBHOOK_DUPLICATE_MISMATCH')
        require(self.sql('SELECT count(*) FROM webhook_events;') == '1', 'DUPLICATE_WEBHOOK_PERSISTED')
        require(self.sql('SELECT attempts FROM webhook_events;') == '1', 'DUPLICATE_WEBHOOK_REPROCESSED')
        payment = self.a.call('GET', '/api/v1/payments/'+self.payment_id)
        require(payment['status'] == 'SUCCESS', 'WEBHOOK_CHANGED_TERMINAL_PAYMENT')

    def investigation(self):
        for session in (self.a, self.admin):
            response = session.call('POST', '/api/v1/payments/'+self.payment_id+'/investigate')
            result = response['investigation']
            require(result['paymentId'] == self.payment_id and result['investigationStatus'] == 'COMPLETED', 'INVESTIGATION_SCOPE')
            require(result['analysisMode'] == 'RAG_LLM' and result['generationStatus'] == 'SUCCEEDED'
                    and result['knowledgeReferences'] and result['evidenceReferences'], 'INVESTIGATION_MODEL_REQUIRED')
        self.b.call('POST', '/api/v1/payments/'+self.payment_id+'/investigate', expected=(403, 404))

    def payment(self):
        super().payment()
        self.check('signed_webhooks_and_replay', self.webhook)
        self.check('authorized_real_model_investigation', self.investigation)

    def run(self):
        status = super().run()
        path = self.folder/'sanitized-e2e.json'
        report = json.loads(path.read_text())
        report.update(verificationKind='PUBLISHED_ARTIFACTS', applicationSource=SOURCE,
                      sourceE2ERun=44652430877, releaseImages=self.lock['images'],
                      releaseLockSha256=hashlib.sha256(LOCK.read_bytes()).hexdigest(),
                      applicationImagesBuilt=False)
        require(len(json.dumps(report).encode()) <= 32768, 'EVIDENCE_TOO_LARGE')
        path.write_text(json.dumps(report, indent=2)+'\n');path.chmod(0o600)
        return status



def cleanup_project(project, folder, *, compose_file=COMPOSE, validate_config=None):
    """Remove only proven runner-project resources; preserve fixed-code evidence.

    Inspect the effective Compose model AND actual Docker ownership before down.
    Never treat a Docker CLI failure as proof of resource absence.
    """
    import subprocess
    expected = project + '_container_pgdata'
    compose = ['docker', 'compose', '--project-name', project, '--env-file',
               str(folder/'container.env'), '-f', compose_file]
    report = {'success': False, 'project': project, 'volumesAbsent': False,
              'containersAbsent': False, 'failureCode': None}

    def command(args, timeout=15):
        result = subprocess.run(args, capture_output=True, timeout=timeout)
        require(result.returncode == 0, 'CLEANUP_DOCKER_OPERATION_FAILED')
        require(len(result.stdout) <= 131072, 'CLEANUP_RESPONSE_TOO_LARGE')
        return result.stdout.decode('utf-8')

    def names(args):
        return command(args).splitlines()

    volume_list = ['docker', 'volume', 'ls', '--filter',
                   'label=com.docker.compose.project='+project, '--format', '{{.Name}}']
    exact_volume = ['docker', 'volume', 'ls', '--filter', 'name=^'+expected+'$',
                    '--format', '{{.Name}}']
    containers = ['docker', 'ps', '-a', '--no-trunc', '--filter',
                  'label=com.docker.compose.project='+project, '--format', '{{.ID}}']
    try:
        require(compose_file in (COMPOSE, 'deploy/compose.candidate-browser.yaml', 'deploy/compose.demo.yaml'), 'CLEANUP_UNREVIEWED_COMPOSE')
        require(compose_file == COMPOSE or validate_config is not None, 'CLEANUP_CANDIDATE_VALIDATION_REQUIRED')
        config = json.loads(command(compose+['config', '--format', 'json']))
        if validate_config is not None:
            validate_config(config)
        require(config.get('name') == project, 'CLEANUP_PROJECT_MISMATCH')
        require(set(config.get('volumes', {})) == {'container_pgdata'}, 'CLEANUP_UNEXPECTED_VOLUME_CONFIG')
        volume = config['volumes']['container_pgdata']
        require(volume.get('name') == expected and not volume.get('external')
                and volume.get('driver', 'local') == 'local' and not volume.get('driver_opts'),
                'CLEANUP_EXTERNAL_OR_SHARED_VOLUME')
        services = config.get('services', {})
        require(set(services) == {'postgres', 'java', 'python', 'frontend', 'llama'}, 'CLEANUP_SERVICE_MISMATCH')
        declared = []
        for service, definition in services.items():
            require(not definition.get('volumes_from'), 'CLEANUP_SHARED_MOUNTS')
            for mount in definition.get('volumes', []):
                require(isinstance(mount, dict), 'CLEANUP_UNREVIEWED_MOUNT')
                if mount.get('type') == 'volume':
                    declared.append((service, mount.get('source'), mount.get('target')))
        require(declared == [('postgres', 'container_pgdata', '/var/lib/postgresql/data')],
                'CLEANUP_UNEXPECTED_VOLUME_MOUNT')
        owned_volumes, named_volumes = names(volume_list), names(exact_volume)
        require(set(owned_volumes) <= {expected} and set(named_volumes) <= {expected},
                'CLEANUP_UNEXPECTED_OWNED_VOLUME')
        require(set(owned_volumes) == set(named_volumes), 'CLEANUP_VOLUME_OWNERSHIP_MISMATCH')
        ids = names(containers)
        require(len(ids) <= 5 and len(ids) == len(set(ids))
                and all(re.fullmatch('[a-f0-9]{64}', i) for i in ids), 'CLEANUP_UNEXPECTED_CONTAINERS')
        if owned_volumes:
            inspected = json.loads(command(['docker', 'volume', 'inspect', expected]))
            require(len(inspected) == 1, 'CLEANUP_VOLUME_INSPECT_MISMATCH')
            actual = inspected[0];labels = actual.get('Labels') or {}
            require(actual.get('Name') == expected and actual.get('Driver') == 'local'
                    and actual.get('Scope') == 'local' and not actual.get('Options')
                    and labels.get('com.docker.compose.project') == project
                    and labels.get('com.docker.compose.volume') == 'container_pgdata',
                    'CLEANUP_VOLUME_OWNERSHIP_MISMATCH')
            users = names(['docker', 'ps', '-a', '--no-trunc', '--filter', 'volume='+expected,
                           '--format', '{{.ID}}'])
            require(set(users) <= set(ids), 'CLEANUP_VOLUME_SHARED_WITH_FOREIGN_CONTAINER')
        if ids:
            # Select only identity and mount metadata; never emit Config.Env.
            fmt = '{"id":{{json .Id}},"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}}}'
            records = [json.loads(line) for line in command(['docker', 'inspect', '--format', fmt, *ids]).splitlines()]
            require(len(records) == len(ids) and {c['id'] for c in records} == set(ids), 'CLEANUP_CONTAINER_INSPECT_MISMATCH')
            seen = set()
            for container in records:
                labels = container.get('labels') or {};service = labels.get('com.docker.compose.service')
                require(labels.get('com.docker.compose.project') == project and service in services
                        and service not in seen, 'CLEANUP_CONTAINER_OWNERSHIP_MISMATCH')
                seen.add(service)
                for mount in container.get('mounts', []):
                    if mount.get('Type') == 'volume':
                        require(service == 'postgres' and mount.get('Name') == expected
                                and expected in owned_volumes
                                and mount.get('Destination') == '/var/lib/postgresql/data',
                                'CLEANUP_UNEXPECTED_ACTUAL_VOLUME')
        command(compose+['down', '--volumes', '--timeout', '30'], timeout=90)
        require(not names(volume_list) and not names(exact_volume), 'CLEANUP_VOLUMES_REMAIN')
        report['volumesAbsent'] = True
        require(not names(containers), 'CLEANUP_CONTAINERS_REMAIN')
        report.update(containersAbsent=True, success=True)
    except Exception as error:
        code = str(error) if isinstance(error, Failure) else 'CLEANUP_UNEXPECTED_OPERATION_FAILURE'
        report['failureCode'] = code if re.fullmatch('[A-Z0-9_]{1,80}', code) else 'CLEANUP_UNCLASSIFIED_FAILURE'
    # Owner-only fixture parent; exclusive file preserves any previous evidence.
    path = folder/'sanitized-cleanup.json'
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'w') as output:
        output.write(json.dumps(report, indent=2)+'\n')
    print('DISPOSABLE_PROJECT_AND_VOLUMES_REMOVED' if report['success'] else report['failureCode'])
    return 0 if report['success'] else 1


def main(action):
    project = guard()
    if action == 'fixtures':
        release_lock();prepare();return 0
    if action == 'run':
        return ReleaseSuite().run()
    folder = Path(os.environ['RUNNER_TEMP']).resolve()/project
    require(os.environ.get('E2E_PROJECT') == project
            and Path(os.environ.get('E2E_DIR', '')).resolve() == folder
            and Path(os.environ.get('E2E_ENV', '')).resolve() == folder/'container.env', 'CLEANUP_PATH_MISMATCH')
    if action == 'diagnostics':
        from capture_failure_diagnostics import collect
        collect(COMPOSE);return 0
    if action == 'cleanup':
        return cleanup_project(project, folder)
    raise Failure('UNKNOWN_RELEASE_ACTION')


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1] if len(sys.argv) == 2 else ''))
    except Exception:
        print('RELEASE_ARTIFACT_GUARD_OR_OPERATION_FAILED');raise SystemExit(1)
