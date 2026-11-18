"""Offline launcher checks. No live Ops constructors, signals, processes or HTTP."""
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock, patch
import phase697a_python_reload as r
from phase697a_process import Snapshot
from phase673_otp_ops import Stop

REPO=Path(__file__).resolve().parents[2]

class ReloadTests(unittest.TestCase):
 def setup_op(self,t):
  op=object.__new__(r.Reload);op.repo=REPO;op.private=Path(t);op.run_dir=Path(t)/'new-run';op.run_dir.mkdir(mode=0o700);op.stage='preflight';op.evidence={};op.native=Mock()
  prior=op.private/r.PRIOR;prior.parent.mkdir(parents=True,mode=0o700)
  old=prior.parent/'chat-validation-diagnostics.jsonl';old.touch(mode=0o600)
  prior.touch(mode=0o600);prior.write_text(json.dumps({'success':True,'diagnosticsEnabled':True,'beforeServices':r.EXPECTED,'newPythonIdentity':r.EXPECTED['ai'],'diagnosticFile':str(old)}))
  env={'HOME':str(Path.home()),'__PYVENV_LAUNCHER__':str(REPO/'ai-service/.venv/bin/python'),'SYNTHETIC_CREDENTIAL':'T'*64,'WHITESPACE':' leading spaces\ttabs\nand=a=b trailing ',r.FIELD:str(old)}
  snapshots={name:Snapshot(identity,'/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python',('python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log'),dict(env)) for name,identity in r.NATIVE_EXPECTED.items()}
  op.specs={name:(8000+i,Path(t),'python') for i,name in enumerate(r.EXPECTED)}
  service_by_port={op.specs[name][0]:r.EXPECTED[name] for name in r.EXPECTED}
  op.service=Mock(side_effect=lambda port,*a:service_by_port[port]);op.identities=Mock(return_value=dict(r.EXPECTED));op.command=Mock(return_value='');op.wait_stopped=Mock();op.wait_listener=Mock(return_value={'pid':'999','start':'replacement start'});op.health_once=Mock()
  op.native.identity.side_effect=lambda pid:next(identity for identity in r.NATIVE_EXPECTED.values() if identity[0]==pid) if pid!=999 else (999,1800000000,123,os.getuid())
  def snapshot(pid,native):
   if pid==999:
    new_env=dict(env);new_env[r.FIELD]=str(op.run_dir/'chat-validation-diagnostics.jsonl')
    return Snapshot((999,1800000000,123,os.getuid()),snapshots['ai'].executable,snapshots['ai'].argv,new_env)
   return next(saved for saved in snapshots.values() if saved.identity[0]==pid)
  return op,snapshots,snapshot,old
 def flow(self,failure=None,valid_old_record=False):
  with tempfile.TemporaryDirectory() as t:
   op,saved,snapshot,old=self.setup_op(t)
   if failure=='stale':op.identities.return_value={'ai':{'pid':'different'}}
   elif failure=='native':op.native.identity.side_effect=Stop('Identity changed.')
   elif failure=='source':op.checked_sources=Mock(side_effect=Stop('Source changed.'))
   elif failure=='health':op.health_once.side_effect=Stop('Health failed.')
   elif failure=='old-sink':old.write_text('do not truncate')
   if valid_old_record:
    old.write_text(json.dumps({'correlationId':'8d447340-43f2-4a84-a1a9-83f5af5b2694','reasonCode':'SCHEMA_MISMATCH'})+'\n')
   original_sink=old.read_bytes()
   responses=['NO_PUBLIC_PROXY_OR_TUNNEL',r.CONFIRM if failure!='declined' else 'NO']
   child=Mock(pid=999)
   with patch.object(r,'snapshot',side_effect=snapshot),patch.object(r,'credentials',side_effect=Stop('Credentials differ.') if failure=='credentials' else None),patch('builtins.input',side_effect=responses),patch.object(r.os,'kill') as kill,patch.object(r.subprocess,'Popen',return_value=child) as start:
    if failure:
     with self.assertRaises(Stop):op.run()
    else:
     op.run();self.assertEqual('verified',op.stage);self.assertTrue(op.evidence['existingEnvironmentPreserved']);self.assertFalse(op.evidence['inferencePerformed']);self.assertFalse(op.evidence['databaseRequests'])
     self.assertEqual(set(r.SOURCE_FILES),set(op.evidence['sourceHashes']));self.assertEqual({'ai','java','llm'},set(op.evidence['nativeProcessIdentities']))
     launch=start.call_args
     original=saved['ai'].environment;intended=dict(original);intended[r.FIELD]=str(op.run_dir/'chat-validation-diagnostics.jsonl')
     self.assertEqual(intended,launch.kwargs['env']);self.assertEqual(saved['ai'].argv[1:],tuple(launch.args[0][1:]));self.assertEqual(str(REPO/'ai-service/.venv/bin/python'),launch.args[0][0]);self.assertTrue(launch.kwargs['start_new_session'])
     self.assertNotIn('T'*64,json.dumps(op.evidence));self.assertEqual(original_sink,old.read_bytes());self.assertEqual(3,op.evidence['diagnosticSchemaVersion'])
     self.assertEqual(0o600,(op.run_dir/'chat-validation-diagnostics.jsonl').stat().st_mode&0o777)
     self.assertEqual(0o600,(op.run_dir/'python.log').stat().st_mode&0o777)
    expected=1 if failure in (None,'health') else 0
    self.assertEqual(expected,start.call_count);self.assertEqual(expected,kill.call_count)
    if expected:kill.assert_called_once_with(r.NATIVE_EXPECTED['ai'][0],signal.SIGTERM)
 def test_reload_changes_only_diagnostic_environment_and_stops_only_python(self):self.flow()
 def test_stale_pid_prevents_stop(self):self.flow('stale')
 def test_native_identity_mismatch_prevents_stop(self):self.flow('native')
 def test_source_drift_prevents_stop(self):self.flow('source')
 def test_credential_mismatch_prevents_stop(self):self.flow('credentials')
 def test_declined_confirmation_prevents_stop(self):self.flow('declined')
 def test_malformed_existing_sink_is_refused_without_overwrite(self):self.flow('old-sink')
 def test_valid_historical_schema_reason_preserved_byte_for_byte(self):self.flow(valid_old_record=True)
 def test_health_failure_never_restarts_again(self):self.flow('health')
 def test_reviewed_source_manifest_matches(self):
  op=object.__new__(r.Reload);op.repo=REPO;op.checked_sources()
 def test_health_requests_only_metadata_once(self):
  op=object.__new__(r.Reload);op.http=Mock()
  def response(url,timeout):
   self.assertEqual(5,timeout);res=Mock();res.status=200;res.read.return_value=json.dumps({'status':'UP','configuredAnalysisMode':'RAG_LLM'} if url.endswith('/health') else {'paths':{'/api/v1/chat':{'post':{}}}}).encode();res.__enter__=Mock(return_value=res);res.__exit__=Mock(return_value=False);return res
  op.http.open.side_effect=response;op.health_once()
  self.assertEqual(['http://127.0.0.1:8000/health','http://127.0.0.1:8000/openapi.json'],[x.args[0] for x in op.http.open.call_args_list])
 def test_health_failure_is_not_retried(self):
  op=object.__new__(r.Reload);op.http=Mock();op.http.open.side_effect=OSError('SYNTHETIC_ONLY')
  with self.assertRaises(Stop):op.health_once()
  self.assertEqual(1,op.http.open.call_count)
 def test_wait_stopped_never_uses_force_kill(self):
  op=object.__new__(r.Reload);op.saved={'ai':Snapshot(r.NATIVE_EXPECTED['ai'],'',(),{})};op.native=Mock();op.native.identity.return_value=r.NATIVE_EXPECTED['ai']
  with patch.object(r.os,'kill',side_effect=[None,ProcessLookupError()]) as kill,patch.object(r.time,'sleep'):
   op.wait_stopped();self.assertEqual([0,0],[call.args[1] for call in kill.call_args_list])
 def test_foreign_listener_never_accepted(self):
  op=object.__new__(r.Reload);op.command=Mock(return_value='other-pid');child=Mock(pid=999);child.poll.return_value=None
  with self.assertRaises(Stop):op.wait_listener(child)
  self.assertEqual(1,op.command.call_count)
 def test_child_exit_never_restarted(self):
  op=object.__new__(r.Reload);child=Mock();child.poll.return_value=1
  with self.assertRaises(Stop):op.wait_listener(child)
 def test_no_database_or_inference_method_in_launcher(self):
  import ast
  tree=ast.parse(Path(r.__file__).read_text())
  names={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
  self.assertFalse(names & {'sql','counts','internal','http_json','backup','launch'})
  self.assertNotIn('eww',Path(r.__file__).read_text())
 def test_noninteractive_main_cannot_construct_operator(self):
  with patch.object(r.sys,'argv',['launcher']),patch.object(r.sys.stdin,'isatty',return_value=False),patch.object(r,'Reload') as constructor:
   self.assertEqual(1,r.main());constructor.assert_not_called()

 def test_fresh_activation_evidence_accepted_by_correlated_verifier(self):
  import phase697a_diagnostic as d
  import phase697a_ai_verify as v
  with tempfile.TemporaryDirectory() as t:
   op,saved,snapshot,old=self.setup_op(t)
   child=Mock(pid=999)
   with patch.object(r,'snapshot',side_effect=snapshot),patch.object(r,'credentials'),patch('builtins.input',side_effect=['NO_PUBLIC_PROXY_OR_TUNNEL',r.CONFIRM]),patch.object(r.os,'kill'),patch.object(r.subprocess,'Popen',return_value=child):
    op.run();op.finish(True)
   path=op.run_dir/'evidence.json';evidence=json.loads(path.read_text())
   self.assertEqual(3,evidence['diagnosticSchemaVersion']);self.assertEqual(0o600,path.stat().st_mode&0o777)
   probe=object.__new__(v.Verification);probe.repo=REPO;probe.private=op.private;probe.evidence={}
   probe.services=dict(evidence['beforeServices']);probe.services['ai']=evidence['newPythonIdentity'];probe.services_checked=Mock()
   def call(service,route,body,**kwargs):
    if probe.call.call_count==1:return 401,{},None
    return 200,{'correlationId':body['correlationId'],'analysisMode':'RAG_LLM','generationStatus':'SUCCEEDED','knowledgeReferences':[{}]},None
   probe.call=Mock(side_effect=call)
   with patch('builtins.input',return_value=str(path)),patch.object(d,'MacOS',return_value=op.native),patch.object(d,'snapshot',side_effect=snapshot),patch.object(d,'credentials',return_value='T'*64):
    d.run(probe)
   self.assertEqual(2,probe.call.call_count)  # One denied auth probe, one authenticated synthetic request.
   self.assertTrue(probe.evidence['generation']['actualInferenceProven'])
   self.assertEqual('NO_MATCHING_RECORD',probe.evidence['diagnosticAttribution'])
   self.assertNotIn('T'*64,json.dumps(evidence)+json.dumps(probe.evidence))

if __name__=='__main__':unittest.main()
