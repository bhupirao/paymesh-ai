"""Offline cold-start configuration and failure guards. No service/network/DB calls."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from phase673_otp_ops import Stop
from ai_reliability_cold import configs,env_file,empty_ports,Cold,CONFIRM
class ColdTests(unittest.TestCase):
 def test_env_home_expansion_without_shell(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'env';p.write_text('KEY="$HOME/safe"\n');p.chmod(0o600)
   self.assertEqual(str(Path.home())+'/safe',env_file(p)['KEY'])
 def test_shell_substitution_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'env';p.write_text('KEY="$(not_executed)"\n');p.chmod(0o600)
   with self.assertRaises(Stop):env_file(p)
 def test_duplicate_env_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'env';p.write_text('KEY=x\nKEY=y\n');p.chmod(0o600)
   with self.assertRaises(Stop):env_file(p)
 def settings(self,folder):
  props=folder/'props';props.write_text('paymesh.ai.chat.service-token='+'T'*64+'\n');props.chmod(0o600)
  return {'javaChatFile':str(props),'pythonChatFile':str(folder/'python.env'),'javaExecutable':'/java21','javaFlags':['--spring.flyway.enabled=false','--server.address=127.0.0.1'],'pythonSettings':{'PAYMESH_AI_MODEL_NAME':'paymesh-qwen','PAYMESH_AI_GENERATION_TIMEOUT':'30'}}
 def env(self,path):
  if Path(path).name=='demo.env':return dict(PAYMESH_DB_USER='paymesh_demo_user',PAYMESH_JWT_PRIVATE_KEY_FILE='/private/key',PAYMESH_JWT_PUBLIC_KEY_FILE='/private/public',PAYMESH_JWT_ISSUER='same',PAYMESH_JWT_AUDIENCE='same',PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED='true',PAYMESH_DB_URL='IGNORED_LEGACY_URL')
  if Path(path).name=='secrets.env':return {k:'SYNTHETIC_ONLY' for k in ('PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN')}
  return {'PAYMESH_AI_CHAT_SERVICE_TOKEN':'T'*64}
 def test_java_python_credentials_match_and_password_only_in_memory_environment(self):
  with tempfile.TemporaryDirectory() as d,patch('ai_reliability_cold.env_file',side_effect=self.env):
   p=Path(d);j,py,args=configs(p,self.settings(p),'SYNTHETIC_DB_PASSWORD')
   self.assertEqual('jdbc:postgresql://127.0.0.1:5432/paymesh_demo',j['PAYMESH_DB_URL']);self.assertEqual('SYNTHETIC_DB_PASSWORD',j['PAYMESH_DB_PASSWORD']);self.assertNotIn('SYNTHETIC_DB_PASSWORD',' '.join(args));self.assertEqual('T'*64,py['PAYMESH_AI_CHAT_SERVICE_TOKEN']);self.assertNotIn('PAYMESH_DB_PASSWORD',py)
 def test_disabled_chat_preserves_payment_and_gateway_configuration(self):
  with tempfile.TemporaryDirectory() as d,patch('ai_reliability_cold.env_file',side_effect=self.env):
   p=Path(d);j,py,args=configs(p,self.settings(p),'SYNTHETIC_DB_PASSWORD',False)
   self.assertIn('--paymesh.ai.chat.enabled=false',args);self.assertEqual('false',py['PAYMESH_AI_CHAT_API_ENABLED']);self.assertEqual('true',j['PAYMESH_AI_ENABLED']);self.assertEqual('SYNTHETIC_ONLY',j['PAYMESH_RAZORPAY_WEBHOOK_SECRET'])
 def test_mismatched_shared_token_rejected(self):
  with tempfile.TemporaryDirectory() as d,patch('ai_reliability_cold.env_file',side_effect=self.env):
   p=Path(d);m=self.settings(p);Path(m['javaChatFile']).write_text('paymesh.ai.chat.service-token='+'X'*64+'\n')
   with self.assertRaises(Stop):configs(p,m,'SYNTHETIC')
 def test_existing_port_never_treated_as_free(self):
  with patch('ai_reliability_cold.subprocess.run',return_value=SimpleNamespace(stdout=b'p123',returncode=0)):
   with self.assertRaises(Stop):empty_ports()
 def test_baseline_change_is_not_accepted(self):
  import sys
  op=object.__new__(Cold);op.m={'migrationHistory':[],'databaseBaseline':{'fingerprints':{},'tableCounts':{}}}
  fake=SimpleNamespace(snapshot=Mock(return_value={'history':[],'fingerprints':{'changed':True},'counts':{}}))
  with patch.dict(sys.modules,{'v14_backup_reader':fake}):
   with self.assertRaises(Stop):op.baseline('SYNTHETIC')
 def test_failed_start_is_one_attempt(self):
  with tempfile.TemporaryDirectory() as d:
   op=object.__new__(Cold);op.m={'ports':{'llm':8082},'cwd':{'llm':d},'startupTimeoutSeconds':{'llm':1}};op.listeners=Mock(return_value='');op.folder=Path(d);op.e={};op.native=Mock();op.write=Mock()
   child=SimpleNamespace(pid=999,poll=Mock(return_value=1));identity=SimpleNamespace(identity=(999,1,0,501))
   with patch('ai_reliability_cold.subprocess.Popen',return_value=child) as pop,patch('ai_reliability_cold.snapshot',return_value=identity):
    with self.assertRaises(Stop):op.launch('llm',['/binary'],{})
    pop.assert_called_once()
 def test_missing_llama_allows_disabled_chat_recovery_without_model_restart(self):
  op=object.__new__(Cold);op.m={'ports':{'llm':8082}};op.listeners=Mock(return_value='')
  self.assertIsNone(op.retained({},'llm'))
 def test_dead_retained_service_is_not_restarted_or_killed(self):
  op=object.__new__(Cold);op.m={'ports':{'frontend':5500}};op.listeners=Mock(return_value='')
  with patch('ai_reliability_cold.subprocess.run',return_value=SimpleNamespace(stdout='')):
   self.assertIsNone(op.retained({'frontendIdentity':[123,1,0,501]},'frontend'))
 def test_unknown_retained_listener_is_fail_closed(self):
  op=object.__new__(Cold);op.m={'ports':{'llm':8082}};op.listeners=Mock(return_value='occupied')
  with self.assertRaises(Stop):op.retained({},'llm')
 def test_live_retained_service_keeps_exact_identity(self):
  op=object.__new__(Cold);op.m={'ports':{'frontend':5500}};op.inspect=Mock(return_value='same-service')
  with patch('ai_reliability_cold.subprocess.run',return_value=SimpleNamespace(stdout='S')):
   self.assertEqual('same-service',op.retained({'frontendIdentity':[123,1,0,501]},'frontend'))
  op.inspect.assert_called_once_with('frontend',[123,1,0,501])
 def test_normal_startup_order_uses_no_inference_or_database_mutation(self):
  import urllib.error
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);archive=folder/'backup';archive.write_text('safe');archive.chmod(0o600);evidence=folder/'backup.json';evidence.write_text('{}');evidence.chmod(0o600)
   op=object.__new__(Cold);op.release=folder;op.private=folder;op.folder=None;op.e={};op.check=Mock();op.write=Mock();op.inspect=Mock();op.stop=Mock()
   import hashlib
   op.m={'backup':{'path':str(archive),'sha256':hashlib.sha256(b'safe').hexdigest()},'backupEvidence':str(evidence),'backupEvidenceSha256':hashlib.sha256(b'{}').hexdigest(),'llamaCommand':['/llama'],'frontendPython':'/python'}
   base={'fingerprints':{}};op.baseline=Mock(return_value=base);services=[SimpleNamespace(identity=(n,1,0,501)) for n in (10,11,12,13)];op.launch=Mock(side_effect=services)
   op.health=Mock(side_effect=[{'paths':{'/api/v1/chat':{'post':{}}}},{'status':'RUNNING'},{'localDemoEnabled':False}])
   def opened(url,timeout):
    if '/api/v1/' in url:raise urllib.error.HTTPError(url,401,'',None,None)
    response=Mock();response.status=200;response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);return response
   op.http=SimpleNamespace(open=Mock(side_effect=opened))
   with patch('ai_reliability_cold.empty_ports'),patch('ai_reliability_cold.prompt_password',return_value='SYNTHETIC'),patch('ai_reliability_cold.configs',return_value=({'PAYMESH_DB_PASSWORD':'SYNTHETIC'}, {},['/java'])),patch('ai_reliability_cold.digest',side_effect=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p) in (archive,evidence) else 'fixed'),patch('ai_reliability_cold.sys.stdin.isatty',return_value=True),patch('ai_reliability_cold.sys.stdout.isatty',return_value=True),patch('builtins.input',side_effect=['NO_PUBLIC_PROXY_OR_TUNNEL',CONFIRM['start']]):
    op.run_cold('start')
   self.assertEqual(['llm','ai','java','frontend'],[c.args[0] for c in op.launch.call_args_list]);op.stop.assert_not_called();self.assertTrue(op.e['databaseUnchanged']);self.assertEqual(2,op.baseline.call_count);self.assertFalse(any('/pay' in c.args[0] for c in op.http.open.call_args_list))
 def test_distinct_explicit_approval_gates(self):self.assertNotEqual(CONFIRM['start'],CONFIRM['degrade'])
if __name__=='__main__':unittest.main()
