"""Offline candidate Chromium orchestration/identity/cleanup regressions."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import candidate_browser as b
import frontend_candidate as c
import browser_bootstrap
from container_e2e import Failure
import release_artifact_e2e as release

ROOT=Path(__file__).resolve().parents[1]


def yaml(name):
    return json.loads(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(ROOT/name)]))


def proof(identifier='paymesh-frontend-candidate-12-1'):
    return {'success':True,'candidateId':identifier,'sourceRevision':c.SOURCE,'workflowRevision':'f'*40,
            'platform':'linux/amd64','imageTag':'paymesh-frontend-candidate:'+identifier,
            'imageConfigDigest':'sha256:'+'a'*64,'imageArchiveSha256':'b'*64,'appSha256':c.APP_SHA256,
            'contextSha256':c.CONTEXT_SHA256,'registryManifestDigest':None,'published':False,
            'browserTested':False,'otherApplicationImagesBuilt':False}


def config(value):
    lock=release.release_lock()
    return {'services':{**{name:{'image':lock['images'][name]} for name in ('java','python','llama')},
            'frontend':{'image':value['imageTag'],'pull_policy':'never'},'postgres':{'image':'postgres:16.16-bookworm'}}}


class CandidateBrowserTests(unittest.TestCase):
    def setUp(self):
        self.workflow=yaml('.github/workflows/candidate-browser-e2e.yml')
        self.steps=self.workflow['jobs']['browser']['steps']

    def test_manual_only_read_only_hosted_bounded_no_environment(self):
        self.assertEqual(self.workflow.get('on',self.workflow.get('true')),{'workflow_dispatch':None})
        self.assertEqual(self.workflow['permissions'],{'contents':'read'})
        job=self.workflow['jobs']['browser'];self.assertEqual(job['runs-on'],'ubuntu-24.04');self.assertEqual(job['timeout-minutes'],55)
        self.assertNotIn('environment',job);self.assertFalse(self.workflow['concurrency']['cancel-in-progress'])
        self.assertEqual(job['env']['E2E_VERIFY_QWEN'],'true')

    def test_pinned_source_and_existing_allowed_actions(self):
        allowed={'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803','docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'}
        checkouts=[]
        for step in self.steps:
            if 'uses' in step:self.assertIn(step['uses'],allowed)
            if step.get('uses','').startswith('actions/checkout@'):checkouts.append(step)
        self.assertEqual(checkouts[1]['with']['ref'],c.SOURCE)
        self.assertTrue(all(s['with']['persist-credentials'] is False for s in checkouts))

    def test_frontend_only_build_no_publication_or_model_on_mac(self):
        source=(ROOT/'.github/workflows/candidate-browser-e2e.yml').read_text()
        self.assertEqual(source.count('deploy/frontend_candidate.py build'),1)
        for forbidden in ['secrets.','docker push','login-action','build-push-action','deploy/build.sh']:self.assertNotIn(forbidden,source)
        pull=next(s['run'] for s in self.steps if 'pull java python llama postgres' in s.get('run',''))
        self.assertNotIn('pull frontend',pull)
        start=next(s['run'] for s in self.steps if s.get('id')=='startup')
        self.assertIn('--no-build --pull never',start)

    def test_compose_candidate_and_backends_are_explicit(self):
        model=yaml(b.COMPOSE);self.assertEqual(set(model['services']),{'java','python','llama','frontend','postgres'})
        for name in ('java','python','llama'):self.assertEqual(model['services'][name]['image'],release.release_lock()['images'][name])
        frontend=model['services']['frontend'];self.assertIn('CANDIDATE_FRONTEND_IMAGE',frontend['image']);self.assertEqual(frontend['pull_policy'],'never')
        self.assertEqual(frontend['network_mode'],'service:java')
        self.assertEqual(model['services']['java']['ports'],['127.0.0.1:15500:15500'])
        self.assertTrue(all('build' not in service for service in model['services'].values()))
        self.assertEqual(model['volumes'],{'container_pgdata':{}})
        b.compose_guard()

    def test_candidate_metadata_rejects_tamper_foreign_and_publication_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);folder.chmod(0o700);file=folder/'candidate.json';file.write_text(json.dumps(proof()));file.chmod(0o600)
            with patch.object(c,'scope',return_value=(proof()['candidateId'],folder)),patch.dict(os.environ,{'GITHUB_SHA':'f'*40}):
                self.assertEqual(b.metadata()['imageConfigDigest'],proof()['imageConfigDigest'])
                for key,value in [('sourceRevision','0'*40),('workflowRevision','0'*40),('imageTag','foreign:tag'),('appSha256','0'*64),('contextSha256','0'*64),('published',True),('registryManifestDigest','sha256:'+'a'*64),('browserTested',True)]:
                    file.write_text(json.dumps({**proof(),key:value}))
                    with self.assertRaises(Failure):b.metadata()
                file.write_text(json.dumps(proof()));file.chmod(0o644)
                with self.assertRaises(Failure):b.metadata()

    def test_mixed_identity_rejects_backend_or_candidate_replacement(self):
        value=proof();valid=config(value);b.validate_config(valid,value)
        for name in ['java','python','llama','frontend']:
            bad=copy.deepcopy(valid);bad['services'][name]['image']='foreign:mutable'
            with self.assertRaises(Failure):b.validate_config(bad,value)
        bad=copy.deepcopy(valid);bad['services']['frontend']['build']='.'
        with self.assertRaises(Failure):b.validate_config(bad,value)

    def test_running_frontend_matches_config_digest_not_registry_digest(self):
        value=proof();image={'Id':value['imageConfigDigest'],'Os':'linux','Architecture':'amd64','Config':{'User':'10001:10001','Entrypoint':['python','-B','/app/container_entry.py'],'Env':[], 'Labels':{c.REVISION:c.SOURCE,c.OWNER:value['candidateId']}}}
        container={'Image':image['Id'],'Config':{'Image':value['imageTag']}}
        b.validate_frontend(container,image,value)
        with self.assertRaises(Failure):b.validate_frontend({**container,'Image':'sha256:'+'c'*64},image,value)
        with self.assertRaises(Failure):b.validate_frontend({**container,'Config':{'Image':'frontend:foreign'}},image,value)

    def test_native_three_test_suite_real_ai_pacing_and_assertions_remain(self):
        run=next(s for s in self.steps if s.get('id')=='browser_tests')
        self.assertEqual(run['run'],'npm test');self.assertEqual(run['working-directory'],'deploy/browser-e2e')
        model=next(s for s in self.steps if 'checksum-verified Qwen' in s.get('name',''))
        self.assertIn('74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db',model['run'])
        config_source=(ROOT/'deploy/browser-e2e/playwright.config.js').read_text()
        for text in ['workers: 1','retries: 0',"browserName: 'chromium'","'journey.spec.js'", "'accessibility.spec.js'"]:self.assertIn(text,config_source)
        journey=(ROOT/'deploy/browser-e2e/journey.spec.js').read_text()
        self.assertIn('modelSuccess(',journey);self.assertIn('HISTORY_REFRESHED',journey);self.assertNotIn('test.skip',journey)
        self.assertIn('61000',(ROOT/'deploy/browser-e2e/auth-budget.js').read_text())

    def test_default_bootstrap_remains_published_and_candidate_is_explicit(self):
        suite=Mock();suite.folder=Path('/synthetic')
        with patch.object(browser_bootstrap.os,'open',return_value=9),patch.object(browser_bootstrap.os,'fdopen'):
            self.assertEqual(browser_bootstrap.verify(suite,'seed',candidate=True),0)
        self.assertEqual(suite.check.call_count,2)
        source=(ROOT/'deploy/browser_bootstrap.py').read_text();self.assertIn('return verify(ReleaseSuite(), action)',source)
        self.assertIn("'publishedImagesVerified': not candidate",source)

    def test_teardown_order_failure_diagnostics_and_artifact_allowlist(self):
        diagnostic=next(i for i,s in enumerate(self.steps) if s.get('run','').endswith('candidate_browser.py diagnostics'))
        cleanup=next(i for i,s in enumerate(self.steps) if s.get('run','').endswith('candidate_browser.py cleanup'))
        image_cleanup=next(i for i,s in enumerate(self.steps) if s.get('run','').endswith('frontend_candidate.py cleanup'))
        self.assertLess(diagnostic,cleanup);self.assertLess(cleanup,image_cleanup)
        self.assertIn('failure()',self.steps[diagnostic]['if'])
        for i in (cleanup,image_cleanup):self.assertIn('always()',self.steps[i]['if'])
        for step in self.steps:
            if 'upload-artifact@' in step.get('uses',''):
                self.assertFalse(step['with']['include-hidden-files']);self.assertEqual(step['with']['retention-days'],3)
                for line in step['with']['path'].splitlines():
                    self.assertTrue(line.endswith(('.json','.log')));self.assertNotIn('secrets',line);self.assertNotIn('tar',line)

    def test_candidate_cleanup_reuses_full_ownership_guard_and_cannot_skip_extra_validation(self):
        with tempfile.TemporaryDirectory() as tmp,patch('subprocess.run') as run:
            self.assertEqual(release.cleanup_project('synthetic',Path(tmp),compose_file=b.COMPOSE),1)
            run.assert_not_called()
            evidence=json.loads((Path(tmp)/'sanitized-cleanup.json').read_text())
            self.assertEqual(evidence['failureCode'],'CLEANUP_CANDIDATE_VALIDATION_REQUIRED')
        source=(ROOT/'deploy/release_artifact_e2e.py').read_text()
        for text in ['CLEANUP_VOLUME_SHARED_WITH_FOREIGN_CONTAINER','CLEANUP_UNEXPECTED_ACTUAL_VOLUME',"['down', '--volumes'",'CLEANUP_VOLUMES_REMAIN','CLEANUP_CONTAINERS_REMAIN']:
            self.assertIn(text,source)

    def test_mixed_stack_identity_checks_three_registry_images_and_one_local_image(self):
        suite=object.__new__(b.CandidateSuite);suite.candidate=proof();suite.lock=release.release_lock();suite.compose=['docker','compose'];records=[];images={}
        for index,name in enumerate(('java','python','llama','frontend','postgres')):
            ref=suite.candidate['imageTag'] if name=='frontend' else 'postgres:16.16-bookworm' if name=='postgres' else suite.lock['images'][name]
            digest=suite.candidate['imageConfigDigest'] if name=='frontend' else 'sha256:'+str(index+1)*64
            records.append({'Image':digest,'Config':{'Image':ref,'Labels':{'com.docker.compose.service':name}},'HostConfig':{}})
            if name=='frontend':images[ref]={'Id':digest,'Os':'linux','Architecture':'amd64','Config':{'User':'10001:10001','Entrypoint':['python','-B','/app/container_entry.py'],'Labels':{c.REVISION:c.SOURCE,c.OWNER:proof()['candidateId']}}}
            elif name!='postgres':images[ref]={'Id':digest,'RepoDigests':[ref],'Os':'linux','Architecture':'amd64','Config':{'Labels':{c.REVISION:release.SOURCE}}}
        def command(args):
            if 'config' in args:return json.dumps(config(proof())).encode()
            if args[-2:]==['ps','-q']:return b'one two three four five'
            if args[:3]==['docker','image','inspect']:return json.dumps([images[args[-1]]]).encode()
            return json.dumps(records).encode()
        suite.command=command
        with tempfile.TemporaryDirectory() as temp,patch.object(b.Suite,'identity'):
            suite.folder=Path(temp);suite.identity()
            evidence=json.loads((suite.folder/'candidate.json').read_text())
            self.assertFalse(evidence['publishedImagesOnly']);self.assertIsNone(evidence['frontendRegistryManifestDigest'])
            self.assertEqual(set(evidence['publishedBackends']),{'java','python','llama'})

    def test_candidate_volume_cleanup_success_and_failure_keep_original_guard(self):
        from test_release_artifact_e2e import CleanupTests
        helper=CleanupTests('test_success_removes_only_project_resources_and_verifies_absence')
        for options,expected in [({},0),({'external':True},1),({'foreign_user':True},1),({'down_fails':True},1)]:
            with tempfile.TemporaryDirectory() as tmp:
                folder,calls,original=helper.fixture(tmp,**options)
                def execute(args,**kwargs):
                    result=original(args,**kwargs)
                    if 'config' in args:
                        model=json.loads(result.stdout)
                        for name,value in config(proof())['services'].items():model['services'][name].update(value)
                        result.stdout=json.dumps(model).encode()
                    return result
                with patch('subprocess.run',side_effect=execute):
                    self.assertEqual(release.cleanup_project('paymesh-e2e-123-1',folder,compose_file=b.COMPOSE,validate_config=lambda model:b.validate_config(model,proof())),expected)
                record=json.loads((folder/'sanitized-cleanup.json').read_text())
                self.assertEqual(record['success'],expected==0)
                if options.get('external') or options.get('foreign_user'):self.assertFalse(any('down' in args for args,_ in calls))

    def test_identity_inherits_strict_v14_seed_and_health_contract(self):
        self.assertIs(b.CandidateSuite.seed,release.ReleaseSuite.seed)
        self.assertIs(b.CandidateSuite.sql,release.ReleaseSuite.sql)
        source=(ROOT/'deploy/candidate_browser.py').read_text()
        self.assertIn('Suite.identity(self)',source);self.assertIn('else:validate_image(container, images[0], service, self.lock)',source)
        self.assertNotIn('release.COMPOSE =',source)


if __name__=='__main__':unittest.main()
