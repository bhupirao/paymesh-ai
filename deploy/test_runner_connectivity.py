"""Offline runner/proxy wiring regression; no Docker, sockets or real accounts."""
import ast,copy,io,json,subprocess,sys,unittest
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock,patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'deploy'),str(ROOT/'frontend')]
import container_e2e
from frontend_entry import ContainerHandler

class RunnerConnectivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def yaml(path):return json.loads(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(path)]))
        cls.compose=yaml(ROOT/'deploy/compose.yaml');cls.workflow=yaml(ROOT/'.github/workflows/container-e2e.yml')
    def require_publishable_edge(self,compose):
        java=compose['services']['java']
        self.assertTrue(any(not compose['networks'][n].get('internal',False) for n in java['networks']),
                        'internal-only endpoints do not program published-port connectivity')
        self.assertEqual(java['ports'],['127.0.0.1:15500:15500'])
    def test_published_frontend_has_non_internal_bridge_endpoint(self):
        self.require_publishable_edge(self.compose)
        self.assertEqual(self.compose['networks']['edge'],{'driver':'bridge'})
    def test_original_internal_only_configuration_is_rejected(self):
        broken=copy.deepcopy(self.compose);broken['services']['java']['networks']=['database']
        with self.assertRaises(AssertionError):self.require_publishable_edge(broken)
    def test_database_remains_internal_and_unpublished(self):
        postgres=self.compose['services']['postgres']
        self.assertEqual(postgres['networks'],['database']);self.assertTrue(self.compose['networks']['database']['internal'])
        self.assertNotIn('ports',postgres);self.assertEqual(postgres['volumes'],['container_pgdata:/var/lib/postgresql/data'])
    def test_shared_namespace_exposes_only_frontend_port(self):
        services=self.compose['services'];self.assertEqual(len(services),5)
        for name in ['frontend','python','llama']:
            self.assertEqual(services[name]['network_mode'],'service:java');self.assertNotIn('ports',services[name])
        self.assertEqual(services['java']['environment']['SERVER_ADDRESS'],'127.0.0.1')
    def test_runner_url_matches_listener_and_host_publication(self):
        self.assertEqual(container_e2e.BASE,'http://127.0.0.1:15500')
        tree=ast.parse((ROOT/'deploy/frontend_entry.py').read_text())
        call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ThreadingHTTPServer')
        self.assertEqual(ast.literal_eval(call.args[0]),('0.0.0.0',15500))
        self.require_publishable_edge(self.compose)
    def test_workflow_uses_host_python_and_real_qwen(self):
        job=self.workflow['jobs']['e2e'];self.assertNotIn('container',job)
        step=next(s for s in job['steps'] if s.get('id')=='api_e2e')
        self.assertEqual(step['run'],'python3 -B deploy/container_e2e.py')
        self.assertEqual(self.workflow.get('on',self.workflow.get('true'))['workflow_dispatch']['inputs']['verify_qwen']['default'],True)
    def test_login_still_passes_through_proxy_to_fixed_java_target(self):
        handler=object.__new__(ContainerHandler);handler.command='POST';handler.headers=Message()
        body=b'{"login":"synthetic@example.invalid","password":"synthetic-test-only"}'
        handler.headers['Origin']=container_e2e.BASE;handler.headers['Content-Type']='application/json';handler.headers['X-PayMesh-CSRF']='1'
        handler.rfile=io.BytesIO(body);handler.reply=MagicMock();handler.error=MagicMock()
        connection=MagicMock();response=connection.getresponse.return_value;response.status=401
        response.read.return_value=b'{"status":401,"message":"Authentication failed"}';response.getheader.return_value=None
        with patch('dev_server.http.client.HTTPConnection',return_value=connection) as create:
            handler.proxy('/api/v1/auth/login',len(body))
        create.assert_called_once_with('127.0.0.1',18080,timeout=15)
        args,kwargs=connection.request.call_args
        self.assertEqual(args,('POST','/api/v1/auth/login'))
        self.assertEqual(kwargs['body'],body);self.assertEqual(kwargs['headers']['Origin'],'http://127.0.0.1:5500')
        self.assertEqual(kwargs['headers']['X-PayMesh-CSRF'],'1');self.assertNotIn('Authorization',kwargs['headers'])
        handler.reply.assert_called_once_with(401,response.read.return_value,'application/json',{})
        handler.error.assert_not_called();connection.close.assert_called_once()

if __name__=='__main__':unittest.main()
