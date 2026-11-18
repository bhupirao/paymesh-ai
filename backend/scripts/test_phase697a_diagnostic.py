"""Synthetic binary/process/HTTP fixtures only. Never inspect live processes or secrets."""
import ctypes
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4
import phase697a_process as p
import phase697a_diagnostic as d
import phase697a_ai_verify as v
from phase673_otp_ops import Stop

CID='8d447340-43f2-4a84-a1a9-83f5af5b2694'
OTHER='b86c2b66-776d-4f42-b7ec-9f87727ef941'
def blob(argv=('python','-m','uvicorn'),entries=(b'KEY=value',)):
 return struct.pack('=i',len(argv))+b'/reviewed/python\0\0\0'+b''.join(a.encode()+b'\0' for a in argv)+b''.join(x+b'\0' for x in entries)+b'\0\0'
def row(cid=CID,reason='INVALID_JSON'):
 return json.dumps({'correlationId':cid,'reasonCode':reason}).encode()+b'\n'

class BinaryProcessTests(unittest.TestCase):
 def test_whitespace_equals_and_unicode_values_are_preserved(self):
  raw=blob(entries=(b'KEY= value with spaces\tand\nnewlines=a=b ', 'LABEL=₹ test'.encode(),b'EMPTY='))
  exe,args,env=p.parse_arguments(raw)
  self.assertEqual('/reviewed/python',exe);self.assertEqual(('python','-m','uvicorn'),args)
  self.assertEqual(' value with spaces\tand\nnewlines=a=b ',env['KEY']);self.assertEqual('₹ test',env['LABEL']);self.assertEqual('',env['EMPTY'])
 def test_argv_whitespace_and_empty_argument(self):
  self.assertEqual(('python','a b',''),p.parse_arguments(blob(argv=('python','a b','')))[1])
 def test_duplicate_environment_rejected(self):
  with self.assertRaises(Stop):p.parse_arguments(blob(entries=(b'TOKEN=a',b'TOKEN=b')))
 def test_malformed_environment_never_leaks_values(self):
  for entry in (b'NO_EQUALS_SECRET',b'1BAD=SECRET',b'=SECRET',b'KEY=\xffSECRET'):
   with self.subTest(entry=entry),self.assertRaises(Stop) as error:p.parse_arguments(blob(entries=(entry,)))
   self.assertNotIn('SECRET',str(error.exception))
 def test_truncated_oversized_or_invalid_layout_fails_closed(self):
  for raw in (b'',b'x'*4,blob()[:-3],struct.pack('=i',0)+b'bad\0',b'x'*(p.MAX_BYTES+1),blob()+b'bad\0'):
   with self.subTest(size=len(raw)),self.assertRaises(Stop):p.parse_arguments(raw)
 def test_wrong_argc_rejected(self):
  raw=blob();raw=struct.pack('=i',99)+raw[4:]
  with self.assertRaises(Stop):p.parse_arguments(raw)
 def test_identity_change_during_read_rejected_including_same_second_reuse(self):
  native=Mock();native.arguments.return_value=blob();native.identity.side_effect=[(123,100,1,os.getuid()),(123,100,2,os.getuid())]
  with self.assertRaises(Stop):p.snapshot(123,native)
 def test_stable_identity_read_and_pre_inference_fence(self):
  native=Mock();native.arguments.return_value=blob();native.identity.return_value=(123,100,2,os.getuid())
  snap=p.snapshot(123,native);p.assert_same(snap,native)
  self.assertEqual({'KEY':'value'},snap.environment);self.assertNotIn('value',repr(snap))
  native.identity.return_value=(123,101,0,os.getuid())
  with self.assertRaises(Stop):p.assert_same(snap,native)
 def test_unavailable_native_reader_fail_closed(self):
  with patch.object(p.sys,'platform','unsupported'),self.assertRaises(Stop):p.snapshot(123)
 def test_reviewed_native_struct_layout(self):self.assertEqual(136,ctypes.sizeof(p.BSDInfo))
 def test_missing_native_environment_fails(self):
  native=Mock();native.identity.return_value=(123,100,1,os.getuid());native.arguments.side_effect=Stop('Native process environment unavailable.')
  with self.assertRaises(Stop):p.snapshot(123,native)

class AppleAuxiliaryLayoutTests(unittest.TestCase):
 @staticmethod
 def tail():
  # Entirely synthetic values, matching seven retained auxiliary keys observed
  # live. libpthread has erased three value strings into NUL runs.
  tail = (b'ptr_munge=\0'+b'\0'*18+b'main_stack=\0'+b'\0'*70+
   b'executable_file=0x'+b'1'*11+b',0x'+b'2'*11+b'\0dyld_file=0x'+b'3'*10+b',0x'+b'4'*10+b'\0'+
   b'executable_cdhash='+b'a'*40+b'\0executable_boothash='+b'b'*40+
   b'\0th_port=\0'+b'\0'*10)
  return tail+b'\0'*(413-len(tail))
 def test_observed_nine_argv_twelve_env_and_zeroed_apple_values(self):
  argv=('python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log')
  entries=tuple(('KEY'+str(i)+'= value with spaces\tand=a=b ').encode() for i in range(12))
  suffix=b'\0\0'+self.tail()
  self.assertEqual(415,len(suffix));self.assertEqual(225,sum(b!=0 for b in suffix))
  raw=blob(argv,entries)+self.tail()
  exe,actual,env=p.parse_arguments(raw)
  self.assertEqual(argv,actual);self.assertEqual(12,len(env))
  self.assertTrue(all(v==' value with spaces\tand=a=b ' for v in env.values()))
  self.assertFalse(set(env) & {key.decode() for key in p._AUXILIARY})
 def test_explicit_relative_execve_path(self):
  raw=blob().replace(b'/reviewed/python',b'./build/bin/llama-server',1)+self.tail()
  self.assertEqual('./build/bin/llama-server',p.parse_arguments(raw)[0])
 def test_ambiguous_or_traversing_execve_paths_rejected(self):
  for path in (b'python',b'../python',b'./../python',b'./bin/../python',b'./',b'./bin//python'):
   with self.subTest(path=path),self.assertRaises(Stop):p.parse_arguments(blob().replace(b'/reviewed/python',path,1))
 def test_relative_execve_path_can_contain_spaces(self):
  raw=blob().replace(b'/reviewed/python',b'./directory with spaces/python',1)
  self.assertEqual('./directory with spaces/python',p.parse_arguments(raw)[0])
 def test_documented_nonzero_auxiliary_values(self):
  suffix=(b'ptr_munge=0x123\0main_stack=0x1,0x2,0x3,0x4\0'
          b'executable_file=0x1,0x2\0dyld_file=0x3,0x4\0'
          b'executable_cdhash='+b'a'*40+b'\0executable_boothash='+b'b'*40+b'\0th_port=0x123\0')
  self.assertEqual({'KEY':'value'},p.parse_arguments(blob()+suffix)[2])
 def test_unknown_trailing_bytes_not_ignored(self):
  for tail in (b'unknown=0x1\0',b'arbitrary bytes\0',b'\xff\0',b'\0junk'):
   with self.subTest(tail=tail),self.assertRaises(Stop):p.parse_arguments(blob()+tail)
 def test_additional_environment_after_boundary_rejected(self):
  with self.assertRaises(Stop):p.parse_arguments(blob()+self.tail()+b'PAYMESH_AI_CHAT_SERVICE_TOKEN=SYNTHETIC\0')
 def test_duplicate_auxiliary_key_rejected(self):
  with self.assertRaises(Stop):p.parse_arguments(blob()+self.tail()+b'ptr_munge=\0')
 def test_malformed_shapes_rejected(self):
  for field in (b'ptr_munge=untrusted',b'main_stack=0x1,0x2',b'executable_file=0x1',b'dyld_file=',b'executable_cdhash=aa',b'executable_boothash=zz',b'th_port=0x123456789',b'executable_file=0x'+b'1'*17+b',0x2'):
   with self.subTest(field=field),self.assertRaises(Stop):p.parse_arguments(blob()+field+b'\0')
 def test_unterminated_tail_rejected(self):
  with self.assertRaises(Stop):p.parse_arguments(blob()+self.tail().rstrip(b'\0'))
 def test_auxiliary_without_environment_boundary_is_ambiguous(self):
  base=blob().rstrip(b'\0')+b'\0'
  with self.assertRaises(Stop):p.parse_arguments(base+b'ptr_munge=0x1\0\0')
 def test_missing_environment_terminator_rejected(self):
  with self.assertRaises(Stop):p.parse_arguments(blob().rstrip(b'\0')+b'\0')
 def test_malformed_environment_before_valid_auxiliary_rejected(self):
  for entry in (b'KEY=a',b'1INVALID=SYNTHETIC'):
   entries=(entry,entry)
   with self.assertRaises(Stop):p.parse_arguments(blob(entries=entries)+self.tail())
 def test_only_zero_padding_still_accepted(self):
  self.assertEqual({'KEY':'value'},p.parse_arguments(blob()+b'\0'*200)[2])
 def test_auxiliary_cannot_override_environment_credentials(self):
  with self.assertRaises(Stop):p.parse_arguments(blob(entries=(b'TOKEN=ORIGINAL',))+b'TOKEN=OVERRIDE\0')

class NativeAdapterTests(unittest.TestCase):
 def test_proc_identity_requires_exact_kernel_struct_and_owner(self):
  native=object.__new__(p.MacOS);native.libproc=Mock()
  def fill(pid,flavor,arg,pointer,size):
   self.assertEqual(3,flavor);pointer._obj.pid=pid;pointer._obj.uid=os.getuid();pointer._obj.start_sec=100;pointer._obj.start_usec=123
   return size
  native.libproc.proc_pidinfo.side_effect=fill
  self.assertEqual((55,100,123,os.getuid()),native.identity(55))
  native.libproc.proc_pidinfo.side_effect=None;native.libproc.proc_pidinfo.return_value=0
  with self.assertRaises(Stop):native.identity(55)
 def test_native_argument_read_preserves_binary_data(self):
  native=object.__new__(p.MacOS);native.libc=Mock();raw=blob(entries=(b'SPACE=a b',))
  def read(mib,length,buf,size,new,newlen):
   self.assertEqual([1,49,55],list(mib));self.assertEqual(3,length)
   size._obj.value=len(raw)
   if buf is not None:ctypes.memmove(buf,raw,len(raw))
   return 0
  native.libc.sysctl.side_effect=read
  self.assertEqual(raw,native.arguments(55));self.assertEqual(2,native.libc.sysctl.call_count)
 def test_native_unavailable_does_not_fall_back_to_ps(self):
  native=object.__new__(p.MacOS);native.libc=Mock();native.libc.sysctl.return_value=-1
  with self.assertRaises(Stop):native.arguments(55)
  self.assertEqual(1,native.libc.sysctl.call_count)

class CorrelationTests(unittest.TestCase):
 def test_valid_correlated_reason(self):self.assertEqual('INVALID_JSON',d.matching_reason(row(),CID))
 def test_concurrent_unrelated_records_are_not_attributed(self):
  self.assertIsNone(d.matching_reason(row(OTHER),CID))
  self.assertEqual('INVALID_JSON',d.matching_reason(row(OTHER,'INVALID_VARIANT')+row(),CID))
 def test_missing_correlation_rejected(self):
  with self.assertRaises(Stop):d.matching_reason(b'{"reasonCode":"INVALID_JSON"}\n',CID)
 def test_duplicate_correlation_rejected(self):
  for raw in (row()+row(),row(OTHER)+row(OTHER)):
   with self.assertRaises(Stop):d.matching_reason(raw,CID)
 def test_duplicate_json_keys_rejected(self):
  with self.assertRaises(Stop):d.matching_reason(b'{"correlationId":"'+CID.encode()+b'","correlationId":"'+CID.encode()+b'","reasonCode":"INVALID_JSON"}',CID)
 def test_invalid_correlation_rejected(self):
  for value in (None,'',CID.upper(),'x'*100,123,'00000000-0000-0000-0000-000000000000'):
   with self.subTest(value=value),self.assertRaises(Stop):d.matching_reason(row(value),CID)
 def test_unrecognized_reason_extra_fields_and_broken_json_rejected(self):
  for raw in (row(reason='SECRET'),b'invalid',json.dumps({'correlationId':CID,'reasonCode':'INVALID_JSON','text':'SECRET'}).encode()):
   with self.assertRaises(Stop) as error:d.matching_reason(raw,CID)
   self.assertNotIn('SECRET',str(error.exception))
 def test_no_diagnostic_is_not_a_claim_of_success(self):self.assertIsNone(d.matching_reason(b'',CID))
 def test_oversized_evidence_rejected(self):
  with self.assertRaises(Stop):d.matching_reason(b'x'*(d.MAX_BYTES+1),CID)
 def test_sink_read_protection(self):
  with tempfile.TemporaryDirectory() as t:
   private=Path(t);private.chmod(0o700);folder=private/'run';folder.mkdir(mode=0o700);target=folder/'chat-validation-diagnostics.jsonl';target.touch(mode=0o600);target.write_bytes(row())
   identity,raw=d.read_sink(target,private);self.assertEqual(row(),raw)
   target.chmod(0o644)
   with self.assertRaises(Stop):d.read_sink(target,private)
 def test_symlink_and_hardlink_rejected(self):
  for kind in ('symlink','hardlink'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as t:
    private=Path(t);private.chmod(0o700);target=private/'chat-validation-diagnostics.jsonl';other=private/'original';other.touch(mode=0o600)
    if kind=='symlink':target.symlink_to(other)
    else:os.link(other,target)
    with self.assertRaises(Stop):d.read_sink(target,private)

class RequestTests(unittest.TestCase):
 def op(self,status='SUCCEEDED'):
  op=object.__new__(v.Verification);op.evidence={}
  def call(service,path,body,**kw):
   if op.call.call_count==1:return 401,{},None
   return 200,{'correlationId':body['correlationId'],'analysisMode':'RAG_LLM' if status=='SUCCEEDED' else 'RAG_ASSISTED','generationStatus':status,'knowledgeReferences':[{}]},None
  op.call=Mock(side_effect=call);return op
 def test_exactly_one_authenticated_synthetic_attempt_no_retry(self):
  op=self.op()
  with patch.object(v,'hidden') as hidden:op.internal(CID,'T'*64)
  hidden.assert_not_called();self.assertEqual(2,op.call.call_count)
  correct=[c for c in op.call.call_args_list if c.kwargs['key']=='T'*64];self.assertEqual(1,len(correct))
  body=correct[0].args[2];self.assertEqual(CID,body['correlationId']);self.assertEqual([],body['history']);self.assertNotIn('evidence',body)
  self.assertNotIn('T'*64,json.dumps(op.evidence))
 def test_timeout_or_fallback_never_retries(self):
  for status in ('TIMEOUT','VALIDATION_FAILED','UNAVAILABLE'):
   op=self.op(status)
   with self.assertRaises(Stop):op.internal(CID,'T'*64)
   self.assertEqual(2,op.call.call_count)
 def test_missing_credentials_no_requests(self):
  op=self.op()
  with self.assertRaises(Stop):op.internal(CID,'')
  op.call.assert_not_called()
 def test_wrong_response_correlation_rejected(self):
  op=self.op();op.call.side_effect=[(401,{},None),(200,{'correlationId':OTHER},None)]
  with self.assertRaises(Stop):op.internal(CID,'T'*64)
  self.assertEqual(2,op.call.call_count)
 def test_bad_auth_negative_probe_prevents_inference(self):
  op=self.op();op.call.side_effect=None;op.call.return_value=(200,{},None)
  with self.assertRaises(Stop):op.internal(CID,'T'*64)
  self.assertEqual(1,op.call.call_count)
 def test_invalid_request_correlation_no_call(self):
  for cid in ('invalid',''):
   op=self.op()
   with self.assertRaises(Stop):op.internal(cid,'T'*64)
   op.call.assert_not_called()

class CredentialsTests(unittest.TestCase):
 def case(self,change=None):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);private=Path(t.name);private.chmod(0o700)
  config=private/'settings with spaces.properties';config.touch(mode=0o600)
  config.write_text('paymesh.ai.chat.enabled=true\npaymesh.ai.chat.service-token='+'T'*64+'\npaymesh.demo.password-recovery.enabled=false\npaymesh.demo.checkout-controls.enabled=false\n')
  diagnostic=private/'chat-validation-diagnostics.jsonl'
  env={'PAYMESH_AI_ANALYSIS_MODE':'RAG_LLM','PAYMESH_AI_CHAT_API_ENABLED':'true','PAYMESH_AI_GENERATION_ENABLED':'true','PAYMESH_AI_INFERENCE_URL':'http://127.0.0.1:8082/v1/chat/completions','PAYMESH_AI_MODEL_NAME':'paymesh-qwen','PAYMESH_AI_GENERATION_TIMEOUT':'30','PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE':str(diagnostic),'PAYMESH_AI_CHAT_SERVICE_TOKEN':'T'*64,'EXTRA':' value with spaces\tand=a=b '}
  ai=p.Snapshot((1,10,1,os.getuid()),'/python',('python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log'),env)
  java=p.Snapshot((2,10,1,os.getuid()),'/java',('java','-jar','artifact.jar','--spring.config.location=classpath:/application.properties','--spring.config.additional-location=file:'+str(config)),{})
  return ai,java,private,diagnostic,config
 def test_credentials_match_without_altering_whitespace_values(self):
  ai,java,private,diagnostic,_=self.case();before=dict(ai.environment)
  self.assertEqual('T'*64,d.credentials(ai,java,private,diagnostic));self.assertEqual(before,ai.environment)
 def test_missing_or_wrong_credentials(self):
  for token in ('','X'*64):
   ai,java,private,diagnostic,_=self.case();ai.environment['PAYMESH_AI_CHAT_SERVICE_TOKEN']=token
   with self.assertRaises(Stop):d.credentials(ai,java,private,diagnostic)
 def test_disabled_access_logging_required(self):
  ai,java,private,diagnostic,_=self.case();ai.argv=ai.argv[:-1]
  with self.assertRaises(Stop):d.credentials(ai,java,private,diagnostic)
 def test_configuration_public_location_refused(self):
  ai,java,private,diagnostic,_=self.case();java.argv=java.argv[:-1]+('--spring.config.additional-location=file:/tmp/public-settings.properties',)
  with self.assertRaises(Stop):d.credentials(ai,java,private,diagnostic)
 def test_otp_checkout_or_changed_generation_rejected(self):
  ai,java,private,diagnostic,config=self.case()
  for prop in ('paymesh.demo.password-recovery.enabled','paymesh.demo.checkout-controls.enabled'):
   original=config.read_text();config.write_text(original.replace(prop+'=false',prop+'=true'))
   with self.assertRaises(Stop):d.credentials(ai,java,private,diagnostic)
   config.write_text(original)
  ai.environment['PAYMESH_AI_GENERATION_TIMEOUT']='999'
  with self.assertRaises(Stop):d.credentials(ai,java,private,diagnostic)
 def test_java_environment_override_fail_closed(self):
  ai,java,private,diagnostic,_=self.case();java.environment['SPRING_APPLICATION_JSON']='SECRET'
  with self.assertRaises(Stop):d.credentials(ai,java,private,diagnostic)

class WorkflowTests(unittest.TestCase):
 def flow(self,status='SUCCEEDED',records='unrelated',stale=False,missing_baseline=False):
  import hashlib
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);private=root/'private';private.mkdir(mode=0o700);folder=private/'activation';folder.mkdir(mode=0o700)
   hashes={}
   for name in d.SOURCE_FILES:
    f=root/'ai-service'/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('synthetic source');hashes[name]=hashlib.sha256(f.read_bytes()).hexdigest()
   sink=folder/'chat-validation-diagnostics.jsonl';sink.touch(mode=0o600)
   identities={k:{'pid':str(n),'start':'synthetic'} for n,k in enumerate(('ai','java','llm','frontend'),100)}
   evidence=folder/'evidence.json';evidence.touch(mode=0o600);evidence.write_text(json.dumps({'success':True,'diagnosticsEnabled':True,'beforeServices':identities,'newPythonIdentity':identities['ai'],'sourceHashes':hashes,'nativeProcessIdentities':{k:[100,100,1,os.getuid()] for k in ('ai','java','llm')},'diagnosticFile':str(sink)}))
   if missing_baseline:
    data=json.loads(evidence.read_text());data.pop('nativeProcessIdentities');evidence.write_text(json.dumps(data))
   op=object.__new__(v.Verification);op.services=identities;op.private=private;op.repo=root;op.evidence={};op.services_checked=Mock()
   def call(service,path,body,**kw):
    if op.call.call_count==1:return 401,{},None
    cid=body['correlationId']
    raw=row(OTHER)
    if records in ('matching','contradictory'):raw+=json.dumps({'correlationId':cid,'reasonCode':'INVALID_VARIANT','schemaFailureCode':'ENUM_VALUE_INVALID'}).encode()+b'\n'
    elif records=='duplicate':raw+=row(cid)+row(cid)
    elif records=='none':raw=b''
    sink.write_bytes(raw)
    return 200,{'correlationId':cid,'analysisMode':'RAG_LLM' if status=='SUCCEEDED' else 'RAG_ASSISTED','generationStatus':status,'knowledgeReferences':[{}]},None
   op.call=Mock(side_effect=call)
   fake_snapshot=p.Snapshot((100,100,1,os.getuid()),'/python',(),{})
   with patch('builtins.input',return_value=str(evidence)),patch.object(d,'MacOS'),patch.object(d,'snapshot',return_value=fake_snapshot),patch.object(d,'credentials',return_value='T'*64),patch.object(d,'assert_same',side_effect=Stop('Process changed.') if stale else None):
    if status!='SUCCEEDED' or records in ('duplicate','contradictory') or stale or missing_baseline:
     with self.assertRaises(Stop):d.run(op)
    else:d.run(op)
   if stale or missing_baseline:op.call.assert_not_called();return
   self.assertEqual(2,op.call.call_count)
   self.assertTrue(d.correlation(op.evidence['diagnosticCorrelationId']))
   self.assertNotIn('T'*64,json.dumps(op.evidence))
   if records=='matching':self.assertEqual('INVALID_VARIANT',op.evidence['diagnosticReasonCode']);self.assertEqual('MATCHED_REQUEST',op.evidence['diagnosticAttribution'])
   elif records in ('unrelated','none'):self.assertIsNone(op.evidence['diagnosticReasonCode']);self.assertEqual('NO_MATCHING_RECORD',op.evidence['diagnosticAttribution'])
 def test_success_ignores_unrelated_reason(self):self.flow()
 def test_fallback_matches_only_own_reason(self):self.flow('VALIDATION_FAILED','matching')
 def test_duplicate_correlation_fails(self):self.flow(records='duplicate')
 def test_success_with_matching_rejection_record_fails(self):self.flow(records='contradictory')
 def test_no_record_is_explicit(self):self.flow(records='none')
 def test_identity_change_prevents_call(self):self.flow(stale=True)
 def test_missing_microsecond_activation_baseline_prevents_call(self):self.flow(missing_baseline=True)

class SchemaCategoryRecordTests(unittest.TestCase):
 def schema_row(self,cid=CID,code='REQUIRED_FIELD_MISSING',reason='SCHEMA_MISMATCH'):
  return json.dumps({'correlationId':cid,'reasonCode':reason,'schemaFailureCode':code}).encode()+b'\n'
 def test_every_fixed_schema_code_is_accepted(self):
  for code in d.SCHEMA_FAILURE_CODES:
   self.assertEqual(code,d.matching_record(self.schema_row(code=code),CID,True)['schemaFailureCode'])
 def test_unrelated_request_cannot_supply_schema_code(self):
  raw=self.schema_row(OTHER,'EXTRA_FIELD_FORBIDDEN')+self.schema_row(CID,'NESTED_STRUCTURE_INVALID')
  self.assertEqual('NESTED_STRUCTURE_INVALID',d.matching_record(raw,CID,True)['schemaFailureCode'])
  self.assertEqual({},d.matching_record(self.schema_row(OTHER),CID,True))
 def test_matching_schema_record_requires_code_in_strict_mode(self):
  with self.assertRaises(Stop):d.matching_record(row(reason='SCHEMA_MISMATCH'),CID,True)
 def test_historical_coarse_record_remains_readable_without_attribution_upgrade(self):
  result=d.matching_record(row(reason='SCHEMA_MISMATCH'),CID)
  self.assertNotIn('schemaFailureCode',result)
 def test_arbitrary_code_type_or_invalid_coarse_reason_rejected(self):
  for code in ('SECRET',None,[],{},123):
   with self.assertRaises(Stop):d.matching_record(self.schema_row(code=code),CID,True)
  with self.assertRaises(Stop):d.matching_record(self.schema_row(reason='INVALID_JSON'),CID,True)
 def test_duplicate_correlated_schema_records_rejected(self):
  with self.assertRaises(Stop):d.matching_record(self.schema_row()+self.schema_row(),CID,True)
 def test_malformed_record_unknown_fields_or_missing_correlation_rejected(self):
  for data in ({'reasonCode':'SCHEMA_MISMATCH','schemaFailureCode':'REQUIRED_FIELD_MISSING'},
    {'correlationId':CID,'reasonCode':'SCHEMA_MISMATCH','schemaFailureCode':'REQUIRED_FIELD_MISSING','field':'SECRET'}):
   with self.assertRaises(Stop):d.matching_record(json.dumps(data).encode(),CID,True)
 def test_python_writer_and_operational_allowlists_match(self):
  import ast
  tree=ast.parse((Path(__file__).resolve().parents[2]/'ai-service/app/services/chat_validation_diagnostics.py').read_text())
  constants={node.targets[0].id:ast.literal_eval(node.value.args[0]) for node in tree.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('SCHEMA_FAILURE_CODES','SCHEMA_REASONS')}
  self.assertEqual(set(d.SCHEMA_FAILURE_CODES),constants['SCHEMA_FAILURE_CODES'])
  self.assertEqual(set(d.SCHEMA_REASONS),constants['SCHEMA_REASONS'])

if __name__=='__main__':unittest.main()
