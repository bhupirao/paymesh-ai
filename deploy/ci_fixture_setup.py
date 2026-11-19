"""Generate NEW runner-only secrets/config. Never reads host PayMesh configuration."""
import json,os,re,secrets,subprocess,sys
from pathlib import Path

def runner_project():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_OS')!='Linux':
        raise RuntimeError('GITHUB_HOSTED_LINUX_ONLY')
    if os.environ.get('DOCKER_HOST','') not in ('','unix:///var/run/docker.sock'):raise RuntimeError('LOCAL_RUNNER_DOCKER_ONLY')
    run,attempt=os.environ.get('GITHUB_RUN_ID',''),os.environ.get('GITHUB_RUN_ATTEMPT','')
    if not re.fullmatch(r'[0-9]+',run) or not re.fullmatch(r'[0-9]+',attempt):raise RuntimeError('INVALID_RUN_ID')
    return 'paymesh-e2e-'+run+'-'+attempt

def prepare():
    project=runner_project();verify=os.environ.get('E2E_VERIFY_QWEN','false');
    if verify not in ('true','false'):raise RuntimeError('INVALID_MODEL_VERIFICATION_FLAG')
    temp=Path(os.environ['RUNNER_TEMP']).resolve();work=Path(os.environ['GITHUB_WORKSPACE']).resolve()
    folder=temp/project;folder.mkdir(mode=0o700,exist_ok=False);secret=folder/'secrets';secret.mkdir(mode=0o700)
    for name in ('db_password','ai_token','razorpay_secret','stripe_secret','settlement_token','admin_password','merchant_password'):
        path=secret/name;path.write_text(secrets.token_urlsafe(48 if name=='ai_token' else 24));path.chmod(0o444)
    subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(secret/'jwt_private')],capture_output=True,check=True)
    subprocess.run(['openssl','pkey','-in',str(secret/'jwt_private'),'-pubout','-out',str(secret/'jwt_public')],capture_output=True,check=True)
    for name in ('jwt_private','jwt_public'):(secret/name).chmod(0o444)
    # Secrets are read-only files within an owner-only parent. Mounts stay readable
    # by the non-root runtime UID; no Compose uid-remapping assumption is made.
    values={'DOCKERHUB_NAMESPACE':'bhupirao','RELEASE_TAG':'v1.0.0','PAYMESH_REPO_DIR':str(work),'CONTAINER_SECRET_DIR':str(secret),'LLAMA_CPP_SOURCE_DIR':str(folder/'llama-source'),'QWEN_MODEL_FILE':str(folder/'qwen.gguf'),'CHAT_ENABLED':'true','ANALYSIS_MODE':'RAG_LLM' if verify=='true' else 'RAG_ASSISTED'}
    env=folder/'container.env';env.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n');env.chmod(0o600)
    with open(os.environ['GITHUB_ENV'],'a') as out:
        for k,v in {'E2E_PROJECT':project,'E2E_DIR':str(folder),'E2E_ENV':str(env)}.items():out.write(k+'='+v+'\n')
    print('RUNNER_ONLY_FIXTURES_PREPARED')
if __name__=='__main__':
    try:prepare()
    except Exception:print('RUNNER_FIXTURE_PREPARATION_FAILED');sys.exit(1)
