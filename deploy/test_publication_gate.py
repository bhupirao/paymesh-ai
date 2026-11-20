"""Offline publication gates: synthetic GitHub metadata, no registry/network use."""
import copy,io,json,os,subprocess,tempfile,unittest,urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock,patch
import publication_gate as g
ROOT=Path(__file__).resolve().parents[1]
class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.env={'PUBLISH':'true','NAMESPACE':'bhupirao','RELEASE_TAG':'v1.0.0','E2E':'true','GITHUB_REPOSITORY':g.REPOSITORY,'GITHUB_REF':'refs/heads/main','GITHUB_SHA':'a'*40}
        self.run={'id':g.RUN_ID,'head_sha':g.SOURCE,'head_branch':'main','status':'completed','conclusion':'success','event':'workflow_dispatch','path':'.github/workflows/container-e2e.yml','workflow_id':423360070,'repository':{'full_name':g.REPOSITORY},'head_repository':{'full_name':g.REPOSITORY}}
        self.protection={'name':'dockerhub-publication','protection_rules':[{'type':'required_reviewers','reviewers':[{'type':'User','reviewer':{'id':1}}]}],'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}}
        self.policies={'total_count':1,'branch_policies':[{'name':'main','type':'branch'}]}
    def read(self,path):
        return {'actions/runs/'+str(g.RUN_ID):self.run,'environments/dockerhub-publication':self.protection,'environments/dockerhub-publication/deployment-branch-policies':self.policies}[path]
    def test_publishing_uses_tested_commit_even_when_main_advances(self):self.assertEqual(g.source_for_release(self.env,self.read),g.SOURCE)
    def test_build_only_uses_dispatch_sha_without_github_or_credentials(self):
        self.env['PUBLISH']='false';read=Mock();self.assertEqual(g.source_for_release(self.env,read),'a'*40);read.assert_not_called()
    def test_invalid_publish_value_rejected(self):
        self.env['PUBLISH']='yes'
        with self.assertRaises(g.GateFailure):g.source_for_release(self.env,self.read)
    def test_non_sha_build_source_rejected(self):
        self.env.update(PUBLISH='false',GITHUB_SHA='main')
        with self.assertRaises(g.GateFailure):g.source_for_release(self.env,self.read)
    def test_wrong_namespace_tag_approval_repository_or_branch_rejected(self):
        for key,value in [('NAMESPACE','other'),('RELEASE_TAG','latest'),('E2E','false'),('GITHUB_REPOSITORY','other/repo'),('GITHUB_REF','refs/heads/unreviewed')]:
            with self.subTest(key=key),self.assertRaises(g.GateFailure):g.source_for_release({**self.env,key:value},self.read)
    def test_unverified_run_identity_status_source_and_workflow_rejected(self):
        original=copy.deepcopy(self.run)
        for key,value in [('id',1),('head_sha','b'*40),('head_branch','other'),('status','in_progress'),('conclusion','failure'),('event','push'),('path','other.yml'),('workflow_id',1),('repository',{'full_name':'other/repo'}),('head_repository',{'full_name':'fork/repo'})]:
            self.run={**original,key:value}
            with self.subTest(key=key),self.assertRaises(g.GateFailure):g.source_for_release(self.env,self.read)
    def test_missing_environment_or_api_failure_fails_closed(self):
        with self.assertRaises(urllib.error.HTTPError):g.source_for_release(self.env,Mock(side_effect=urllib.error.HTTPError('omitted',404,'omitted',None,None)))
    def test_missing_reviewers_rejected(self):
        for rules in [[],[{'type':'required_reviewers','reviewers':[]}],[{'type':'wait_timer','wait_timer':1}]]:
            self.protection['protection_rules']=rules
            with self.assertRaises(g.GateFailure):g.source_for_release(self.env,self.read)
    def test_unrestricted_environment_branches_rejected(self):
        self.protection['deployment_branch_policy']=None
        with self.assertRaises(g.GateFailure):g.source_for_release(self.env,self.read)
    def test_wildcard_tags_or_extra_branch_policies_rejected(self):
        for value in [{'total_count':1,'branch_policies':[{'name':'*','type':'branch'}]}, {'total_count':1,'branch_policies':[{'name':'main','type':'tag'}]}, {'total_count':2,'branch_policies':[{'name':'main','type':'branch'},{'name':'other','type':'branch'}]}]:
            self.policies=value
            with self.assertRaises(g.GateFailure):g.source_for_release(self.env,self.read)
    def test_missing_token_never_opens_network(self):
        with patch.dict(os.environ,{},clear=True),patch.object(g.urllib.request,'build_opener') as open_:
            with self.assertRaises(g.GateFailure):g.github('actions/runs/'+str(g.RUN_ID))
            open_.assert_not_called()
    def test_redirects_denied(self):self.assertIsNone(g.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_main_does_not_print_exception_or_token(self):
        with patch.dict(os.environ,{'PUBLISH':'true'},clear=True),patch.object(g,'source_for_release',side_effect=RuntimeError('PRIVATE_SECRET')),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(g.main(),1)
        self.assertEqual(output.getvalue(),'PUBLICATION_SOURCE_GATE_FAILED\n')
    def test_workflow_builds_pinned_source_and_checks_registry_digest(self):
        workflow=json.loads(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(ROOT/'.github/workflows/container-images.yml')]))
        validate=workflow['jobs']['validate'];images=workflow['jobs']['images'];steps=images['steps']
        self.assertEqual(validate['outputs']['source_sha'],'${{ steps.release.outputs.source_sha }}')
        gate=next(s for s in validate['steps'] if s.get('id')=='release');self.assertEqual(gate['run'],'python3 -B deploy/publication_gate.py')
        checkout=next(s for s in steps if s.get('uses','').startswith('actions/checkout@'))
        self.assertEqual(checkout['with']['ref'],'${{ needs.validate.outputs.source_sha }}');self.assertFalse(checkout['with']['persist-credentials'])
        login=next(s for s in steps if s.get('uses','').startswith('docker/login-action@'))
        guard=next(s for s in steps if s.get('name')=='Check protected credential presence without displaying values')
        self.assertLess(steps.index(guard),steps.index(login));self.assertEqual(guard['if'],'inputs.publish_images')
        build=next(s for s in steps if s.get('id')=='build');self.assertIn('org.opencontainers.image.revision=',build['with']['labels'])
        post=next(s for s in steps if s.get('name')=='Verify published digest and pull by immutable reference')
        self.assertEqual(post['if'],'inputs.publish_images');self.assertEqual(post['env']['DIGEST'],'${{ steps.build.outputs.digest }}')
        self.assertIn("manifest['digest']==digest",post['run']);self.assertIn('docker pull --platform linux/amd64 "$IMAGE@$DIGEST"',post['run'])
        self.assertIn('GITHUB_STEP_SUMMARY',post['run']);self.assertNotIn('latest',build['with']['tags'])

if __name__=='__main__':unittest.main()
