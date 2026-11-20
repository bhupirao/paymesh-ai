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
        for table in ('ai_conversations', 'ai_conversation_messages', 'ai_conversation_requests', 'ai_conversation_creations', 'gateway_transactions', 'webhook_events'):
            require(self.sql('SELECT count(*) FROM '+table+';') == '0', 'EMPTY_RELEASE_DATABASE_REQUIRED')
        self.sql("""BEGIN READ ONLY;
DO $$ DECLARE t record; populated boolean; BEGIN
  FOR t IN SELECT table_schema,table_name FROM information_schema.tables
           WHERE table_schema='public' AND table_type='BASE TABLE'
             AND table_name<>'flyway_schema_history'
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
        # No volume pruning. The dedicated hosted VM owns and discards its volume.
        import subprocess
        result = subprocess.run(['docker', 'compose', '--project-name', project, '--env-file', str(folder/'container.env'), '-f', COMPOSE, 'down', '--timeout', '30'], capture_output=True, timeout=90)
        require(result.returncode == 0, 'DISPOSABLE_TEARDOWN_FAILED')
        print('DISPOSABLE_PROJECT_STOPPED');return 0
    raise Failure('UNKNOWN_RELEASE_ACTION')


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1] if len(sys.argv) == 2 else ''))
    except Exception:
        print('RELEASE_ARTIFACT_GUARD_OR_OPERATION_FAILED');raise SystemExit(1)
