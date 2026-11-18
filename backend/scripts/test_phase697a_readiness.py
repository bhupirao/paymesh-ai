"""Offline operational behavior tests. No live Ops constructors, credentials, sockets or databases."""
import copy,json,tempfile,unittest,shlex,zipfile
from pathlib import Path
from unittest.mock import Mock,MagicMock,patch
import phase697a_schema as schema
import phase697a_ai_verify as probe

REPO=Path(__file__).resolve().parents[2]
class SchemaReadinessTests(unittest.TestCase):
 def test_exact_inventory_and_checksums(self):
  inventory=schema.migrations(REPO);self.assertEqual(set(range(1,15)),set(inventory))
  rows=[{'version':str(n),'checksum':schema.checksum(p),'success':True} for n,p in sorted(inventory.items()) if n<=11]
  schema.validate_history(json.dumps(rows),REPO,11)
  for key,value in [('checksum',0),('success',False),('version','99')]:
   wrong=copy.deepcopy(rows);wrong[0][key]=value
   with self.assertRaises(schema.Stop):schema.validate_history(json.dumps(wrong),REPO,11)
 def test_line_ending_and_bom_checksum_compatibility(self):
  with tempfile.TemporaryDirectory() as t:
   a=Path(t)/'a';b=Path(t)/'b';a.write_bytes(b'SELECT 1;\n-- comment\n');b.write_bytes(b'\xef\xbb\xbfSELECT 1;\r\n-- comment\r\n')
   self.assertEqual(schema.checksum(a),schema.checksum(b))
 def flags(self,extra=None):
  flags=dict(schema.EXPECTED);flags.update(extra or {});return ['/java','-jar','target/paymesh-backend-0.0.1-SNAPSHOT.jar']+['--'+k+'='+v for k,v in flags.items()]
 def test_flags_pin_new_migrations_and_disable_chat(self):
  result=schema.flags_from(self.flags(),Path('/private-not-read'))
  self.assertEqual('14',result['spring.flyway.target']);self.assertEqual('false',result['paymesh.ai.chat.enabled'])
  self.assertEqual('false',result['paymesh.demo.checkout-controls.enabled'])
 def test_wrong_target_profile_port_and_public_origin_rejected(self):
  for key,value in [('spring.datasource.url','jdbc:postgresql://127.0.0.1:5432/other'),('spring.datasource.username','other'),('server.address','0.0.0.0'),('server.port','9999'),('spring.profiles.active','default'),('paymesh.sessions.origin','https://public.invalid')]:
   with self.subTest(key=key),self.assertRaises(schema.Stop):schema.flags_from(self.flags({key:value}),Path('/not-read'))
 def test_chat_otp_or_checkout_activation_refused(self):
  for key in ('paymesh.ai.chat.enabled','paymesh.demo.password-recovery.enabled','paymesh.demo.checkout-controls.enabled'):
   with self.assertRaises(schema.Stop):schema.flags_from(self.flags({key:'true'}),Path('/not-read'))
 def test_secrets_and_unknown_launch_options_refused(self):
  for item in ('--paymesh.ai.chat.service-token=TEST_ONLY','--spring.datasource.password=TEST_ONLY','--unknown=anything'):
   with self.assertRaises(schema.Stop):schema.flags_from(self.flags()+[item],Path('/not-read'))
 def test_duplicate_flag_refused(self):
  with self.assertRaises(schema.Stop):schema.flags_from(self.flags()+['--server.port=18080'],Path('/not-read'))
 def test_unreviewed_env_stops_before_backup_and_restart(self):
  op=object.__new__(schema.Deployment);op.env={'JAVA_TOOL_OPTIONS':'unreviewed'};op.backup=Mock();op.restart=Mock()
  with self.assertRaises(schema.Stop):op.run()
  op.backup.assert_not_called();op.restart.assert_not_called()
 def test_no_mutation_without_both_operator_confirmations(self):
  source=Path(schema.__file__).read_text()
  self.assertLess(source.index("input('Attest"),source.index('self.backup()'))
  self.assertLess(source.index("input('Approve"),source.index('self.restart(False)'))
  self.assertIn('self.history(11)',source);self.assertIn('self.history(14)',source)
  self.assertIn('self.integrity()!=before',source);self.assertIn('self.unchanged_other_services()',source)
 def test_new_tables_and_financial_fingerprints_are_complete(self):
  self.assertEqual(6,len(schema.TABLES));self.assertEqual(8,len(schema.FINANCIAL))
  self.assertEqual([6,4,4,2,6,4],schema.BASELINE)
 def test_noninteractive_entry_stops_before_constructing_ops(self):
  with patch.object(schema.sys,'argv',['script']),patch.object(schema.sys.stdin,'isatty',return_value=False),patch.object(schema,'Deployment') as construct:
   self.assertEqual(1,schema.main());construct.assert_not_called()

 def test_database_or_baseline_failure_cannot_restart(self):
  for case in ('identity','history','counts','attestation','confirmation','backup-change'):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as t:
    root=Path(t);(root/'.git').mkdir();(root/'.git/index').write_bytes(b'test-index')
    op=object.__new__(schema.Deployment);op.repo=root;op.private=root/'private';op.env={k:'test-only' for k in ('PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN')};op.evidence={};op.backup=Mock();op.restart=Mock();op.launch=Mock()
    op.command=Mock(return_value='PostgreSQL 16.3');op.service=Mock(return_value={'pid':'123'})
    op.history=Mock(side_effect=schema.Stop('History differs') if case=='history' else None)
    op.counts=Mock(return_value=[7,4,4,2,6,4] if case=='counts' else schema.BASELINE)
    op.integrity=Mock(side_effect=[{'payments':'before'},{'payments':'changed'}] if case=='backup-change' else None,return_value={'payments':'before'})
    op.http_json=Mock(return_value=(200,{'localDemoEnabled':False}))
    def sql(query):
     if query.startswith('SELECT current_database'):return 'wrong' if case=='identity' else 'paymesh_demo|paymesh_demo_user|127.0.0.1|5432'
     if query=='SHOW server_version_num':return '160011'
     if 'to_regclass' in query:return 't'
     return '0'
    op.sql=Mock(side_effect=sql)
    answers=['NO' if case=='attestation' else schema.PRIVATE,'NO' if case=='confirmation' else schema.CONFIRM]
    with patch.object(schema,'protected'),patch.object(schema,'hidden',return_value='test-only'),patch('builtins.input',side_effect=answers):
     with self.assertRaises(schema.Stop):op.run()
    op.restart.assert_not_called()
    if case!='backup-change':op.backup.assert_not_called()
 def test_existing_python_contract_literals_match_java(self):
  import ast
  contract=json.loads((REPO/'backend/src/main/resources/ai-chat/contract.json').read_text())
  tree=ast.parse((REPO/'ai-service/app/services/chat_service.py').read_text())
  values={}
  for node in tree.body:
   if isinstance(node,ast.Assign):
    for target in node.targets:
     if isinstance(target,ast.Name) and target.id in ('POLICIES','LIMITS','FOLLOW'):values[target.id]=ast.literal_eval(node.value)
  self.assertEqual(contract['policies'],{k:list(v) for k,v in values['POLICIES'].items()})
  self.assertEqual(contract['limitations'],values['LIMITS'])
  self.assertEqual(contract['followUps'],values['FOLLOW'])

 def test_exact_main_classpath_resource_preserved(self):
  argv=self.flags({'spring.config.location':'classpath:/application.properties'})
  with patch.object(schema,'protected') as guard:
   flags=schema.flags_from(argv,Path('/private-not-read'))
  self.assertEqual('classpath:/application.properties',flags['spring.config.location']);guard.assert_not_called()
  for key,value in schema.EXPECTED.items():self.assertEqual(value,flags[key])
 def test_other_classpath_resources_rejected(self):
  for value in ('classpath:application.properties','classpath:/other.properties','classpath:/application.yml','classpath*:/application.properties','optional:classpath:/application.properties','classpath:/application.properties/','classpath:/application.properties?x=1'):
   with self.subTest(value=value),self.assertRaises(schema.Stop):
    schema.flags_from(self.flags({'spring.config.location':value}),Path('/private-not-read'))
 def test_unexpected_mixed_or_additional_classpath_rejected(self):
  for key,value in [('spring.config.location','classpath:/application.properties,file:/not-read.properties'),('spring.config.location','file:/not-read.properties,classpath:/application.properties'),('spring.config.location','classpath:/application.properties,classpath:/other.properties'),('spring.config.location','classpath:/application.properties,'),('spring.config.additional-location','classpath:/application.properties')]:
   with self.subTest(key=key,value=value),self.assertRaises(schema.Stop):
    schema.flags_from(self.flags({key:value}),Path('/private-not-read'))
 def test_seven_protected_file_locations_accepted_unchanged(self):
  with tempfile.TemporaryDirectory() as t:
   private=Path(t).resolve();private.chmod(0o700);files=[]
   for n in range(7):
    p=private/('reviewed-'+str(n)+'.properties');p.write_text('# synthetic test configuration\n');p.chmod(0o600);files.append(p)
   locations=','.join('file:'+str(p) for p in files)
   result=schema.flags_from(self.flags({'spring.config.location':'classpath:/application.properties','spring.config.additional-location':locations}),private)
   self.assertEqual(locations,result['spring.config.additional-location'])
   # Existing protected file-only main configuration remains supported.
   result=schema.flags_from(self.flags({'spring.config.location':'file:'+str(files[0])}),private)
   self.assertEqual('file:'+str(files[0]),result['spring.config.location'])
 def test_relative_external_and_symlink_file_locations_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();private=root/'private';private.mkdir(mode=0o700)
   external=root/'outside.properties';external.write_text('# synthetic');external.chmod(0o600)
   link=private/'escape.properties';link.symlink_to(external)
   for key in ('spring.config.location','spring.config.additional-location'):
    for value in ('file:relative.properties','file:'+str(external),'file:'+str(link),'file:'+str(private/'..'/'outside.properties')):
     with self.subTest(key=key,value=value),self.assertRaises(schema.Stop):
      schema.flags_from(self.flags({key:value}),private)
 def test_file_owner_permissions_and_symlink_checks_remain(self):
  with tempfile.TemporaryDirectory() as t:
   private=Path(t).resolve();p=private/'config.properties';p.write_text('# synthetic');p.chmod(0o644)
   with self.assertRaises(schema.Stop):schema.flags_from(self.flags({'spring.config.additional-location':'file:'+str(p)}),private)
   p.chmod(0o600);link=private/'link.properties';link.symlink_to(p)
   with self.assertRaises(schema.Stop):schema.flags_from(self.flags({'spring.config.additional-location':'file:'+str(link)}),private)
   with patch('phase673_otp_ops.os.getuid',return_value=p.stat().st_uid+1),self.assertRaises(schema.Stop):
    schema.flags_from(self.flags({'spring.config.additional-location':'file:'+str(p)}),private)

 def test_unexpected_mixed_configuration_locations_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   private=Path(t).resolve();p=private/'config.properties';p.write_text('# synthetic');p.chmod(0o600)
   reviewed='file:'+str(p)
   for key,value in (
    ('spring.config.location','classpath:/application.properties,'+reviewed),
    ('spring.config.location',reviewed+',classpath:/other.properties'),
    ('spring.config.additional-location',reviewed+',classpath:/application.properties'),
    ('spring.config.additional-location',reviewed+',https://example.invalid/config.properties'),
    ('spring.config.additional-location',reviewed+',file:relative.properties')):
    with self.subTest(key=key,value=value),self.assertRaises(schema.Stop):
     schema.flags_from(self.flags({key:value}),private)
 def test_launch_requires_packaged_classpath_resource_before_activation(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();folder=root/'backend/src/main/resources/db/migration';folder.mkdir(parents=True)
   sources=schema.migrations(REPO)
   for p in sources.values():(folder/p.name).write_bytes(p.read_bytes())
   jar=root/'backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar';jar.parent.mkdir()
   def package(include):
    with zipfile.ZipFile(jar,'w') as archive:
     if include:archive.writestr('BOOT-INF/classes/application.properties','# synthetic')
     for p in sources.values():archive.writestr('BOOT-INF/classes/db/migration/'+p.name,p.read_bytes())
     for name in ('chat/AiChatClient','chat/conversations/ConversationController','chat/conversations/ConversationService','security/accounts/ConversationRetention'):
      archive.writestr('BOOT-INF/classes/com/paymesh/backend/'+name+'.class',b'synthetic test placeholder')
   argv=self.flags({'spring.config.location':'classpath:/application.properties'});argv[2]=str(jar)
   op=object.__new__(schema.Deployment);op.repo=root;op.private=root/'private';op.services={'java':{'pid':'123'}};op.command=Mock(return_value=shlex.join(argv));op.evidence={}
   package(False)
   with self.assertRaisesRegex(schema.Stop,'classpath application.properties missing'):op.launch()
   package(True);op.launch()
   self.assertEqual('classpath:/application.properties',op.flags['spring.config.location'])

class VerificationPreparationTests(unittest.TestCase):
 def operation(self):
  op=object.__new__(probe.Verification);op.http=MagicMock();op.evidence={};op.token=op.cookie=None;return op
 def test_health_does_not_claim_model_connectivity(self):
  op=self.operation();op.call=Mock(side_effect=[(200,{'status':'UP'},None),(200,{'status':'UP'},None),(200,{'status':'ok'},None),(200,{},None),(200,{},None),(200,{},None),(200,{'localDemoEnabled':False},None)])
  op.health();self.assertTrue(op.evidence['healthOnlyNotInference']);self.assertEqual(7,op.call.call_count)
 def test_health_rejects_otp_enabled(self):
  op=self.operation();op.call=Mock(side_effect=[(200,{'status':'UP'},None)]*6+[(200,{'localDemoEnabled':True},None)])
  with self.assertRaises(probe.Stop):op.health()
 def test_valid_mode_combinations_are_honest(self):
  self.assertTrue(probe.safe_generation({'analysisMode':'RAG_LLM','generationStatus':'SUCCEEDED','knowledgeReferences':[{'documentId':'PM-KB-IDEMPOTENCY'}]})['actualInferenceProven'])
  for generation in ('TIMEOUT','UNAVAILABLE','VALIDATION_FAILED'):
   self.assertFalse(probe.safe_generation({'analysisMode':'RAG_ASSISTED','generationStatus':generation,'knowledgeReferences':[{'documentId':'PM-KB-IDEMPOTENCY'}]})['actualInferenceProven'])
  with self.assertRaises(probe.Stop):probe.safe_generation({'analysisMode':'RAG_LLM','generationStatus':'TIMEOUT'})
 def test_arbitrary_urls_paths_and_secret_destinations_rejected(self):
  op=self.operation()
  for service,path in [('frontend','http://evil.invalid'),('python','/sql'),('java','/api/v1/chat'),('llm','/v1/chat/completions')]:
   with self.assertRaises(probe.Stop):op.call(service,path)
  with self.assertRaises(probe.Stop):op.call('frontend','/admin/ai',key='TEST_ONLY')
  with self.assertRaises(probe.Stop):op.call('python','/api/v1/chat',token='TEST_ONLY')
  op.http.open.assert_not_called()
 def test_http_upstream_and_browser_credential_boundaries(self):
  op=self.operation();response=Mock(status=200);response.read.return_value=b'{}';response.headers.get.return_value=None
  op.http.open.return_value.__enter__.return_value=response
  op.call('python','/api/v1/chat',{'question':'synthetic'},key='TEST_ONLY')
  req=op.http.open.call_args.args[0];self.assertEqual('http://127.0.0.1:8000/api/v1/chat',req.full_url)
  self.assertEqual('TEST_ONLY',req.headers['X-paymesh-ai-chat-token']);self.assertNotIn('Authorization',req.headers);self.assertNotIn('Cookie',req.headers)
 def test_internal_auth_requires_wrong_key_rejection_then_correlation(self):
  op=self.operation()
  def call(service,path,body=None,**kw):
   if op.call.call_count==1:return 401,{},None
   return 200,{'correlationId':body['correlationId'],'analysisMode':'RAG_LLM','generationStatus':'SUCCEEDED','knowledgeReferences':[{'documentId':'PM-KB-IDEMPOTENCY'}]},None
  op.call=Mock(side_effect=call)
  with patch.object(probe,'hidden',return_value='T'*64):op.internal()
  self.assertTrue(op.evidence['internalAuthenticationVerified']);self.assertNotEqual(op.call.call_args_list[0].kwargs['key'],op.call.call_args_list[1].kwargs['key'])
 def test_internal_fallback_does_not_pass_inference(self):
  op=self.operation()
  op.call=Mock(side_effect=lambda *a,**k:(401,{},None) if op.call.call_count==1 else (200,{'correlationId':a[2]['correlationId'],'analysisMode':'RAG_ASSISTED','generationStatus':'TIMEOUT','knowledgeReferences':[{'documentId':'PM-KB-IDEMPOTENCY'}]},None))
  with patch.object(probe,'hidden',return_value='T'*64),self.assertRaises(probe.Stop):op.internal()
  self.assertFalse(op.evidence['generation']['actualInferenceProven'])
 def test_enable_stages_matching_secrets_without_restarts(self):
  with tempfile.TemporaryDirectory() as t:
   op=self.operation();op.run_dir=Path(t)
   with patch('builtins.input',return_value='NO_PUBLIC_PROXY_OR_TUNNEL'),patch.object(probe,'hidden',return_value='T'*64):op.stage_config(True)
   java=Path(t,'java-chat.properties');python=Path(t,'python-chat.env')
   self.assertIn('service-token='+'T'*64,java.read_text());self.assertIn('SERVICE_TOKEN='+'T'*64,python.read_text())
   self.assertEqual(0o600,java.stat().st_mode&0o777);self.assertEqual(0o600,python.stat().st_mode&0o777)
   self.assertNotIn('T'*64,json.dumps(op.evidence));self.assertFalse(op.evidence['serviceRestartsPerformed'])
 def test_disable_does_not_read_key_or_delete_old_config(self):
  with tempfile.TemporaryDirectory() as t:
   op=self.operation();op.run_dir=Path(t)
   with patch('builtins.input',return_value='NO_PUBLIC_PROXY_OR_TUNNEL'),patch.object(probe,'hidden') as key:op.stage_config(False);key.assert_not_called()
   self.assertIn('paymesh.ai.chat.enabled=false',Path(t,'java-chat.properties').read_text())
 def test_stage_rejects_unattested_or_invalid_credentials(self):
  op=self.operation()
  with patch('builtins.input',return_value='NO'),self.assertRaises(probe.Stop):op.stage_config(True)
  with patch('builtins.input',return_value='NO_PUBLIC_PROXY_OR_TUNNEL'),patch.object(probe,'hidden',return_value='short'),self.assertRaises(probe.Stop):op.stage_config(True)
 def test_templates_fail_closed_and_use_correct_llm_port(self):
  java=(REPO/'backend/phase697-ai.properties.example').read_text();python=(REPO/'ai-service/phase697-chat.env.example').read_text()
  self.assertIn('paymesh.ai.chat.enabled=false',java);self.assertIn('PAYMESH_AI_CHAT_API_ENABLED=false',python)
  self.assertIn('127.0.0.1:8082/v1/chat/completions',python);self.assertIn('PAYMESH_AI_CHAT_SERVICE_TOKEN=\n',python)
if __name__=='__main__':unittest.main()
