"""Offline publication contracts. All Docker/HTTP operations are mocked."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import frontend_release as r
import frontend_candidate as c
ROOT=Path(__file__).resolve().parents[1]


def browser():
    return {'success':True,'modelInferenceVerified':True,'nativeBrowserTested':True,'infrastructureError':False,
            'frontendArtifactKind':'source-built-candidate','retries':0,
            'tests':[{'code':x,'status':'passed','chromiumLaunchStatus':'SUCCEEDED'} for x in r.TESTS],
            'steps':[{'code':x,'passed':True} for x in r.STAGES]}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.env={'GITHUB_ACTIONS':'true','RUNNER_OS':'Linux','RUNNER_ENVIRONMENT':'github-hosted','GITHUB_REPOSITORY':r.REPO,
                  'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1',
                  'GITHUB_SHA':'f'*40,'RUNNER_TEMP':self.temp.name,'GITHUB_TOKEN':'PRIVATE_CANARY','DOCKERHUB_USERNAME':'bhupirao','DOCKERHUB_TOKEN':'PRIVATE_CANARY'}
        self.patch=patch.dict(os.environ,self.env,clear=True);self.patch.start();self.addCleanup(self.patch.stop)
        self.identifier,self.folder=c.scope();self.folder.mkdir(mode=0o700)
        self.build={'success':True,'candidateId':self.identifier,'sourceRevision':r.SOURCE,'workflowRevision':'f'*40,
                    'contextSha256':r.CONTEXT,'presentationSha256':r.PRESENTATION,'appSha256':c.APP_SHA256,'platform':'linux/amd64',
                    'published':False,'registryManifestDigest':None,'otherApplicationImagesBuilt':False,
                    'imageTag':'paymesh-frontend-candidate:'+self.identifier,'imageConfigDigest':'sha256:'+'a'*64,
                    'imageArchiveSha256':hashlib.sha256(b'synthetic-image').hexdigest()}

    def test_fixed_source_and_runtime_pins(self):
        self.assertEqual(c.SOURCE,r.SOURCE);self.assertEqual(c.CONTEXT_SHA256,r.CONTEXT);self.assertEqual(c.PRESENTATION_SHA256,r.PRESENTATION)
        self.assertEqual(r.IMAGE,'bhupirao/paymesh-frontend:v1.0.1')

    def test_mutable_and_unknown_rules_fail_closed(self):
        for value in [{},{'immutable_tags_settings':{'enabled':False,'rules':['.*']}},{'immutable_tags_settings':{'enabled':True,'rules':['v.*']}}]:self.assertFalse(r.immutable(value))
        self.assertTrue(r.immutable({'immutable_tags_settings':{'enabled':True,'rules':['^v1[.]0[.]1$']}}))

    def test_existing_tag_is_never_overwritten(self):
        with patch.object(r,'registry',return_value=('sha256:'+'b'*64,{})):
            with self.assertRaisesRegex(r.Invalid,'RELEASE_TAG_EXISTS'):r.absent()

    def test_tag_absence_requires_actual_404(self):
        for status in [401,403,429,500]:
            error=r.urllib.error.HTTPError('https://registry.invalid',status,'private',{},None)
            with patch.object(r,'registry',side_effect=error):
                with self.assertRaises(r.Invalid):r.absent()
        with patch.object(r,'registry',side_effect=r.urllib.error.HTTPError('https://registry.invalid',404,'missing',{},None)):r.absent()

    def test_preflight_requires_historical_evidence_and_protected_main_environment(self):
        run={'head_sha':r.HISTORICAL_HEAD,'conclusion':'success','status':'completed','head_branch':'main','event':'workflow_dispatch','path':'.github/workflows/candidate-browser-e2e.yml'}
        env={'can_admins_bypass':False,'protection_rules':[{'type':'required_reviewers','prevent_self_review':False,'reviewers':[{'reviewer':{'login':'bhupirao'}}]}],
             'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}}
        branches={'branch_policies':[{'name':'main','type':'branch'}]}
        def github(path):return run if path.startswith('actions/runs/') else branches if path.endswith('deployment-branch-policies') else env
        info={'is_private':False,'immutable_tags_settings':{'enabled':True,'rules':['^v1[.]0[.]1$']}}
        with patch.object(r,'github',side_effect=github),patch.object(r,'get',return_value=info),patch.object(r,'absent'):
            r.preflight()
            env['can_admins_bypass']=True
            with self.assertRaises(r.Invalid):r.preflight()
            env['can_admins_bypass']=False;env['protection_rules']=[]
            with self.assertRaises(r.Invalid):r.preflight()

    def test_archive_hash_is_computed_from_actual_bytes(self):
        p=Path(self.temp.name)/'bytes';p.write_bytes(b'synthetic-image')
        self.assertEqual(r.digest(p),self.build['imageArchiveSha256'])
        p.write_bytes(b'changed');self.assertNotEqual(r.digest(p),self.build['imageArchiveSha256'])

    def test_all_three_tests_and_ten_stages_required(self):
        r.validate_browser(browser())
        for field in ['tests','steps']:
            report=browser();report[field].pop()
            with self.assertRaises(r.Invalid):r.validate_browser(report)
        report=browser();report['tests'][0]['status']='skipped'
        with self.assertRaises(r.Invalid):r.validate_browser(report)

    def test_real_inference_and_zero_retries_required(self):
        for key,value in [('success',False),('modelInferenceVerified',False),('retries',1),('infrastructureError',True)]:
            report=browser();report[key]=value
            with self.assertRaises(r.Invalid):r.validate_browser(report)

    def test_build_rejects_changed_source_hash_config_and_registry_claim(self):
        r.validate_build(self.build)
        for key,value in [('sourceRevision','0'*40),('presentationSha256','0'*64),('contextSha256','0'*64),('imageConfigDigest','PRIVATE_CANARY'),('registryManifestDigest','sha256:'+'b'*64),('workflowRevision','0'*40)]:
            with self.assertRaises(r.Invalid):r.validate_build({**self.build,key:value})

    def test_cleanup_success_and_failure(self):
        stack={'success':True,'containersAbsent':True,'volumesAbsent':True};image={'success':True,'containerAbsent':True,'candidateImageAbsent':True,'temporaryPayloadRemoved':True}
        r.validate_cleanup(stack,image)
        for key in stack:
            with self.assertRaises(r.Invalid):r.validate_cleanup({**stack,key:False},image)
        for key in image:
            with self.assertRaises(r.Invalid):r.validate_cleanup(stack,{**image,key:False})

    def test_export_strips_unknown_fields_and_seal_requires_cleanup(self):
        stack=Path(self.temp.name).resolve()/'paymesh-e2e-123-1';stack.mkdir(mode=0o700);os.environ['E2E_DIR']=str(stack)
        r.write(self.folder/'candidate.json',{**self.build,'private':'PRIVATE_CANARY'})
        r.write(stack/'sanitized-browser.json',{**browser(),'private':'PRIVATE_CANARY'})
        r.write(stack/'sanitized-browser-final.json',{'success':True})
        (self.folder/'frontend-candidate.tar').write_bytes(b'synthetic-image')
        r.export();payload=Path(self.temp.name)/'frontend-release-payload'
        self.assertNotIn('PRIVATE_CANARY',(payload/'proof.json').read_text())
        with self.assertRaises(FileNotFoundError):r.seal()
        r.write(stack/'sanitized-cleanup.json',{'success':True,'project':'paymesh-e2e-123-1','containersAbsent':True,'volumesAbsent':True})
        r.write(self.folder/'cleanup.json',{'success':True,'candidateId':self.identifier,'containerAbsent':True,'candidateImageAbsent':True,'temporaryPayloadRemoved':True})
        os.environ['GITHUB_OUTPUT']=str(Path(self.temp.name)/'out');r.seal()
        self.assertTrue(r.read(payload/'proof.json')['cleanupVerified'])

    def publication(self, corrupt=False, wrong_artifact=False, bad_member=False, login_failure=False):
        proof={'build':self.build,'browser':browser(),'cleanupVerified':True};raw=json.dumps(proof).encode();archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('proof.json',raw);z.writestr('../frontend.tar' if bad_member else 'frontend.tar',b'wrong' if corrupt else b'synthetic-image')
        os.environ.update(RELEASE_ARTIFACT_ID='42',RELEASE_ARCHIVE_SHA256=self.build['imageArchiveSha256'],RELEASE_PROOF_SHA256=hashlib.sha256(raw).hexdigest())
        metadata={'name':'frontend-v101-payload-123-1','expired':False,'size_in_bytes':len(archive.getvalue()),'workflow_run':{'id':123,'head_sha':'0'*40 if wrong_artifact else 'f'*40}}
        image={'Id':self.build['imageConfigDigest'],'Os':'linux','Architecture':'amd64','Config':{'Labels':{c.REVISION:r.SOURCE,c.OWNER:self.identifier},'User':'10001:10001','Entrypoint':['python','-B','/app/container_entry.py'],'Env':[]}}
        calls=[]
        def command(args,config,stdin=None):
            calls.append(args)
            if args[1]=='login':
                (config/'config.json').write_text('PRIVATE_CANARY')
                if login_failure:raise r.Invalid('RELEASE_DOCKER_OPERATION_FAILED')
            return json.dumps([image]).encode() if args[1:3]==['image','inspect'] else b''
        with patch.object(r,'preflight'),patch.object(r,'absent'),patch.object(r,'github',return_value=metadata),patch.object(r,'request',return_value=io.BytesIO(archive.getvalue())),patch.object(r,'command',side_effect=command),patch.object(r,'registry',return_value=('sha256:'+'b'*64,{'config':{'digest':image['Id']}})):
            if corrupt or wrong_artifact or bad_member or login_failure:
                with self.assertRaises(r.Invalid):r.publish()
            else:r.publish()
        return calls

    def test_publish_uses_transferred_tested_image_without_rebuild(self):
        calls=self.publication();self.assertTrue(any(x[1]=='load' for x in calls));self.assertEqual(sum(x[1]=='push' for x in calls),1)
        self.assertFalse(any('build' in x or 'buildx' in x for x in calls));self.assertTrue(any(x[1]=='pull' and '@sha256:' in x[2] for x in calls))
        proof=r.read(Path(self.temp.name)/'frontend-release-publish/publication.json');self.assertEqual(proof['registryManifestDigest'],'sha256:'+'b'*64);self.assertNotEqual(proof['registryManifestDigest'],proof['imageConfigDigest'])
        self.assertFalse((Path(self.temp.name)/'frontend-release-publish/auth/config.json').exists())

    def test_corrupt_transfer_cannot_reach_docker(self):self.assertEqual(self.publication(corrupt=True),[])
    def test_foreign_artifact_cannot_reach_docker(self):self.assertEqual(self.publication(wrong_artifact=True),[])
    def test_zip_path_traversal_cannot_reach_docker(self):self.assertEqual(self.publication(bad_member=True),[])
    def test_login_failure_cannot_push_and_erases_auth(self):
        calls=self.publication(login_failure=True);self.assertFalse(any(x[1]=='push' for x in calls))
        self.assertFalse((Path(self.temp.name)/'frontend-release-publish/auth/config.json').exists())

    def test_raw_error_never_printed(self):
        output=io.StringIO()
        with patch.object(r,'preflight',side_effect=RuntimeError('PRIVATE_CANARY')),contextlib.redirect_stdout(output):self.assertEqual(r.main('preflight'),1)
        self.assertEqual(output.getvalue().strip(),'FRONTEND_RELEASE_OPERATION_FAILED')

    def test_manual_workflow_protected_publish_after_cleanup(self):
        path=ROOT/'.github/workflows/frontend-v101-publication.yml'
        data=json.loads(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(path)]))
        self.assertEqual(data.get('on',data.get('true')),{'workflow_dispatch':None});self.assertEqual(data['permissions'],{'contents':'read'})
        verify=data['jobs']['verify'];publish=data['jobs']['publish'];self.assertEqual(verify['timeout-minutes'],55)
        self.assertEqual(publish['needs'],'verify');self.assertIn("needs.verify.result == 'success'",publish['if']);self.assertEqual(publish['environment'],'dockerhub-publication')
        steps=verify['steps'];seal=next(i for i,s in enumerate(steps) if s.get('id')=='seal');payload=next(i for i,s in enumerate(steps) if s.get('id')=='payload')
        teardown=[i for i,s in enumerate(steps) if s.get('run','').endswith('.py cleanup')]
        self.assertTrue(all(i<seal<payload for i in teardown));self.assertTrue(all('always()' in steps[i]['if'] for i in teardown))
        self.assertTrue(all('secrets.' not in json.dumps(s) for s in steps));self.assertEqual(publish['permissions'],{'contents':'read','actions':'read'})
        allowed={'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803','docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'}
        for job in data['jobs'].values():
            for step in job['steps']:
                if 'uses' in step:self.assertIn(step['uses'],allowed)
        checkout=[s for s in steps if s.get('with',{}).get('path')=='candidate-source'];self.assertEqual(checkout[0]['with']['ref'],r.SOURCE)
        self.assertEqual(verify['env']['E2E_VERIFY_QWEN'],'true')

if __name__=='__main__':unittest.main()
