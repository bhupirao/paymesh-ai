"""Explicit operator-only Python reload. Inert on import; no inference or database calls.

Preserves native launch environment, except the fresh protected diagnostic sink.
Current PID/microsecond identities and reviewed source hashes are pinned. No retry,
forced termination, automatic recovery, Java/frontend/llama restart or DB connection.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from phase673_otp_ops import Ops, Stop, protected
from phase697a_process import MacOS, snapshot, assert_same
from phase697a_diagnostic import SOURCE_FILES, credentials, read_sink, unique_pairs, matching_record

EXPECTED = {
    'ai': {'pid':'50828','start':'Tue Nov 17 22:36:17 2026'},
    'java': {'pid':'43617','start':'Tue Nov 17 07:50:16 2026'},
    'frontend': {'pid':'41673','start':'Tue Nov 17 07:09:16 2026'},
    'llm': {'pid':'79855','start':'Sat Nov 14 09:43:39 2026'},
}
NATIVE_EXPECTED = {
    'ai': (50828,1794935177,865250,501),
    'java': (43617,1794882016,867215,501),
    'frontend': (41673,1794879556,684801,501),
    'llm': (79855,1794629619,200196,501),
}
FIELD = 'PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE'
PRIOR = 'otp-step17-python-correlated-diagnostics-reload-20261117T170549Z-smlgqpzt/evidence.json'
CONFIRM = 'RELOAD_ONLY_PYTHON_WITH_CORRELATED_DIAGNOSTICS'
REVIEWED_HASHES = {'ai-service/app/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'ai-service/app/api/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'ai-service/app/api/body_limit.py': '1d509c1f64ab6c77354d141b768119aa97cf4dc92c846035d02831856a51e6ac', 'ai-service/app/api/chat.py': '6f41fce583b7f5e5894dd3535da209c48b0b9bc815dc9de20d786b4add8165dc', 'ai-service/app/api/chat_boundary.py': '2bd9a19e8102f3d972067137d38e73f9456767f4385a0f27664e813004983e62', 'ai-service/app/api/health.py': 'c43310fe0e0dbe51a061f926f109ddf033451bedecb1fd30a9c934dcdec0cde2', 'ai-service/app/api/investigations.py': '53d3ea18ddf704909794ee42483b8b5769d428b2a839a02dd4ebb082b5e857c9', 'ai-service/app/config.py': 'f05e4c7a68fb8be5c1c41f70d48e5805bffd5f6e1249997d92ceff45f9198f15', 'ai-service/app/main.py': 'be7047caf5c5aeec00e1f214262bffcb878906f04639ae055e1e004323640545', 'ai-service/app/schemas/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'ai-service/app/schemas/chat.py': '545df98b673c332604442851d006c1c9ec9abb77ec2bf502b2a0d87dd511e40c', 'ai-service/app/schemas/investigation.py': '732ee7786859f3765b1db41b61de4fdf03ec18cf28f0534ef617383851d928f6', 'ai-service/app/services/__init__.py': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'ai-service/app/services/chat_service.py': 'b296c4bf51235aa9dd6377659ad947047481bba232d0ede0a49d1c3835b73bf4', 'ai-service/app/services/chat_validation_diagnostics.py': 'fafa42e9bfe9857543e68176830c30dceaa671d87f711321299283e07d089562', 'ai-service/app/services/generation_budget.py': 'e394e55e0f4bb89af681c48f740c7f5e49e62f0b6804844c0389290e9ebf6ce0', 'ai-service/app/services/investigation_service.py': 'bf29536b7ef1c697f173c27cea360bc92c2149de49307a8d700edc69133c9ae6', 'ai-service/app/services/local_provider.py': '6c733c400103839b4fce7e49b019db623acbba67219f33051bdcbb7f57616eb3', 'ai-service/app/services/rag_service.py': '6792658ea47995f365d4860706d847fbe8b2477bdeb1c844f0e616bb43276634', 'ai-service/app/services/retrieval.py': 'ddd2dd95daea64c3270e2e7dd999e49682619200a130f2b57bbf840d25141a41', 'backend/scripts/phase673_otp_ops.py': '9934221f87c01ce1f4c91714dbeb757332f7d1aab6cff9177d4260e1d9041159', 'backend/scripts/phase697a_diagnostic.py': '61028f38c821b05f89496b5f19f47106b6830b95b0d40fd2eed060d1649a0e81', 'backend/scripts/phase697a_process.py': '23c9834c567225f09bd6d4465807562c9f5d1798155d670b896adbe40f22f0ad'}


class Reload(Ops):
    def __init__(self):
        super().__init__('python-correlated-diagnostics-reload')
        self.native = MacOS()
        self.specs = {
            'ai':(8000,self.repo/'ai-service','python'),
            'java':(18080,self.repo/'backend','java'),
            'frontend':(5500,self.repo,'python'),
            'llm':(8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm'),
        }

    def checked_sources(self):
        if not REVIEWED_HASHES:
            raise Stop('Reviewed source manifest missing.')
        for name,digest in REVIEWED_HASHES.items():
            if hashlib.sha256((self.repo/name).read_bytes()).hexdigest() != digest:
                raise Stop('Reviewed source changed; request another review.')

    def identities(self):
        return {name:self.service(*spec) for name,spec in self.specs.items()}

    def preserved_services(self):
        for name in ('java','frontend','llm'):
            if self.service(*self.specs[name]) != self.services[name]:
                raise Stop('A preserved service changed; stop for review.')
            assert_same(self.saved[name],self.native)

    def fence_python(self):
        if self.service(*self.specs['ai']) != self.services['ai']:
            raise Stop('Python listener identity changed before stop.')
        assert_same(self.saved['ai'],self.native)

    def wait_stopped(self):
        pid = self.saved['ai'].identity[0]
        for _ in range(120):
            try:os.kill(pid,0)
            except ProcessLookupError:return
            except PermissionError:raise Stop('Python identity inaccessible; no forced kill.') from None
            assert_same(self.saved['ai'],self.native)
            time.sleep(0.25)
        raise Stop('Python did not exit; no forced kill or retry.')

    def wait_listener(self,child):
        for _ in range(120):
            if child.poll() is not None:
                raise Stop('Replacement Python exited; no automatic recovery.')
            pids = set(self.command(['/usr/sbin/lsof','-t','-nP','-iTCP:8000','-sTCP:LISTEN'],allow_empty=True).split())
            if pids:
                if pids != {str(child.pid)}:
                    raise Stop('Port8000 claimed by another process; stop for review.')
                return self.service(*self.specs['ai'])
            time.sleep(0.25)
        raise Stop('Replacement listener unavailable; no automatic recovery.')

    def health_once(self):
        # Exactly one GET per metadata endpoint; no HTTP retries or chat invocation.
        def get(path):
            try:
                with self.http.open('http://127.0.0.1:8000'+path,timeout=5) as response:
                    raw=response.read(1048577)
                    if response.status!=200 or len(raw)>1048576:
                        raise Stop('Python metadata check failed; do not retry automatically.')
                    return json.loads(raw)
            except Stop:raise
            except Exception:raise Stop('Python metadata check failed; do not retry automatically.') from None
        h=get('/health')
        if h.get('status')!='UP' or h.get('configuredAnalysisMode')!='RAG_LLM':
            raise Stop('Python health is not the reviewed RAG_LLM configuration.')
        schema=get('/openapi.json')
        if 'post' not in schema.get('paths',{}).get('/api/v1/chat',{}):
            raise Stop('Private chat route missing from Python metadata.')

    def preserved_files(self):
        for path,digest in self.file_hashes.items():
            if hashlib.sha256(protected(Path(path)).read_bytes()).hexdigest()!=digest:
                raise Stop('Previous protected evidence changed; stop for review.')
        inode,raw=read_sink(self.old_sink,self.private)
        if inode!=self.old_inode or raw!=self.old_raw:
            raise Stop('Previous diagnostic sink changed; preserve it for review.')

    def run(self):
        self.checked_sources()
        self.services=self.identities()
        if self.services!=EXPECTED:
            raise Stop('Pinned service identities changed; request a fresh review.')
        self.saved={name:snapshot(int(identity['pid']),self.native) for name,identity in self.services.items()}
        if any(saved.identity!=NATIVE_EXPECTED[name] for name,saved in self.saved.items()):
            raise Stop('Pinned microsecond process identity changed.')
        self.evidence['beforeServices']=self.services
        self.evidence['beforeNativeProcessIdentities']={name:list(saved.identity) for name,saved in self.saved.items()}
        prior=protected(self.private/PRIOR)
        previous=json.loads(prior.read_text(),object_pairs_hook=unique_pairs)
        old_expected=dict(previous.get('beforeServices',{}));old_expected['ai']=previous.get('newPythonIdentity')
        if previous.get('success') is not True or previous.get('diagnosticsEnabled') is not True or old_expected!=self.services:
            raise Stop('Previous successful diagnostic evidence differs.')
        self.old_sink=Path(previous['diagnosticFile'])
        self.old_inode,self.old_raw=read_sink(self.old_sink,self.private)
        # Historical correlated reasons are valid evidence, not an empty-file prerequisite.
        # Validate without attribution; preserve every byte and inode through reload.
        matching_record(self.old_raw,str(uuid.uuid4()))
        self.file_hashes={str(prior):hashlib.sha256(prior.read_bytes()).hexdigest()}
        self.evidence['priorActivationEvidence']=str(prior)
        self.evidence['retainedDiagnosticFile']=str(self.old_sink)
        python=self.saved['ai'];java=self.saved['java']
        credentials(python,java,self.private,self.old_sink)
        if (self.repo/'ai-service/.env').exists():
            raise Stop('Unexpected Python dotenv configuration.')
        launcher=self.repo/'ai-service/.venv/bin/python'
        if python.environment.get('HOME')!=str(Path.home()) or python.environment.get('__PYVENV_LAUNCHER__')!=str(launcher) or python.executable!='/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python':
            raise Stop('Python home/interpreter differs from reviewed launcher.')
        # The native snapshot supplies every environment value unchanged, in memory.
        environment=dict(python.environment)
        if input('Type NO_PUBLIC_PROXY_OR_TUNNEL: ').strip()!='NO_PUBLIC_PROXY_OR_TUNNEL':
            raise Stop('Private deployment attestation missing.')
        if input('Type '+CONFIRM+': ').strip()!=CONFIRM:
            raise Stop('Python reload not approved.')
        diagnostic=self.run_dir/'chat-validation-diagnostics.jsonl'
        fd=os.open(diagnostic,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        os.close(fd)
        _,empty=read_sink(diagnostic,self.private)
        if empty:raise Stop('Fresh diagnostic sink is not empty.')
        environment[FIELD]=str(diagnostic)
        self.evidence['diagnosticFile']=str(diagnostic)
        self.checked_sources();self.preserved_files();self.preserved_services();self.fence_python()
        self.stage='python-stop';self.evidence['stopRequested']=True
        os.kill(python.identity[0],signal.SIGTERM)  # Only this pinned AI PID; no force kill.
        self.wait_stopped()
        if self.command(['/usr/sbin/lsof','-t','-nP','-iTCP:8000','-sTCP:LISTEN'],allow_empty=True):
            raise Stop('Port8000 is occupied; replacement not started.')
        self.preserved_services();self.checked_sources()
        self.stage='python-start'
        fd=os.open(self.run_dir/'python.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as log:
            child=subprocess.Popen([str(launcher),*python.argv[1:]],cwd=self.repo/'ai-service',env=environment,
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        self.evidence['newPythonPid']=child.pid
        self.evidence['newPythonIdentity']=self.wait_listener(child)
        self.stage='python-health';self.health_once()
        replacement=snapshot(child.pid,self.native)
        if replacement.environment!=environment or replacement.argv[1:]!=python.argv[1:] or replacement.executable!=python.executable:
            raise Stop('Replacement launch state differs; no automatic recovery.')
        credentials(replacement,java,self.private,diagnostic)
        self.preserved_services();self.preserved_files();self.checked_sources()
        for saved in (replacement,self.saved['java'],self.saved['llm']):assert_same(saved,self.native)
        # Required by internal-diagnostic; exact current application hashes plus native identities.
        self.evidence['sourceHashes']={name:REVIEWED_HASHES['ai-service/'+name] for name in SOURCE_FILES}
        self.evidence['nativeProcessIdentities']={name:list(saved.identity) for name,saved in {
            'ai':replacement,'java':self.saved['java'],'llm':self.saved['llm']}.items()}
        self.evidence.update(diagnosticsEnabled=True,diagnosticSchemaVersion=3,existingEnvironmentPreserved=True,
            noAccessLog=True,inferencePerformed=False,databaseRequests=False,preservedServicesVerified=True)
        self.stage='verified'

    def finish(self,success):
        self.evidence.update(success=success,stage=self.stage)
        self.private_json(self.run_dir/'evidence.json',self.evidence)
        print('PYTHON_CORRELATED_DIAGNOSTICS_READY; INFERENCE_NOT_PERFORMED' if success else 'STOPPED_NO_AUTOMATIC_RETRY_OR_RECOVERY')
        print('Protected activation evidence: '+str(self.run_dir/'evidence.json'))


def main():
    os.umask(0o077);op=None
    if len(sys.argv)!=1 or not sys.stdin.isatty() or not sys.stdout.isatty():
        print('Interactive no-argument operator wrapper required.');return 1
    try:
        op=Reload();op.run();op.finish(True);return 0
    except Stop as error:print(str(error),file=sys.stderr)
    except (Exception,KeyboardInterrupt):print('Python reload stopped; preserve protected evidence; no automatic recovery.',file=sys.stderr)
    if op:
        try:op.finish(False)
        except Exception:print('Protected evidence could not be completed.',file=sys.stderr)
    return 1

if __name__=='__main__':sys.exit(main())
