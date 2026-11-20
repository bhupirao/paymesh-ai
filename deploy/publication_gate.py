"""Read-only release gate. No Docker credentials, registry writes or model downloads."""
import json,os,re,sys,urllib.request
SOURCE='cefa7df83a5bf16d011e82041c95e2d93b9c637b'
RUN_ID=44652430877
REPOSITORY='bhupirao/paymesh-ai'
class GateFailure(Exception):pass

def require(value):
    if not value:raise GateFailure('PUBLICATION_GATE_FAILED')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def github(path):
    token=os.environ.get('GITHUB_TOKEN','');require(bool(token))
    request=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+'/'+path,
        headers={'Accept':'application/vnd.github+json','Authorization':'Bearer '+token,'User-Agent':'PayMesh-release-gate'})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:
        data=response.read(131073);require(len(data)<=131072);return json.loads(data)

def source_for_release(env,read=github):
    require(env.get('PUBLISH') in ('true','false'))
    if env['PUBLISH']=='false':
        require(bool(re.fullmatch('[0-9a-f]{40}',env.get('GITHUB_SHA',''))));return env['GITHUB_SHA']
    require(env.get('NAMESPACE')=='bhupirao' and env.get('RELEASE_TAG')=='v1.0.0' and env.get('E2E')=='true')
    require(env.get('GITHUB_REPOSITORY')==REPOSITORY and env.get('GITHUB_REF')=='refs/heads/main')
    run=read('actions/runs/'+str(RUN_ID))
    require(run.get('id')==RUN_ID and run.get('head_sha')==SOURCE and run.get('head_branch')=='main')
    require(run.get('status')=='completed' and run.get('conclusion')=='success' and run.get('event')=='workflow_dispatch')
    require(run.get('path')=='.github/workflows/container-e2e.yml' and run.get('workflow_id')==423360070)
    require(run.get('repository',{}).get('full_name')==REPOSITORY and run.get('head_repository',{}).get('full_name')==REPOSITORY)
    protection=read('environments/dockerhub-publication')
    require(protection.get('name')=='dockerhub-publication')
    require(any(r.get('type')=='required_reviewers' and r.get('reviewers') for r in protection.get('protection_rules',[])))
    require(protection.get('deployment_branch_policy')=={'protected_branches':False,'custom_branch_policies':True})
    policies=read('environments/dockerhub-publication/deployment-branch-policies')
    require(policies.get('total_count')==1 and len(policies.get('branch_policies',[]))==1)
    require(policies['branch_policies'][0].get('name')=='main' and policies['branch_policies'][0].get('type')=='branch')
    return SOURCE

def main():
    try:
        source=source_for_release(os.environ)
        with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('source_sha='+source+'\n')
        print('PUBLICATION_SOURCE_GATE_PASS')
        return 0
    except Exception:
        print('PUBLICATION_SOURCE_GATE_FAILED');return 1
if __name__=='__main__':raise SystemExit(main())
