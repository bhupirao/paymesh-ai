"""Offline published-artifact regressions. No Docker, network or live data."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_artifact_e2e as r
import capture_failure_diagnostics as diagnostics
ROOT = Path(__file__).resolve().parents[1]


def yaml(path):
    return json.loads(subprocess.check_output(['ruby', '-rjson', '-ryaml', '-e',
                    'puts JSON.generate(YAML.load_file(ARGV[0]))', str(ROOT/path)]))


def env(temp='/tmp'):
    project = 'paymesh-e2e-123-1'
    folder = str(Path(temp).resolve()/project)
    return {'GITHUB_ACTIONS':'true','RUNNER_OS':'Linux','RUNNER_ENVIRONMENT':'github-hosted',
            'GITHUB_REPOSITORY':'bhupirao/paymesh-ai','GITHUB_EVENT_NAME':'workflow_dispatch',
            'GITHUB_REF':'refs/heads/main','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1',
            'E2E_VERIFY_QWEN':'true','RUNNER_TEMP':temp,'E2E_PROJECT':project,
            'E2E_DIR':folder,'E2E_ENV':folder+'/container.env'}


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose=yaml('deploy/compose.release-verify.yaml')
        cls.original=yaml('deploy/compose.yaml')
        cls.workflow=yaml('.github/workflows/release-artifact-e2e.yml')

    def test_exact_release_metadata(self):
        lock=r.release_lock()
        self.assertEqual(lock['reviewedMain'],'c3bb92e971b17da2188e96172b16b7b001ec4ba4')
        expected={'java':'22649c06e406681e4ea699a60ebcf1d537068ec1091b0b72c678a749c792eb2b',
                  'python':'29edd8acb856f9a19067592e9fb384e43ce74a060b1b6dabe04d747f0bfe65ee',
                  'frontend':'388718b672a9b944348a40257a56d212f1a6e4cb6ad372376a4e03ba5b1b2412',
                  'llama':'09a63d5e9312e4126b90cdc927045cbb69a654b66dd722e3823c53d4066bf74e'}
        for name,digest in expected.items():
            self.assertEqual(lock['images'][name],'bhupirao/paymesh-'+name+'@sha256:'+digest)
            self.assertEqual(self.compose['services'][name]['image'],lock['images'][name])

    def test_only_image_and_build_settings_differ(self):
        for name,service in self.original['services'].items():
            expected=copy.deepcopy(service);expected.pop('build',None)
            if name!='postgres':expected['image']=r.release_lock()['images'][name]
            self.assertEqual(self.compose['services'][name],expected)
        for key in ('networks','volumes','secrets'):self.assertEqual(self.compose[key],self.original[key])

    def test_no_build_sections_or_build_dependencies(self):
        self.assertNotIn('build:',(ROOT/r.COMPOSE).read_text())
        self.assertEqual(len(self.compose['services']),5)
        text=(ROOT/'.github/workflows/release-artifact-e2e.yml').read_text()
        for forbidden in ('buildx','login-action','build-push','docker push','docker build','secrets.','environment:','llama-source'):
            self.assertNotIn(forbidden,text)

    def test_manual_only_read_only_and_hosted(self):
        triggers=self.workflow.get('on',self.workflow.get('true'))
        self.assertEqual(triggers,{'workflow_dispatch':None})
        self.assertEqual(self.workflow['permissions'],{'contents':'read'})
        job=self.workflow['jobs']['verify']
        self.assertEqual(job['runs-on'],'ubuntu-24.04');self.assertEqual(job['timeout-minutes'],55)
        self.assertIn("refs/heads/main",job['if'])
        self.assertEqual(job['env']['E2E_VERIFY_QWEN'],'true')
        self.assertFalse(self.workflow['concurrency']['cancel-in-progress'])

    def test_actions_are_exact_allowlisted_sha_pins(self):
        uses=[s['uses'] for s in self.workflow['jobs']['verify']['steps'] if 'uses' in s]
        self.assertEqual(uses,['actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803',
                             'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9',
                             'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'])

    def test_pull_precedes_no_build_start(self):
        steps=self.workflow['jobs']['verify']['steps']
        startup=next(s for s in steps if s.get('id')=='startup')
        for flag in ('--no-build','--pull never','--wait-timeout 240'):self.assertIn(flag,startup['run'])
        self.assertTrue(any(' pull' in s.get('run','') for s in steps[:steps.index(startup)]))

    def test_failure_capture_upload_then_always_cleanup(self):
        steps=self.workflow['jobs']['verify']['steps']
        diagnostic=next(i for i,s in enumerate(steps) if s.get('run','').endswith('.py diagnostics'))
        upload=next(i for i,s in enumerate(steps) if 'uses' in s and 'upload-artifact' in s['uses'])
        cleanup=next(i for i,s in enumerate(steps) if s.get('run','').endswith('.py cleanup'))
        self.assertLess(diagnostic,upload);self.assertLess(upload,cleanup)
        self.assertIn('failure()',steps[diagnostic]['if'])
        self.assertIn('always()',steps[upload]['if']);self.assertIn('always()',steps[cleanup]['if'])
        paths=steps[upload]['with']['path']
        self.assertNotIn('container.env',paths);self.assertNotIn('secrets',paths)
        self.assertEqual(steps[upload]['with']['retention-days'],3)

    def test_model_is_runner_only_checksum_verified_no_retries(self):
        text=(ROOT/'.github/workflows/release-artifact-e2e.yml').read_text()
        self.assertIn('74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db',text)
        self.assertIn('--max-filesize 550000000',text);self.assertNotIn('--retry',text)


class RuntimeGuardTests(unittest.TestCase):
    def test_valid_hosted_guard(self):
        with patch.dict(os.environ,env(),clear=True):self.assertEqual(r.guard(),'paymesh-e2e-123-1')

    def test_wrong_host_context_and_fallback_rejected(self):
        for key,value in [('RUNNER_ENVIRONMENT','self-hosted'),('GITHUB_REPOSITORY','other/repo'),
                          ('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF','refs/heads/other'),
                          ('E2E_VERIFY_QWEN','false'),('DOCKER_HOST','tcp://remote:2375')]:
            with self.subTest(key=key),patch.dict(os.environ,{**env(),key:value},clear=True):
                with self.assertRaises(r.Failure if key!='DOCKER_HOST' else RuntimeError):r.guard()

    def test_release_compose_selected_only(self):
        with patch.dict(os.environ,env(),clear=True):suite=r.ReleaseSuite()
        self.assertEqual(suite.compose[-1],r.COMPOSE);self.assertTrue(suite.verify_qwen)

    def test_foreign_fixture_path_rejected(self):
        with patch.dict(os.environ,{**env(),'E2E_ENV':'/private/config'},clear=True):
            with self.assertRaises(r.Failure):r.ReleaseSuite()

    def test_teardown_delegates_only_validated_project(self):
        with patch.dict(os.environ,env(),clear=True),patch.object(r,'cleanup_project',return_value=0) as call:
            self.assertEqual(r.main('cleanup'),0)
        call.assert_called_once_with('paymesh-e2e-123-1',Path('/tmp').resolve()/'paymesh-e2e-123-1')

    def test_teardown_foreign_project_never_executes(self):
        with patch.dict(os.environ,{**env(),'E2E_PROJECT':'real-db'},clear=True),patch('subprocess.run') as call:
            with self.assertRaises(r.Failure):r.main('cleanup')
            call.assert_not_called()

    def test_diagnostics_uses_reviewed_compose(self):
        with patch.dict(os.environ,env(),clear=True),patch.object(diagnostics,'collect') as call:r.main('diagnostics')
        call.assert_called_once_with(r.COMPOSE)

    def test_unreviewed_diagnostic_compose_fails_closed(self):
        with self.assertRaises(ValueError):diagnostics.collect('/private/config.yaml')

    def test_no_raw_secrets_in_redacted_diagnostics(self):
        secret='SYNTHETIC_CANARY_SECRET_12345'
        text=diagnostics.redact('password='+secret+'\nAuthorization: Bearer '+secret+'\nCookie: pm_refresh='+secret,[secret])
        self.assertNotIn(secret,text);self.assertNotIn('pm_refresh=',text)


class ImageIdentityTests(unittest.TestCase):
    def fixture(self):
        lock=r.release_lock();ref=lock['images']['java']
        container={'Config':{'Image':ref},'Image':'sha256:config'}
        image={'Id':'sha256:config','RepoDigests':[ref],'Os':'linux','Architecture':'amd64',
               'Config':{'Labels':{'org.opencontainers.image.revision':r.SOURCE}}}
        return container,image,lock

    def test_config_hash_distinguished_from_manifest_hash(self):
        c,i,l=self.fixture();r.validate_image(c,i,'java',l)
        self.assertNotEqual(c['Image'],l['images']['java'].split('@')[1])

    def test_wrong_tag_config_arch_os_or_source_rejected(self):
        for variant in ('tag','config','digest','arch','os','source'):
            c,i,l=self.fixture()
            if variant=='tag':c['Config']['Image']='bhupirao/paymesh-java:v1.0.0'
            if variant=='config':c['Image']='foreign'
            if variant=='digest':i['RepoDigests']=[]
            if variant=='arch':i['Architecture']='arm64'
            if variant=='os':i['Os']='windows'
            if variant=='source':i['Config']['Labels']={}
            with self.subTest(variant=variant),self.assertRaises(r.Failure):r.validate_image(c,i,'java',l)


class ApiCoverageTests(unittest.TestCase):
    def suite(self):
        with patch.dict(os.environ,env(),clear=True):return r.ReleaseSuite()

    def test_real_chat_and_saved_turn_not_fallback(self):
        good={'analysisMode':'RAG_LLM','generationStatus':'SUCCEEDED','knowledgeReferences':[{}]}
        for path in ('/api/v1/merchant/ai/chat','/api/v1/admin/ai/chat','/api/v1/merchant/ai/conversations/id/messages'):
            for value,passes in [(good,True),({**good,'analysisMode':'RAG_ASSISTED'},False),
                                 ({**good,'generationStatus':'VALIDATION_FAILED'},False),
                                 ({**good,'knowledgeReferences':[]},False)]:
                response={'turn':{'response':value}} if path.endswith('/messages') else value
                with self.subTest(path=path,passes=passes),patch.object(r.Session,'call',return_value=response):
                    session=r.ReleaseSession('ADMIN')
                    if passes:self.assertEqual(session.call('POST',path,{}),response)
                    else:
                        with self.assertRaises(r.Failure):session.call('POST',path,{})

    def test_investigation_both_roles_and_isolation(self):
        s=self.suite();s.payment_id='11111111-1111-4111-8111-111111111111'
        response={'investigation':{'paymentId':s.payment_id,'investigationStatus':'COMPLETED','analysisMode':'RAG_LLM','generationStatus':'SUCCEEDED','knowledgeReferences':[{}],'evidenceReferences':['payment']}}
        s.a=Mock();s.admin=Mock();s.b=Mock();s.a.call.return_value=s.admin.call.return_value=response
        s.investigation();s.a.call.assert_called_once();s.admin.call.assert_called_once()
        self.assertEqual(s.b.call.call_args.kwargs['expected'],(403,404))
        s.a.call.return_value={'investigation':{**response['investigation'],'generationStatus':'TIMEOUT'}}
        with self.assertRaises(r.Failure):s.investigation()

    def test_webhook_invalid_duplicate_and_terminal_protection(self):
        s=self.suite();s.payment_id='11111111-1111-4111-8111-111111111111';s.a=Mock()
        s.a.call.return_value={'status':'SUCCESS'};s.sql=Mock(side_effect=['0','1','1'])
        receipt={'http':200,'id':'22222222-2222-4222-8222-222222222222','status':'IGNORED'}
        s.command=Mock(side_effect=[json.dumps(v).encode() for v in ({'http':401},receipt,receipt)])
        with patch.object(Path,'read_text',return_value='SYNTHETIC_CANARY_WEBHOOK_SECRET'):s.webhook()
        self.assertEqual(s.command.call_count,3)
        for call in s.command.call_args_list:
            self.assertNotIn('SYNTHETIC_CANARY',str(call.args[0]))
            self.assertIn('SYNTHETIC_CANARY_WEBHOOK_SECRET',call.args[1].decode())
        self.assertTrue(json.loads(s.command.call_args_list[0].args[1])['invalid'])
        self.assertFalse(json.loads(s.command.call_args_list[1].args[1])['invalid'])
        compile(r.WEBHOOK_CLIENT,'webhook-client','exec')

    def test_invalid_signature_acceptance_fails_without_more_calls(self):
        s=self.suite();s.payment_id='11111111-1111-4111-8111-111111111111'
        s.command=Mock(return_value=b'{"http":200}');s.sql=Mock()
        with patch.object(Path,'read_text',return_value='SYNTHETIC_SECRET'):
            with self.assertRaises(r.Failure):s.webhook()
        s.command.assert_called_once();s.sql.assert_not_called()

    def test_exact_migration_and_empty_tables_before_seed(self):
        s=self.suite();s.sql=Mock(side_effect=['14','0']+['0']*6+['ADMIN\nMERCHANT',''])
        with patch.object(r.Suite,'seed') as seed:s.seed();seed.assert_called_once()
        self.assertEqual(s.sql.call_count,10)
        self.assertIn("BEGIN READ ONLY",s.sql.call_args.args[0])
        self.assertIn("information_schema.tables",s.sql.call_args.args[0])

    def test_seed_queries_use_actual_migration_table_names(self):
        # Counts must execute against the migration inventory, not a mock that
        # returns zero for any misspelled relation. No external database used.
        import re
        import sqlite3
        migrations=ROOT/'backend/src/main/resources/db/migration'
        names=set()
        for migration in migrations.glob('V*.sql'):
            names.update(re.findall(r'CREATE TABLE\s+(\w+)',migration.read_text(),re.I))
        names.add('flyway_schema_history')
        db=sqlite3.connect(':memory:')
        try:
            for name in names:db.execute('CREATE TABLE '+name+' (fixture INTEGER)')
            s=self.suite();queries=[]
            def sql(text):
                queries.append(text)
                if text.startswith('SELECT role_name'):return 'ADMIN\nMERCHANT'
                if 'BEGIN READ ONLY' in text:return ''
                if text.startswith('SELECT count(*) FROM flyway_schema_history'):
                    return '0' if 'NOT success' in text else '14'
                return str(db.execute(text).fetchone()[0])
            s.sql=sql
            with patch.object(r.Suite,'seed') as seed:s.seed();seed.assert_called_once()
            self.assertIn('SELECT count(*) FROM payment_gateway_transactions;',queries)
            with self.assertRaises(sqlite3.OperationalError):db.execute('SELECT count(*) FROM gateway_transactions;')
        finally:db.close()

    def test_reference_roles_must_match_exact_migration_seed(self):
        migration=(ROOT/'backend/src/main/resources/db/migration/V8__authentication_and_merchant_memberships.sql').read_text()
        self.assertIn("INSERT INTO roles (role_name) VALUES ('ADMIN'), ('MERCHANT');",migration)
        for roles in ('', 'ADMIN', 'MERCHANT', 'ADMIN\nMERCHANT\nUNEXPECTED', 'ADMIN\nADMIN\nMERCHANT'):
            s=self.suite();s.sql=Mock(side_effect=['14','0']+['0']*6+[roles])
            with self.subTest(roles=roles),patch.object(r.Suite,'seed') as seed:
                with self.assertRaisesRegex(r.Failure,'REFERENCE_ROLE_BASELINE_MISMATCH'):s.seed()
                seed.assert_not_called()
                self.assertEqual(s.sql.call_count,9)

    def test_only_validated_reference_data_excluded_from_empty_scan(self):
        s=self.suite();s.sql=Mock(side_effect=['14','0']+['0']*6+['ADMIN\nMERCHANT',''])
        with patch.object(r.Suite,'seed'):s.seed()
        statement=s.sql.call_args.args[0]
        self.assertIn("table_name NOT IN ('flyway_schema_history','roles')",statement)
        self.assertIn("IF populated THEN RAISE EXCEPTION 'CI_EMPTY_DATABASE_REQUIRED'",statement)
        self.assertEqual(s.sql.call_args_list[-2].args[0], 'SELECT role_name FROM roles ORDER BY role_name;')

    def test_nonempty_business_table_blocks_admin_bootstrap(self):
        s=self.suite();s.sql=Mock(side_effect=['14','0']+['0']*6+['ADMIN\nMERCHANT',r.Failure('CONTAINER_OPERATION_FAILED')])
        with patch.object(r.Suite,'seed') as seed:
            with self.assertRaises(r.Failure):s.seed()
            seed.assert_not_called()

    def test_extra_migration_blocks_seed(self):
        s=self.suite();s.sql=Mock(return_value='15')
        with patch.object(r.Suite,'seed') as seed:
            with self.assertRaises(r.Failure):s.seed()
            seed.assert_not_called()


class CleanupTests(unittest.TestCase):
    def fixture(self, temp, **options):
        project='paymesh-e2e-123-1';volume=project+'_container_pgdata'
        folder=Path(temp).resolve()/project;folder.mkdir(mode=0o700)
        services={name:{'volumes':[]} for name in ('postgres','java','python','frontend','llama')}
        services['postgres']['volumes']=[{'type':'volume','source':'container_pgdata','target':'/var/lib/postgresql/data'}]
        config={'name':project,'volumes':{'container_pgdata':{'name':volume}},'services':services}
        actual={'Name':volume,'Driver':'local','Scope':'local','Options':None,
                'Labels':{'com.docker.compose.project':project,'com.docker.compose.volume':'container_pgdata'}}
        records=[{'id':str(i+1)*64,'labels':{'com.docker.compose.project':project,'com.docker.compose.service':name},
                  'mounts':[{'Type':'volume','Name':volume,'Destination':'/var/lib/postgresql/data'}] if name=='postgres' else []}
                 for i,name in enumerate(services)]
        calls=[];state={'removed':False}
        if options.get('external'):config['volumes']['container_pgdata']['external']=True
        if options.get('explicit_shared_name'):config['volumes']['container_pgdata']['name']='shared-data'
        if options.get('driver_options'):config['volumes']['container_pgdata']['driver_opts']={'device':'/protected/data','o':'bind','type':'none'}
        if options.get('extra_volume'):config['volumes']['unexpected']={'name':project+'_unexpected'}
        if options.get('extra_mount'):services['python']['volumes']=[{'type':'volume','source':'other','target':'/other'}]
        if options.get('wrong_labels'):actual['Labels']['com.docker.compose.project']='foreign'
        if options.get('unlabelled'):actual['Labels']={}
        if options.get('anonymous_mount'):records[1]['mounts']=[{'Type':'volume','Name':'unknown-anonymous','Destination':'/unknown'}]
        if options.get('other_container'):records[1]['labels']['com.docker.compose.project']='foreign'
        def output(value, code=0):
            return Mock(returncode=code,stdout=(value if isinstance(value,str) else json.dumps(value)).encode(),stderr=b'SYNTHETIC_PRIVATE_ERROR_MUST_NOT_ESCAPE')
        def execute(args,**kwargs):
            calls.append((args,kwargs))
            self.assertTrue(kwargs['capture_output']);self.assertIn(kwargs['timeout'],(15,90))
            if 'config' in args:return output(config)
            if 'down' in args:
                if options.get('down_fails'):return output('',1)
                state['removed']=True;return output('')
            if args[:3]==['docker','volume','ls']:
                if options.get('absence_query_fails') and state['removed']:return output('',1)
                if state['removed'] and not options.get('volume_remains'):return output('')
                if options.get('no_resources'):return output('')
                return output(volume+'\n')
            if args[:3]==['docker','volume','inspect']:return output([actual])
            if args[:3]==['docker','ps','-a']:
                if state['removed'] and not options.get('container_remains'):return output('')
                if options.get('no_resources'):return output('')
                if 'volume='+volume in args:
                    return output(('f'*64 if options.get('foreign_user') else records[0]['id'])+'\n')
                return output('\n'.join(c['id'] for c in records)+'\n')
            if args[:2]==['docker','inspect']:return output('\n'.join(json.dumps(c) for c in records)+'\n')
            self.fail('Unexpected CLI category')
        return folder,calls,execute

    def run_cleanup(self,temp,**options):
        folder,calls,execute=self.fixture(temp,**options)
        with patch.dict(os.environ,env(temp),clear=True),patch('subprocess.run',side_effect=execute),contextlib.redirect_stdout(io.StringIO()) as output:
            status=r.main('cleanup')
        report=json.loads((folder/'sanitized-cleanup.json').read_text())
        self.assertEqual((folder/'sanitized-cleanup.json').stat().st_mode&0o777,0o600)
        self.assertNotIn('SYNTHETIC_PRIVATE',output.getvalue()+json.dumps(report))
        return status,report,calls

    def test_success_removes_only_project_resources_and_verifies_absence(self):
        with tempfile.TemporaryDirectory() as temp:status,report,calls=self.run_cleanup(temp)
        self.assertEqual(status,0);self.assertTrue(report['success']);self.assertTrue(report['volumesAbsent']);self.assertTrue(report['containersAbsent'])
        down=next(i for i,c in enumerate(calls) if 'down' in c[0]);argv=calls[down][0]
        self.assertIn('--volumes',argv);self.assertIn('paymesh-e2e-123-1',argv);self.assertIn(r.COMPOSE,argv)
        self.assertNotIn('--remove-orphans',argv)
        self.assertEqual(calls[down][1]['timeout'],90)
        self.assertEqual(len(calls[down+1:]),3)
        for args,_ in calls:self.assertNotIn('prune',args);self.assertNotIn('rm',args)

    def test_failed_test_does_not_skip_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,calls,execute=self.fixture(temp)
            with patch.dict(os.environ,env(temp),clear=True),patch.object(r,'ReleaseSuite') as suite,patch('subprocess.run',side_effect=execute):
                suite.return_value.run.return_value=1
                self.assertEqual(r.main('run'),1)
                self.assertEqual(r.main('cleanup'),0)
            self.assertTrue(any('down' in args for args,_ in calls))
        workflow=yaml('.github/workflows/release-artifact-e2e.yml')['jobs']['verify']['steps']
        cleanup=next(s for s in workflow if s.get('run','').endswith('.py cleanup'))
        self.assertIn('always()',cleanup['if'])

    def test_external_or_shared_config_never_reaches_down(self):
        for option in ('external','explicit_shared_name','driver_options','extra_volume','extra_mount'):
            with self.subTest(option=option),tempfile.TemporaryDirectory() as temp:
                status,report,calls=self.run_cleanup(temp,**{option:True})
                self.assertEqual(status,1);self.assertFalse(report['success'])
                self.assertFalse(any('down' in args for args,_ in calls))

    def test_unowned_or_shared_actual_resources_never_reach_down(self):
        for option in ('wrong_labels','unlabelled','foreign_user','anonymous_mount','other_container'):
            with self.subTest(option=option),tempfile.TemporaryDirectory() as temp:
                status,report,calls=self.run_cleanup(temp,**{option:True})
                self.assertEqual(status,1);self.assertFalse(any('down' in args for args,_ in calls))
                self.assertFalse(report['volumesAbsent'])

    def test_remaining_volume_fails_postcleanup_assertion(self):
        with tempfile.TemporaryDirectory() as temp:status,report,calls=self.run_cleanup(temp,volume_remains=True)
        self.assertEqual(status,1);self.assertEqual(report['failureCode'],'CLEANUP_VOLUMES_REMAIN');self.assertFalse(report['volumesAbsent'])

    def test_remaining_container_fails_postcleanup_assertion(self):
        with tempfile.TemporaryDirectory() as temp:status,report,calls=self.run_cleanup(temp,container_remains=True)
        self.assertEqual(status,1);self.assertEqual(report['failureCode'],'CLEANUP_CONTAINERS_REMAIN');self.assertTrue(report['volumesAbsent'])

    def test_failed_absence_query_is_not_proof_of_removal(self):
        with tempfile.TemporaryDirectory() as temp:status,report,calls=self.run_cleanup(temp,absence_query_fails=True)
        self.assertEqual(status,1);self.assertEqual(report['failureCode'],'CLEANUP_DOCKER_OPERATION_FAILED');self.assertFalse(report['volumesAbsent'])

    def test_failed_down_reports_failure_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:status,report,calls=self.run_cleanup(temp,down_fails=True)
        self.assertEqual(status,1);self.assertEqual(report['failureCode'],'CLEANUP_DOCKER_OPERATION_FAILED')
        self.assertEqual(sum('down' in args for args,_ in calls),1);self.assertFalse(report['success'])

    def test_no_startup_resources_still_checked(self):
        with tempfile.TemporaryDirectory() as temp:status,report,calls=self.run_cleanup(temp,no_resources=True)
        self.assertEqual(status,0);self.assertTrue(report['volumesAbsent'])

    def test_cleanup_artifact_retained_after_cleanup_even_on_failure(self):
        steps=yaml('.github/workflows/release-artifact-e2e.yml')['jobs']['verify']['steps']
        clean=next(i for i,s in enumerate(steps) if s.get('run','').endswith('.py cleanup'))
        evidence=steps[clean+1]
        self.assertIn('always()',evidence['if']);self.assertIn('upload-artifact@',evidence['uses'])
        self.assertEqual(evidence['with']['path'],'${{ env.E2E_DIR }}/sanitized-cleanup.json')
        self.assertEqual(evidence['with']['if-no-files-found'],'error')
        self.assertEqual(steps[clean]['timeout-minutes'],5)


if __name__=='__main__':unittest.main()
