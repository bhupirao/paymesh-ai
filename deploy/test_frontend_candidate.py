"""Candidate preparation tests; Docker and network are mocked, never executed."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import frontend_candidate as c

ROOT = Path(__file__).resolve().parents[1]


def workflow():
    return json.loads(subprocess.check_output(['ruby', '-rjson', '-ryaml', '-e',
        'puts JSON.generate(YAML.load_file(ARGV[0]))', str(ROOT/'.github/workflows/frontend-candidate.yml')]))


def image(identifier='paymesh-frontend-candidate-12-1'):
    return {'Id': 'sha256:'+'a'*64, 'Os': 'linux', 'Architecture': 'amd64',
            'RepoTags': ['paymesh-frontend-candidate:'+identifier],
            'Config': {'User': '10001:10001', 'Entrypoint': ['python', '-B', '/app/container_entry.py'],
                       'Env': ['PATH=/usr/bin'], 'Labels': {c.REVISION: c.SOURCE, c.OWNER: identifier}}}


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = {'GITHUB_ACTIONS':'true', 'RUNNER_OS':'Linux', 'RUNNER_ENVIRONMENT':'github-hosted',
                    'GITHUB_REPOSITORY':'bhupirao/paymesh-ai', 'GITHUB_REF':'refs/heads/main',
                    'GITHUB_EVENT_NAME':'workflow_dispatch', 'GITHUB_RUN_ID':'12', 'GITHUB_RUN_ATTEMPT':'1',
                    'RUNNER_TEMP':self.temp.name}

    def test_manual_hosted_read_only_bounded_no_inputs(self):
        w=workflow();self.assertEqual(w.get('on',w.get('true')),{'workflow_dispatch':None})
        self.assertEqual(w['permissions'],{'contents':'read'});self.assertEqual(w['jobs']['candidate']['runs-on'],'ubuntu-24.04')
        self.assertEqual(w['jobs']['candidate']['timeout-minutes'],20)
        self.assertFalse(w['concurrency']['cancel-in-progress'])

    def test_exact_reviewed_source_not_moving_branch(self):
        steps=workflow()['jobs']['candidate']['steps'];checkouts=[s for s in steps if s.get('uses','').startswith('actions/checkout@')]
        self.assertEqual(checkouts[1]['with']['ref'],c.SOURCE)
        self.assertEqual(c.SOURCE,'a15410f2eb2c7d987c142fd7e3758eb237c6c70d')
        self.assertTrue(all(s['with']['persist-credentials'] is False for s in checkouts))

    def test_existing_sha_allowlist_only_and_no_publication(self):
        allowed={'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803',
                 'docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069',
                 'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'}
        source=(ROOT/'.github/workflows/frontend-candidate.yml').read_text()
        for step in workflow()['jobs']['candidate']['steps']:
            if 'uses' in step:self.assertIn(step['uses'],allowed)
        for value in ['secrets.','environment:','login-action','build-push-action','docker push','v1.0.0','workflow_run','pull_request','schedule:']:
            self.assertNotIn(value,source)

    def test_unique_guard_rejects_remote_docker_forks_or_non_manual_runs(self):
        identifier,folder=c.scope(self.env);self.assertEqual(identifier,'paymesh-frontend-candidate-12-1')
        self.assertEqual(folder,Path(self.temp.name).resolve()/identifier)
        for key,value in [('GITHUB_EVENT_NAME','push'),('GITHUB_REF','refs/heads/other'),('RUNNER_ENVIRONMENT','self-hosted'),('DOCKER_HOST','tcp://foreign:2375'),('GITHUB_RUN_ID','../outside')]:
            with self.assertRaises(c.Invalid):c.scope({**self.env,key:value})

    def test_pinned_runtime_context_matches_reviewed_bytes(self):
        # Derive candidate membership from tracked runtime paths; no Docker call.
        names=[p.relative_to(ROOT).as_posix() for p in (ROOT/'frontend').rglob('*') if p.is_file() and c.runtime_path(p.relative_to(ROOT).as_posix())]
        names+=['.dockerignore','deploy/Dockerfile.frontend','deploy/frontend_entry.py']
        names=[name for name in names if '__pycache__' not in name and not name.endswith('.pyc')]
        self.assertEqual(c.fingerprint(ROOT,names),c.CONTEXT_SHA256)
        self.assertEqual(hashlib.sha256((ROOT/'frontend/assets/js/app.js').read_bytes()).hexdigest(),c.APP_SHA256)
        self.assertEqual(hashlib.sha256((ROOT/'frontend/assets/js/chat/presentation.js').read_bytes()).hexdigest(),c.PRESENTATION_SHA256)

    def test_context_rejects_secrets_symlinks_and_unreviewed_paths(self):
        root=Path(self.temp.name);(root/'frontend').mkdir();good=root/'frontend/index.html';good.write_text('synthetic')
        self.assertTrue(c.fingerprint(root,['frontend/index.html']))
        good.write_text('ghp_'+'A'*40)
        with self.assertRaises(c.Invalid):c.fingerprint(root,['frontend/index.html'])
        good.unlink();good.symlink_to('/etc/hosts')
        with self.assertRaises(c.Invalid):c.fingerprint(root,['frontend/index.html'])
        self.assertFalse(c.runtime_path('private.env'));self.assertFalse(c.runtime_path('models/qwen.gguf'))

    def test_image_identity_platform_user_source_and_environment(self):
        c.validate_image(image(),'paymesh-frontend-candidate-12-1')
        for mutation in [{'Architecture':'arm64'},{'Id':'not-a-digest'},{'Config':{'Labels':{c.REVISION:'wrong'}}}]:
            with self.assertRaises(c.Invalid):c.validate_image({**image(),**mutation},'paymesh-frontend-candidate-12-1')
        value=image();value['Config']['Env']+=['SECRET_TOKEN=CANARY']
        with self.assertRaises(c.Invalid):c.validate_image(value,'paymesh-frontend-candidate-12-1')

    def build_case(self, corrupt=False):
        work=Path(self.temp.name)/'workspace';source=work/'candidate-source'
        files=['frontend/assets/js/app.js','frontend/assets/js/chat/presentation.js','deploy/Dockerfile.frontend','deploy/frontend_entry.py','.dockerignore']
        for name in files:
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('synthetic-reviewed-content')
        app_hash=hashlib.sha256((source/files[0]).read_bytes()).hexdigest()
        identifier,folder=c.scope(self.env);calls=[]
        def command(args,timeout=30):
            calls.append(args)
            if args[0]=='git':return c.SOURCE.encode() if args[-1]=='HEAD' else ('\0'.join(files)+'\0').encode()
            if args[1:3]==['image','inspect']:return json.dumps([image(identifier)]).encode()
            if args[1]=='cp':Path(args[-1]).write_bytes(b'wrong-presentation' if corrupt and args[-1].endswith('built-presentation.js') else (source/files[0]).read_bytes())
            if args[1:3]==['image','save']:Path(args[args.index('--output')+1]).write_bytes(b'synthetic-archive-not-an-image')
            return b''
        with patch.dict(os.environ,{**self.env,'GITHUB_WORKSPACE':str(work),'GITHUB_SHA':'f'*40},clear=True),patch.object(c,'APP_SHA256',app_hash),patch.object(c,'PRESENTATION_SHA256',app_hash),patch.object(c,'CONTEXT_SHA256',c.fingerprint(source,files)),patch.object(c,'command',side_effect=command):
            if corrupt:
                with self.assertRaisesRegex(c.Invalid,'^BUILT_PRESENTATION_MISMATCH$'):c.build()
                self.assertFalse(any(a[1:3]==['image','save'] for a in calls))
                self.assertFalse((folder/'candidate.json').exists())
                return
            c.build()
        report=json.loads((folder/'candidate.json').read_text())
        self.assertEqual(report['presentationSha256'],app_hash)
        self.assertTrue(any(a[1]=='cp' and a[-2].endswith('/app/assets/js/chat/presentation.js') for a in calls))
        self.assertFalse(report['published']);self.assertFalse(report['browserTested']);self.assertIsNone(report['registryManifestDigest'])
        self.assertEqual(report['imageConfigDigest'],image()['Id'])
        self.assertEqual(report['imageArchiveSha256'],hashlib.sha256(b'synthetic-archive-not-an-image').hexdigest())
        builds=[a for a in calls if a[:3]==['docker','buildx','build']]
        self.assertEqual(len(builds),1);self.assertIn('--load',builds[0]);self.assertNotIn('--push',builds[0])
        self.assertTrue(builds[0][builds[0].index('--file')+1].endswith('Dockerfile.frontend'))

    def test_build_records_only_candidate_identity_and_exact_built_content(self):
        self.build_case()

    def test_built_presentation_mismatch_fails_before_success_evidence(self):
        self.build_case(corrupt=True)

    def test_both_candidate_workflows_run_history_lifecycle_and_bootstrap(self):
        for name in ['frontend-candidate.yml','candidate-browser-e2e.yml']:
            source=(ROOT/'.github/workflows'/name).read_text()
            self.assertIn('node --experimental-vm-modules candidate-source/frontend/tests/history-state.test.mjs',source)
            self.assertIn('node --experimental-vm-modules candidate-source/frontend/tests/session-bootstrap.test.mjs',source)

    def test_wrong_source_stops_before_any_docker_operation(self):
        work=Path(self.temp.name)/'workspace';(work/'candidate-source').mkdir(parents=True)
        calls=[]
        with patch.dict(os.environ,{**self.env,'GITHUB_WORKSPACE':str(work)},clear=True),patch.object(c,'command',side_effect=lambda args:calls.append(args) or b'wrong-source'):
            with self.assertRaisesRegex(c.Invalid,'SOURCE_COMMIT_MISMATCH'):c.build()
        self.assertTrue(all(args[0]=='git' for args in calls))

    def test_no_registry_digest_claim_or_application_builds(self):
        source=(ROOT/'deploy/frontend_candidate.py').read_text()
        self.assertIn("'registryManifestDigest': None",source);self.assertIn("'browserTested': False",source)
        for value in ['--load','--provenance=false','--sbom=false','--network',"'none'",'BUILT_BOOTSTRAP_MISMATCH']:
            self.assertIn(value,source)
        for value in ['docker push','system prune','volume rm','compose up','--push','--force']:
            self.assertNotIn(value,source)

    def test_evidence_private_exclusive_bounded(self):
        folder=Path(self.temp.name)/'owned';folder.mkdir(mode=0o700)
        c.evidence(folder,'candidate.json',{'success':False,'failureCode':'FIXED_CODE'})
        self.assertEqual((folder/'candidate.json').stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):c.evidence(folder,'candidate.json',{})
        with self.assertRaises(c.Invalid):c.evidence(folder,'arbitrary.env',{})

    def cleanup_case(self,foreign=False,shared=False,remaining=False):
        identifier,folder=c.scope(self.env);folder.mkdir(mode=0o700)
        state={'container':True,'image':True};calls=[]
        extracted=folder/'built-presentation.js';extracted.write_text('synthetic')
        def command(args,timeout=30):
            calls.append(args)
            if args[1:3]==['ps','-aq']:
                if any(x.startswith('ancestor=') for x in args):return b''
                return b'id' if state['container'] or remaining else b''
            if args[1]=='inspect':return json.dumps([{'Name':'/'+identifier,'Config':{'Image':'paymesh-frontend-candidate:'+identifier,'Labels':{c.OWNER:'foreign' if foreign else identifier}},'Mounts':[],'State':{'Running':False}}]).encode()
            if args[1:3]==['container','rm']:state['container']=False;return b''
            if args[1:3]==['image','ls']:return b'id' if state['image'] else b''
            if args[1:3]==['image','inspect']:
                value=image(identifier)
                if shared:value['RepoTags']+=['unrelated:keep']
                return json.dumps([value]).encode()
            if args[1:3]==['image','rm']:state['image']=False;return b''
            raise AssertionError('UNEXPECTED_COMMAND')
        with patch.dict(os.environ,self.env,clear=True),patch.object(c,'command',side_effect=command):
            if foreign or shared or remaining:
                with self.assertRaises(c.Invalid):c.cleanup()
            else:c.cleanup();self.assertTrue(json.loads((folder/'cleanup.json').read_text())['success']);self.assertFalse(extracted.exists())
        return calls

    def test_scoped_cleanup_success(self):
        calls=self.cleanup_case();self.assertTrue(any(a[1:3]==['container','rm'] for a in calls));self.assertTrue(any(a[1:3]==['image','rm'] for a in calls))

    def test_foreign_container_never_removed(self):
        self.assertFalse(any(a[1:3]==['container','rm'] for a in self.cleanup_case(foreign=True)))

    def test_shared_image_never_removed(self):
        self.assertFalse(any(a[1:3]==['image','rm'] for a in self.cleanup_case(shared=True)))

    def test_cleanup_checks_absence_and_reports_failure(self):
        self.cleanup_case(remaining=True)
        output=io.StringIO()
        with patch.object(c,'cleanup',side_effect=RuntimeError('PRIVATE_CANARY')),contextlib.redirect_stdout(output):
            self.assertEqual(c.main('cleanup'),1)
        self.assertNotIn('PRIVATE_CANARY',output.getvalue())

    def test_failure_and_success_cleanup_order_artifact_scope(self):
        steps=workflow()['jobs']['candidate']['steps'];build=next(i for i,s in enumerate(steps) if s.get('id')=='build')
        cleanup=next(i for i,s in enumerate(steps) if s.get('run','').endswith('.py cleanup'))
        self.assertGreater(cleanup,build);self.assertIn('always()',steps[cleanup]['if'])
        self.assertIn('always()',steps[cleanup-1]['if']);self.assertIn('always()',steps[cleanup+1]['if'])
        for step in steps:
            if step.get('uses','').startswith('actions/upload-artifact@'):
                self.assertRegex(step['with']['path'],r'/(candidate|cleanup)\.json$')
                self.assertFalse(step['with']['include-hidden-files'])

    def test_original_release_digests_and_browser_contract_remain_published_only(self):
        lock=json.loads((ROOT/'deploy/release-v1.0.0-images.json').read_text())
        self.assertEqual(lock['images']['frontend'],'bhupirao/paymesh-frontend@sha256:388718b672a9b944348a40257a56d212f1a6e4cb6ad372376a4e03ba5b1b2412')
        compose=(ROOT/'deploy/compose.release-verify.yaml').read_text()
        for ref in lock['images'].values():self.assertIn(ref,compose)
        workflow_source=(ROOT/'.github/workflows/browser-e2e.yml').read_text()
        self.assertIn("E2E_VERIFY_QWEN: 'true'",workflow_source)
        self.assertNotIn('frontend-candidate',workflow_source)


if __name__=='__main__':unittest.main()
