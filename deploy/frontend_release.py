"""Fixed frontend v1.0.1 promotion. Captures commands; emits fixed codes only."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import frontend_candidate as candidate

IMAGE = 'bhupirao/paymesh-frontend:v1.0.1'
REPO = 'bhupirao/paymesh-ai'
HISTORICAL_RUN = 44877848710
HISTORICAL_HEAD = '2d2f6dad99443849a15b4b86879b594eb7b4e967'
SOURCE = 'a15410f2eb2c7d987c142fd7e3758eb237c6c70d'
CONTEXT = 'd8ccb142df61fbe71c16bc7f65f761230e0c83e80cd762f9724b34703273c01e'
PRESENTATION = '8f1bec53de24ee2d9aa5301d47f11513959cc816071d1ca69467abcca1b78780'
TESTS = {'DESKTOP_KEYBOARD_AND_VALIDATION','MOBILE_KEYBOARD_AND_VALIDATION','COMPLETE_NATIVE_BROWSER_JOURNEY'}
STAGES = {'MERCHANT_REGISTRATION_VALIDATION','ADMIN_LOGIN_AND_NATIVE_APPROVAL','DASHBOARD_SESSION_AND_ROLE_PROTECTION','PAYMENT_CREATION_PROCESSING_AND_LIST','MERCHANT_OWNERSHIP_ISOLATION','NATIVE_INVESTIGATION_REAL_QWEN','PARTIAL_AND_FULL_REFUND_UI','PAYMENT_LINK_AND_CUSTOMER_CHECKOUT','MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY','CROSS_TAB_LOGOUT_AND_PROTECTED_ROUTE'}
LIMIT = 1_073_741_824

class Invalid(Exception):
    pass

def require(ok, code):
    if not ok:
        raise Invalid(code)

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        require(urllib.parse.urlparse(url).scheme == 'https', 'HTTPS_REQUIRED')
        out = super().redirect_request(req, fp, code, msg, headers, url)
        if out and urllib.parse.urlparse(req.full_url).netloc != urllib.parse.urlparse(url).netloc:
            out.remove_header('Authorization')
        return out

def request(url, token=None):
    headers = {'Accept':'application/vnd.github+json'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    return urllib.request.build_opener(Redirect()).open(urllib.request.Request(url, headers=headers), timeout=45)

def get(url, token=None):
    with request(url, token) as response:
        raw = response.read(1_048_577)
    require(len(raw) <= 1_048_576, 'METADATA_LIMIT')
    return json.loads(raw)

def github(path):
    token = os.environ.get('GITHUB_TOKEN')
    require(bool(token), 'GITHUB_TOKEN_REQUIRED')
    return get('https://api.github.com/repos/'+REPO+'/'+path, token)

def scope():
    identifier, folder = candidate.scope()
    require(bool(re.fullmatch('[a-f0-9]{40}',os.environ.get('GITHUB_SHA','')))
            and candidate.SOURCE == SOURCE and candidate.CONTEXT_SHA256 == CONTEXT
            and candidate.PRESENTATION_SHA256 == PRESENTATION, 'RELEASE_SOURCE_PIN_MISMATCH')
    return identifier, folder

def private(path):
    if not path.exists():
        path.mkdir(mode=0o700)
    candidate.private(path)
    return path

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b''):
            value.update(chunk)
    return value.hexdigest()

def read(path):
    stat = path.lstat()
    require(path.is_file() and not path.is_symlink() and stat.st_uid == os.getuid()
            and stat.st_size <= 65536 and not stat.st_mode & 0o077, 'PRIVATE_EVIDENCE_REQUIRED')
    return json.loads(path.read_text())

def write(path, value):
    raw = json.dumps(value, sort_keys=True).encode()
    require(len(raw) <= 65536, 'EVIDENCE_LIMIT')
    with os.fdopen(os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600),'wb') as out:
        out.write(raw)

def immutable(info):
    settings = info.get('immutable_tags_settings') or {}
    # Deliberately recognize only unambiguous rules, not a different regex engine.
    return settings.get('enabled') is True and any(rule in ('.*','^.*$','^v1[.]0[.]1$','^v1\\.0\\.1$') for rule in settings.get('rules',[]))

def registry(ref):
    token = get('https://auth.docker.io/token?service=registry.docker.io&scope=repository:bhupirao/paymesh-frontend:pull')['token']
    url = 'https://registry-1.docker.io/v2/bhupirao/paymesh-frontend/manifests/'+ref
    headers = {'Authorization':'Bearer '+token,'Accept':'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'}
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as response:
        raw = response.read(1_048_577)
        header = response.headers.get('Docker-Content-Digest')
    require(len(raw)<=1_048_576 and header=='sha256:'+hashlib.sha256(raw).hexdigest(), 'REGISTRY_MANIFEST_MISMATCH')
    return header, json.loads(raw)

def absent():
    try:
        registry('v1.0.1')
    except urllib.error.HTTPError as error:
        require(error.code == 404, 'TAG_AVAILABILITY_UNKNOWN')
        return
    raise Invalid('RELEASE_TAG_EXISTS')

def preflight():
    scope()
    run = github('actions/runs/'+str(HISTORICAL_RUN))
    require(run.get('head_sha')==HISTORICAL_HEAD and run.get('conclusion')=='success'
            and run.get('status')=='completed' and run.get('head_branch')=='main' and run.get('event')=='workflow_dispatch'
            and run.get('path')=='.github/workflows/candidate-browser-e2e.yml', 'HISTORICAL_E2E_REQUIRED')
    env = github('environments/dockerhub-publication')
    reviewers = [r for r in env.get('protection_rules',[]) if r.get('type')=='required_reviewers']
    require(env.get('can_admins_bypass') is False and any(r.get('prevent_self_review') is False
            and any(x.get('reviewer',{}).get('login')=='bhupirao' for x in r.get('reviewers',[])) for r in reviewers), 'APPROVAL_PROTECTION_REQUIRED')
    require(env.get('deployment_branch_policy')=={'protected_branches':False,'custom_branch_policies':True}, 'MAIN_ONLY_REQUIRED')
    branches = github('environments/dockerhub-publication/deployment-branch-policies')['branch_policies']
    require(len(branches)==1 and branches[0].get('name')=='main' and branches[0].get('type')=='branch', 'MAIN_ONLY_REQUIRED')
    info = get('https://hub.docker.com/v2/namespaces/bhupirao/repositories/paymesh-frontend')
    require(info.get('is_private') is False and immutable(info), 'PUBLIC_IMMUTABLE_TAG_POLICY_REQUIRED')
    absent()

def validate_build(build):
    identifier, _ = scope()
    require(build.get('success') is True and build.get('candidateId')==identifier
            and build.get('sourceRevision')==SOURCE and build.get('workflowRevision')==os.environ['GITHUB_SHA']
            and build.get('contextSha256')==CONTEXT and build.get('presentationSha256')==PRESENTATION
            and build.get('appSha256')==candidate.APP_SHA256 and build.get('platform')=='linux/amd64'
            and build.get('published') is False and build.get('registryManifestDigest') is None
            and build.get('otherApplicationImagesBuilt') is False
            and build.get('imageTag')=='paymesh-frontend-candidate:'+identifier
            and bool(re.fullmatch(candidate.DIGEST,build.get('imageConfigDigest','')))
            and bool(re.fullmatch('[a-f0-9]{64}',build.get('imageArchiveSha256',''))), 'BUILD_EVIDENCE_MISMATCH')

def validate_browser(report):
    tests, stages = report.get('tests',[]), report.get('steps',[])
    require(report.get('success') is True and report.get('modelInferenceVerified') is True
            and report.get('nativeBrowserTested') is True and report.get('infrastructureError') is False
            and report.get('frontendArtifactKind')=='source-built-candidate' and report.get('retries')==0
            and len(tests)==3 and {t.get('code') for t in tests}==TESTS
            and all(t.get('status')=='passed' and t.get('chromiumLaunchStatus')=='SUCCEEDED' for t in tests)
            and len(stages)==10 and {s.get('code') for s in stages}==STAGES
            and all(s.get('passed') is True for s in stages), 'COMPLETE_REAL_CHROMIUM_REQUIRED')

def export():
    _, folder = scope()
    candidate.private(folder)
    stack = Path(os.environ['E2E_DIR'])
    require(stack == Path(os.environ['RUNNER_TEMP']).resolve()/('paymesh-e2e-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']), 'STACK_SCOPE_REQUIRED')
    build = read(folder/'candidate.json');validate_build(build)
    report = read(stack/'sanitized-browser.json');validate_browser(report)
    require(read(stack/'sanitized-browser-final.json').get('success') is True, 'FINAL_COUNTS_REQUIRED')
    payload = private(Path(os.environ['RUNNER_TEMP']).resolve()/'frontend-release-payload')
    source = folder/'frontend-candidate.tar'
    require(source.is_file() and not source.is_symlink() and source.stat().st_size<=LIMIT
            and digest(source)==build['imageArchiveSha256'], 'ARCHIVE_MISMATCH')
    target = payload/'frontend.tar'
    with source.open('rb') as src, target.open('xb') as dst:
        os.chmod(target,0o600);shutil.copyfileobj(src,dst)
    safe_build={k:build[k] for k in ('success','candidateId','sourceRevision','workflowRevision','contextSha256',
        'presentationSha256','appSha256','platform','published','registryManifestDigest','otherApplicationImagesBuilt',
        'imageTag','imageConfigDigest','imageArchiveSha256')}
    safe_report={'success':True,'modelInferenceVerified':True,'nativeBrowserTested':True,'infrastructureError':False,
        'frontendArtifactKind':'source-built-candidate','retries':0,
        'tests':[{'code':code,'status':'passed','chromiumLaunchStatus':'SUCCEEDED'} for code in sorted(TESTS)],
        'steps':[{'code':code,'passed':True} for code in sorted(STAGES)]}
    write(payload/'proof.json', {'build':safe_build,'browser':safe_report,'cleanupVerified':False})

def validate_cleanup(stack, image):
    require(stack.get('success') is True and stack.get('volumesAbsent') is True and stack.get('containersAbsent') is True,
            'STACK_CLEANUP_REQUIRED')
    require(image.get('success') is True and image.get('containerAbsent') is True and image.get('candidateImageAbsent') is True
            and image.get('temporaryPayloadRemoved') is True, 'IMAGE_CLEANUP_REQUIRED')

def seal():
    identifier, folder = scope()
    payload = private(Path(os.environ['RUNNER_TEMP']).resolve()/'frontend-release-payload')
    proof = read(payload/'proof.json');validate_build(proof['build']);validate_browser(proof['browser'])
    stack = read(Path(os.environ['E2E_DIR'])/'sanitized-cleanup.json');image=read(folder/'cleanup.json')
    require(stack.get('project')=='paymesh-e2e-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
            and image.get('candidateId')==identifier, 'CLEANUP_SCOPE_REQUIRED')
    validate_cleanup(stack,image)
    require(digest(payload/'frontend.tar')==proof['build']['imageArchiveSha256'], 'ARCHIVE_MISMATCH')
    proof['cleanupVerified']=True
    # Existing validated proof only; exclusive replacement file then atomic replace.
    temporary=payload/'sealed.json';write(temporary,proof);os.replace(temporary,payload/'proof.json')
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:
        output.write('archive_sha256='+proof['build']['imageArchiveSha256']+'\nproof_sha256='+digest(payload/'proof.json')+'\n')

def command(args, config, stdin=None):
    result = subprocess.run(args,input=stdin,capture_output=True,timeout=300,
                            env={**{k:v for k,v in os.environ.items() if k not in ('DOCKERHUB_TOKEN','DOCKERHUB_USERNAME','GITHUB_TOKEN')},'DOCKER_CONFIG':str(config)})
    require(result.returncode==0 and len(result.stdout)<=4_194_304, 'RELEASE_DOCKER_OPERATION_FAILED')
    return result.stdout

def publish():
    preflight()
    identifier, _ = scope()
    artifact_id = os.environ.get('RELEASE_ARTIFACT_ID','')
    require(bool(re.fullmatch('[0-9]+',artifact_id)), 'ARTIFACT_ID_REQUIRED')
    artifact=github('actions/artifacts/'+artifact_id)
    require(artifact.get('name')=='frontend-v101-payload-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
            and artifact.get('expired') is False and artifact.get('size_in_bytes',LIMIT+1)<=LIMIT
            and artifact.get('workflow_run',{}).get('id')==int(os.environ['GITHUB_RUN_ID'])
            and artifact.get('workflow_run',{}).get('head_sha')==os.environ['GITHUB_SHA'], 'ARTIFACT_PROVENANCE_MISMATCH')
    folder=private(Path(os.environ['RUNNER_TEMP']).resolve()/'frontend-release-publish')
    archive=folder/'payload.zip'
    with request('https://api.github.com/repos/'+REPO+'/actions/artifacts/'+artifact_id+'/zip',os.environ['GITHUB_TOKEN']) as src, archive.open('xb') as dst:
        total=0
        while True:
            chunk=src.read(1_048_576)
            if not chunk:break
            total+=len(chunk);require(total<=LIMIT,'ARTIFACT_LIMIT');dst.write(chunk)
    with zipfile.ZipFile(archive) as z:
        names=z.namelist();require(sorted(names)==['frontend.tar','proof.json'], 'ARTIFACT_MEMBERS_MISMATCH')
        for name,limit in [('proof.json',65536),('frontend.tar',LIMIT)]:
            require(z.getinfo(name).file_size<=limit,'ARTIFACT_LIMIT')
            with z.open(name) as src,(folder/name).open('xb') as dst:
                os.chmod(folder/name,0o600);shutil.copyfileobj(src,dst)
    require(digest(folder/'proof.json')==os.environ['RELEASE_PROOF_SHA256']
            and digest(folder/'frontend.tar')==os.environ['RELEASE_ARCHIVE_SHA256'], 'TRANSFER_DIGEST_MISMATCH')
    proof=read(folder/'proof.json');validate_build(proof['build']);validate_browser(proof['browser'])
    require(proof.get('cleanupVerified') is True and proof['build']['imageArchiveSha256']==os.environ['RELEASE_ARCHIVE_SHA256'], 'SEALED_CLEANUP_REQUIRED')
    anonymous=private(folder/'anonymous');auth=private(folder/'auth')
    command(['docker','load','--input',str(folder/'frontend.tar')],anonymous)
    build=proof['build'];images=json.loads(command(['docker','image','inspect',build['imageTag']],anonymous))
    require(len(images)==1 and images[0]['Id']==build['imageConfigDigest'], 'LOADED_IMAGE_MISMATCH')
    candidate.validate_image(images[0],identifier)
    require(os.environ.get('DOCKERHUB_USERNAME')=='bhupirao' and bool(os.environ.get('DOCKERHUB_TOKEN')), 'REGISTRY_CREDENTIAL_REQUIRED')
    absent() # Recheck immediately before the only tag/push; server immutability closes races.
    try:
        command(['docker','login','--username','bhupirao','--password-stdin'],auth,os.environ['DOCKERHUB_TOKEN'].encode())
        command(['docker','tag',build['imageConfigDigest'],IMAGE],anonymous)
        command(['docker','push',IMAGE],auth)
    finally:
        credentials=auth/'config.json'
        if credentials.exists():
            require(credentials.is_file() and not credentials.is_symlink(),'AUTH_CONFIG_MISMATCH');credentials.unlink()
    registry_digest,manifest=registry('v1.0.1')
    require(manifest.get('config',{}).get('digest')==build['imageConfigDigest'], 'PUBLISHED_CONFIG_MISMATCH')
    command(['docker','pull',IMAGE.split(':')[0]+'@'+registry_digest],anonymous)
    pulled=json.loads(command(['docker','image','inspect',IMAGE.split(':')[0]+'@'+registry_digest],anonymous))
    require(len(pulled)==1 and pulled[0]['Id']==build['imageConfigDigest'], 'ANONYMOUS_PULL_MISMATCH')
    candidate.validate_image(pulled[0],identifier)
    write(folder/'publication.json',{'success':True,'image':IMAGE,'registryManifestDigest':registry_digest,
          'imageConfigDigest':build['imageConfigDigest'],'sourceRevision':SOURCE,'contextSha256':CONTEXT,
          'presentationSha256':PRESENTATION,'browserRun':int(os.environ['GITHUB_RUN_ID']),
          'threeChromiumTestsPassed':True,'tenStagesPassed':True,'realInferenceVerified':True,
          'cleanupVerified':True,'anonymousDigestPullVerified':True,'publishedOtherImages':False})

def main(action):
    try:
        require(action in ('preflight','export','seal','publish'),'FIXED_ACTION_REQUIRED')
        globals()[action]()
        print('FRONTEND_RELEASE_'+action.upper()+'_PASS')
        return 0
    except Exception as error:
        code=str(error) if isinstance(error,Invalid) else 'FRONTEND_RELEASE_OPERATION_FAILED'
        code=code if re.fullmatch('[A-Z0-9_]{1,80}',code) else 'FRONTEND_RELEASE_OPERATION_FAILED'
        if action=='publish':
            try:
                scope()
                folder=private(Path(os.environ['RUNNER_TEMP']).resolve()/'frontend-release-publish')
                if not (folder/'publication.json').exists():
                    write(folder/'publication.json',{'success':False,'failureCode':code,'image':IMAGE,
                          'publicationMayHaveOccurred':True,'automaticRetryAllowed':False})
            except Exception:
                pass
        print(code)
        return 1

if __name__=='__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv)==2 else ''))
