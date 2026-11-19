"""Offline synthetic redaction and workflow ordering tests; never calls Docker."""
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import capture_failure_diagnostics as d
ROOT=Path(__file__).resolve().parents[1]
BEGIN='-'*5+'BEGIN PRIVATE KEY'+'-'*5
END='-'*5+'END PRIVATE KEY'+'-'*5

class RedactionTests(unittest.TestCase):
    def test_known_values_and_json_escaped_values(self):
        text='secret with spaces\n'+json.dumps('secret with spaces')
        self.assertNotIn('secret with spaces',d.redact(text,['secret with spaces']))
    def test_timestamped_pem_lines_removed(self):
        body='A'*60+'=='
        text='00:00 '+BEGIN+'\n00:00 '+body+'\n00:00 '+END+'\nCaused by: safe failure'
        clean=d.redact(text,[body]);self.assertNotIn(body,clean);self.assertNotIn(BEGIN,clean);self.assertIn('safe failure',clean)
    def test_uninventoried_pem_block_removed(self):
        self.assertNotIn('private contents',d.redact(BEGIN+'\nprivate contents\n'+END,[]))
    def test_unterminated_pem_removed(self):self.assertNotIn('private contents',d.redact(BEGIN+'\nprivate contents',[]))
    def test_jwt_and_bearer_redacted(self):
        jwt='eyJ'+('a'*10)+'.'+('b'*30)+'.'+('c'*30)
        clean=d.redact('Authorization: Bearer '+jwt,[]);self.assertNotIn(jwt,clean)
    def test_basic_authorization_redacted(self):self.assertNotIn('YWJjZGVmZ2g=',d.redact('Authorization: Basic YWJjZGVmZ2g=',[]))
    def test_quoted_credentials_with_whitespace(self):
        clean=d.redact('{"password": "unknown spaced credential", "api_key":"opaque-value"}',[])
        self.assertNotIn('unknown spaced credential',clean);self.assertNotIn('opaque-value',clean)
    def test_cookie_header_redacted(self):self.assertNotIn('private-cookie',d.redact('Set-Cookie: pm_refresh=private-cookie; HttpOnly',[]))
    def test_url_userinfo_and_query_redacted(self):
        clean=d.redact('http://alice:privatepass@db/path?token=private-query',[])
        self.assertNotIn('privatepass',clean);self.assertNotIn('private-query',clean)
    def test_partial_key_tail_redacted(self):self.assertNotIn('B'*64,d.redact('B'*64+'\n',[]))
    def test_useful_startup_exception_preserved(self):
        message='Caused by: java.lang.IllegalStateException: Unsafe local session cookie configuration'
        self.assertEqual(d.redact(message,[]),message)
    def test_capture_is_byte_bounded_and_drops_partial_secret_line(self):
        text,meta=d.capture([sys.executable,'-c',"import sys;sys.stdout.write('safe\\n'+'PRIVATE_PARTIAL_'*10000);sys.stdout.flush()"],limit=64,timeout=2)
        self.assertTrue(meta['truncated']);self.assertNotIn('PRIVATE_PARTIAL_',text);self.assertIn('safe',text)
    def test_capture_timeout_bounded(self):
        start=time.monotonic();_,meta=d.capture([sys.executable,'-c','import time;time.sleep(5)'],limit=64,timeout=.1)
        self.assertTrue(meta['timedOut']);self.assertLess(time.monotonic()-start,4)

class CollectionTests(unittest.TestCase):
    def fixture(self,folder):
        project='paymesh-e2e-123-1';run=folder/project;run.mkdir(mode=0o700);secrets=run/'secrets';secrets.mkdir(mode=0o700)
        for name in d.SECRET_NAMES:(secrets/name).write_text('SYNTHETIC_CANARY_'+name+'_PRIVATE_VALUE')
        (run/'container.env').write_text('NEVER_UPLOAD_THIS_ENV_CONTENT')
        env={'GITHUB_ACTIONS':'true','RUNNER_OS':'Linux','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','RUNNER_TEMP':str(folder),'E2E_PROJECT':project,'E2E_DIR':str(run),'E2E_ENV':str(run/'container.env')}
        return run,env
    def test_missing_inventory_fails_closed_without_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp).resolve();run,env=self.fixture(folder);(run/'secrets/ai_token').unlink()
            with patch.dict(os.environ,env,clear=True),patch.object(d,'capture') as capture:d.collect();capture.assert_not_called()
            report=json.loads((run/'diagnostics/status.json').read_text());self.assertEqual(report['status'],'REDACTION_UNAVAILABLE_NO_LOGS_CAPTURED');self.assertFalse(list((run/'diagnostics').glob('*.log')))
    def test_symlink_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            run,_=self.fixture(Path(temp).resolve());p=run/'secrets/ai_token';p.unlink();p.symlink_to(run/'container.env')
            with self.assertRaises(ValueError):d.secret_values(run)
    def test_redacted_capture_includes_all_services_and_selected_state(self):
        with tempfile.TemporaryDirectory() as temp:
            run,env=self.fixture(Path(temp).resolve());calls=[]
            def capture(args,**kwargs):
                calls.append(args)
                if args[-3:]==['ps','-a','-q']:return 'a'*64,{'exitCode':0}
                return 'Caused by: SAFE_EXCEPTION\nSYNTHETIC_CANARY_db_password_PRIVATE_VALUE\n',{'exitCode':0}
            with patch.dict(os.environ,env,clear=True),patch.object(d,'capture',side_effect=capture):d.collect()
            logs=[c for c in calls if 'logs' in c];self.assertEqual({c[-1] for c in logs},{'java','postgres','python','llama','frontend'})
            self.assertTrue(all('--timestamps' in c and '--tail' in c and '200' in c for c in logs))
            inspect=next(c for c in calls if c[:2]==['docker','inspect']);self.assertNotIn('.Config.Env',inspect[3]);self.assertIn('.State.ExitCode',inspect[3]);self.assertIn('.State.Health.Status',inspect[3])
            joined=''.join(p.read_text() for p in (run/'diagnostics').iterdir());self.assertNotIn('SYNTHETIC_CANARY_',joined);self.assertNotIn('NEVER_UPLOAD_THIS_ENV_CONTENT',joined);self.assertIn('SAFE_EXCEPTION',joined)
            self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in (run/'diagnostics').iterdir()))
    def test_invalid_container_id_never_reaches_inspect(self):
        with tempfile.TemporaryDirectory() as temp:
            run,env=self.fixture(Path(temp).resolve());calls=[]
            def capture(args,**kwargs):calls.append(args);return '--untrusted-id',{'exitCode':0}
            with patch.dict(os.environ,env,clear=True),patch.object(d,'capture',side_effect=capture):d.collect()
            self.assertFalse(any(c[:2]==['docker','inspect'] for c in calls))

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(ROOT/'.github/workflows/container-e2e.yml')]);cls.steps=json.loads(raw)['jobs']['e2e']['steps']
    def test_failure_capture_and_upload_before_cleanup(self):
        startup=next(s for s in self.steps if s.get('id')=='startup')
        capture=next(s for s in self.steps if s.get('name')=='Capture bounded redacted startup failure diagnostics')
        upload=next(s for s in self.steps if s.get('uses','').startswith('actions/upload-artifact@'))
        cleanup=next(s for s in self.steps if s.get('name','').startswith('Stop only'))
        self.assertLess(self.steps.index(startup),self.steps.index(capture));self.assertLess(self.steps.index(capture),self.steps.index(upload));self.assertLess(self.steps.index(upload),self.steps.index(cleanup))
        for step in (capture,upload):self.assertEqual(step['if'],"${{ failure() && steps.startup.outcome == 'failure' }}")
        self.assertEqual(cleanup['if'],'always()')
    def test_artifact_retention_and_narrow_path(self):
        upload=next(s for s in self.steps if s.get('uses','').startswith('actions/upload-artifact@'))['with']
        self.assertEqual(upload['retention-days'],3);self.assertFalse(upload['include-hidden-files'])
        self.assertEqual(upload['path'].splitlines(),['${{ env.E2E_DIR }}/diagnostics/*.log','${{ env.E2E_DIR }}/diagnostics/status.json'])
        self.assertNotIn('secrets',upload['path']);self.assertNotIn('.env',upload['path']);self.assertNotIn('**',upload['path'])
    def test_upload_not_conditioned_on_capture_success(self):
        upload=next(s for s in self.steps if s.get('uses','').startswith('actions/upload-artifact@'))
        self.assertNotIn('success()',upload['if']);self.assertNotIn('steps.capture',upload['if'])
if __name__=='__main__':unittest.main()
