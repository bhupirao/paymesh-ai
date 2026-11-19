"""Exercise the actual workflow shell with a fake Docker CLI, never real Docker."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class BuildCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(ROOT/'.github/workflows/container-e2e.yml')])
        cls.workflow=json.loads(raw)
        cls.script=next(s['run'] for s in cls.workflow['jobs']['e2e']['steps'] if s.get('name')=='Validate Compose and build all images on one ephemeral runner')
    def execute(self,script=None,fail=''):
        with tempfile.TemporaryDirectory(prefix='paymesh-mocked-build-') as name:
            folder=Path(name);log=folder/'calls.jsonl';binary=folder/'docker'
            binary.write_text('#!'+sys.executable+'\n'+'''import json,os,sys
args=sys.argv[1:]
with open(os.environ['MOCK_CALLS'],'a') as out:out.write(json.dumps(args)+'\\n')
if args[0]=='compose':
    # Reproduce the observed runner: attestation flags unavailable on Compose.
    if 'build' in args:sys.exit(64)
    sys.exit(0 if args[-2:]==['config','--quiet'] else 65)
if args[:2]!=['buildx','build'] or '--push' in args:sys.exit(66)
tag=args[args.index('--tag')+1]
if os.environ.get('MOCK_FAIL_IMAGE') and os.environ['MOCK_FAIL_IMAGE'] in tag:sys.exit(67)
''');binary.chmod(0o700)
            env={**os.environ,'PATH':str(folder)+os.pathsep+os.environ['PATH'],'MOCK_CALLS':str(log),'MOCK_FAIL_IMAGE':fail,'E2E_PROJECT':'paymesh-e2e-1-1','E2E_ENV':str(folder/'private config.env'),'E2E_DIR':str(folder/'runner with spaces'),'GITHUB_WORKSPACE':str(folder/'workspace with spaces')}
            result=subprocess.run(['bash','-e','-o','pipefail','-c',self.script if script is None else script],env=env,capture_output=True,text=True)
            calls=[json.loads(s) for s in log.read_text().splitlines()] if log.is_file() else []
            return result.returncode,calls,env
    def test_observed_compose_flag_failure_reproduced(self):
        code,calls,_=self.execute('docker compose build --provenance=false --sbom=false java')
        self.assertEqual(code,64);self.assertEqual(len(calls),1)
    def test_all_four_builds_use_compatible_exporter(self):
        code,calls,_=self.execute();self.assertEqual(code,0)
        builds=[c for c in calls if c[:2]==['buildx','build']]
        self.assertEqual(len(builds),4)
        for component,args in zip(('java','python','frontend','llama'),builds):
            with self.subTest(component=component):
                self.assertIn('--load',args);self.assertIn('--provenance=false',args);self.assertIn('--sbom=false',args)
                self.assertEqual(args[args.index('--platform')+1],'linux/amd64')
                self.assertEqual(args[args.index('--tag')+1],'bhupirao/paymesh-'+component+':v1.0.0')
                self.assertNotIn('--push',args)
        self.assertEqual(calls[0][-2:],['config','--quiet'])
        self.assertFalse(any(c[0]=='compose' and 'build' in c for c in calls))
    def test_context_and_dockerfile_paths_preserve_whitespace(self):
        code,calls,env=self.execute();self.assertEqual(code,0)
        builds=calls[1:];work=env['GITHUB_WORKSPACE']
        for component,args in zip(('java','python','frontend','llama'),builds):
            context=work+'/backend' if component=='java' else env['E2E_DIR']+'/llama-source' if component=='llama' else work
            file=work+'/backend/Dockerfile' if component=='java' else work+'/deploy/Dockerfile.'+component
            self.assertEqual(args[-1],context);self.assertEqual(args[args.index('--file')+1],file)
    def test_failed_build_stops_without_retry(self):
        code,calls,_=self.execute(fail='paymesh-python:');self.assertEqual(code,67)
        self.assertEqual(len([c for c in calls if c[:2]==['buildx','build']]),2)
    def test_real_qwen_requirement_and_no_publication_remain(self):
        event=self.workflow.get('on',self.workflow.get('true'))
        self.assertIs(event['workflow_dispatch']['inputs']['verify_qwen']['default'],True)
        text=(ROOT/'.github/workflows/container-e2e.yml').read_text()
        self.assertNotIn('docker/login-action',text);self.assertNotIn('push: true',text)
        self.assertIn('Run real disposable-container API E2E',text)
if __name__=='__main__':unittest.main()
