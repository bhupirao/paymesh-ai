"""Offline only: no signals, listeners, credentials, database or live services."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from phase673_otp_ops import Stop
from ai_reliability_python_launch import python_spec
from ai_reliability_forward import Forward,java_spec,env_digest,TABLES,FINANCIAL,CONFIRM
class ReleaseTests(unittest.TestCase):
 def py(self):return SimpleNamespace(argv=('python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log'),environment={'PAYMESH_AI_CHAT_SERVICE_TOKEN':'SYNTHETIC_ONLY','PAYMESH_AI_MODEL_NAME':'same-model','PAYMESH_AI_GENERATION_TIMEOUT':'30'})
 def java(self):return SimpleNamespace(executable='/reviewed/java',argv=('java','-jar','/prior.jar','--spring.datasource.url=jdbc:postgresql://127.0.0.1:5432/paymesh_demo','--spring.datasource.username=paymesh_demo_user','--server.address=127.0.0.1','--server.port=18080','--paymesh.jwt.audience=same-audience','--paymesh.ai.chat.enabled=true','--spring.flyway.enabled=true'))
 def test_python_new_release_only_and_secret_not_argv(self):
  saved=self.py();args,cwd,env=python_spec('/release',saved,'/private/sink',True)
  self.assertEqual(Path('/release/python'),cwd);self.assertEqual('/release/python/.venv/bin/python',args[0]);self.assertEqual(saved.argv[1:],tuple(args[1:]));self.assertNotIn('SYNTHETIC_ONLY',' '.join(args));self.assertEqual('same-model',env['PAYMESH_AI_MODEL_NAME']);self.assertEqual('1',env['PYTHONDONTWRITEBYTECODE'])
 def test_python_disabled_independent_of_inference_configuration(self):
  saved=self.py();_,_,env=python_spec('/release',saved,'/sink',False)
  self.assertEqual('false',env['PAYMESH_AI_CHAT_API_ENABLED']);self.assertEqual('30',env['PAYMESH_AI_GENERATION_TIMEOUT']);self.assertEqual('SYNTHETIC_ONLY',env['PAYMESH_AI_CHAT_SERVICE_TOKEN']);self.assertNotIn('PAYMESH_AI_CHAT_API_ENABLED',saved.environment)
 def test_import_override_rejected(self):
  saved=self.py();saved.environment['PYTHONPATH']='unreviewed'
  with self.assertRaises(Stop):python_spec('/release',saved,'/sink',True)
 def test_wrong_python_listener_rejected(self):
  saved=self.py();saved.argv=(*saved.argv[:-2],'0','--access-log')
  with self.assertRaises(Stop):python_spec('/release',saved,'/sink',True)
 def test_java_preserves_configuration_disables_migrations_cleanup_otp(self):
  args=java_spec(self.java(),'/new.jar',True)
  for flag in ('--spring.flyway.enabled=false','--spring.jpa.hibernate.ddl-auto=validate','--spring.sql.init.mode=never','--paymesh.conversations.cleanup-enabled=false','--paymesh.jwt.audience=same-audience','--paymesh.demo.password-recovery.enabled=false','--paymesh.demo.checkout-controls.enabled=false'):self.assertIn(flag,args)
  self.assertNotIn('--spring.flyway.enabled=true',args);self.assertEqual(1,sum(a.startswith('--paymesh.ai.chat.enabled=') for a in args))
 def test_degraded_uses_new_artifact_and_independent_chat_flag(self):
  args=java_spec(self.java(),'/new.jar',False);self.assertEqual('/new.jar',args[2]);self.assertIn('--paymesh.ai.chat.enabled=false',args)
  self.assertFalse(any('refund.enabled=false' in a or 'payments.enabled=false' in a for a in args))
 def test_wrong_database_rejected(self):
  saved=self.java();saved.argv=tuple(a.replace('5432/paymesh_demo','5432/unreviewed') for a in saved.argv)
  with self.assertRaises(Stop):java_spec(saved,'/new.jar',True)
 def test_all_declared_tables_exist_in_migrations(self):
  import re
  sql='\n'.join(p.read_text() for p in (Path(__file__).resolve().parents[1]/'src/main/resources/db/migration').glob('V*.sql'))
  names=set(re.findall(r'CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)',sql,re.I));self.assertTrue(set(TABLES)<=names);self.assertEqual(8,len(FINANCIAL));self.assertEqual(len(TABLES),len(set(TABLES)))
 def test_environment_whitespace_is_not_split(self):self.assertNotEqual(env_digest({'key':'with whitespace'}),env_digest({'key':'with'}))
 def test_file_pin_failure_stops_without_action(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'source';p.write_text('changed');op=object.__new__(Forward);op.release=Path(d);op.m={'filePins':{'source':'0'*64}}
   with patch('ai_reliability_forward.os.kill') as kill,patch('ai_reliability_forward.subprocess.Popen') as pop:
    with self.assertRaises(Stop):op.check()
    kill.assert_not_called();pop.assert_not_called()
 def test_existing_listener_never_starts_replacement(self):
  op=object.__new__(Forward);op.m={'services':{'ai':{'port':8000}}};op.listeners=Mock(return_value='occupied')
  with patch('ai_reliability_forward.subprocess.Popen') as pop:
   with self.assertRaises(Stop):op.start('ai',[],Path('/release'),{})
   pop.assert_not_called()
 def test_identity_failure_never_sends_signal(self):
  op=object.__new__(Forward);op.native=Mock();saved=SimpleNamespace(identity=(1,2,3,4))
  with patch('ai_reliability_forward.assert_same',side_effect=Stop('changed')),patch('ai_reliability_forward.os.kill') as kill:
   with self.assertRaises(Stop):op.stop(saved,8000)
   kill.assert_not_called()
 def test_backup_gate_never_stops_services_on_mismatch(self):
  op=object.__new__(Forward);op.stop=Mock()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'backup';p.write_text('synthetic');p.chmod(0o600)
   with self.assertRaises(Stop):op.deploy(True,{'backup':{'path':str(p),'sha256':'0'*64,'readable':True},'success':True})
   op.stop.assert_not_called()
 def test_deploy_order_and_metadata_only_health(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);archive=folder/'backup';archive.write_text('synthetic');archive.chmod(0o600);(folder/'release-manifest.json').write_text('{}')
   op=object.__new__(Forward);op.release=folder;op.private=folder;op.folder=folder;op.m={'services':{'java':{'cwd':d}}};op.e={};op.native=Mock()
   op.java=self.java();op.java.environment={};op.python=self.py();op.integrity=Mock(return_value={'payments':'same'});op.write=Mock();op.stop=Mock();op.preserved=Mock();op.check=Mock();op.start=Mock(side_effect=[op.python,op.java])
   op.health=Mock(side_effect=[{'status':'UP'},{'paths':{'/api/v1/chat':{'post':{}}}},{'status':'UP'},{'status':'RUNNING'},{'localDemoEnabled':False}])
   prior={'success':True,'backup':{'path':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'readable':True},'integrity':{'payments':'same'},'releaseManifestSha256':hashlib.sha256(b'{}').hexdigest()}
   with patch('ai_reliability_forward.credentials'),patch('ai_reliability_forward.assert_same'):op.deploy(True,prior)
   self.assertEqual([18080,8000],[call.args[1] for call in op.stop.call_args_list]);self.assertEqual(['ai','java'],[call.args[0] for call in op.start.call_args_list]);self.assertTrue(op.e['chatEnabled']);self.assertTrue(all('/chat' not in c.args[0] for c in op.health.call_args_list));self.assertEqual(0o600,(folder/'chat-validation-diagnostics.jsonl').stat().st_mode&0o777)
 def test_changed_database_stops_before_termination(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'backup';a.write_text('x');a.chmod(0o600);m=p/'release-manifest.json';m.write_text('{}')
   op=object.__new__(Forward);op.release=p;op.integrity=Mock(return_value={'different':True});op.stop=Mock()
   prior={'success':True,'backup':{'path':str(a),'sha256':hashlib.sha256(b'x').hexdigest(),'readable':True},'releaseManifestSha256':hashlib.sha256(b'{}').hexdigest(),'integrity':{}}
   with self.assertRaises(Stop):op.deploy(True,prior)
   op.stop.assert_not_called()
 def test_missing_migration_history_is_fail_closed(self):
  op=object.__new__(Forward);op.m={'migrationHistory':[{'version':'14'}]};op.db=Mock(return_value='[]')
  with self.assertRaises(Stop):op.integrity()
  self.assertEqual(1,op.db.call_count)
 def test_confirmations_are_distinct(self):self.assertEqual(3,len(set(CONFIRM.values())))
if __name__=='__main__':unittest.main()
