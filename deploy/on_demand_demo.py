"""Runner-only demo lifecycle. Import is inert; all outward operations guarded."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from ci_fixture_setup import prepare
from container_e2e import Suite, require
from release_artifact_e2e import ReleaseSuite, guard, cleanup_project, validate_image
from browser_bootstrap import verify
from frontend_release import TESTS, STAGES
from demo_edge import Edge, public_host

ROOT=Path(__file__).resolve().parent.parent
COMPOSE='deploy/compose.demo.yaml'
LOCK=ROOT/'deploy/demo-images.json'

def private_json(path,value):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'w') as f:
        json.dump(value,f)

def lock():
    value=json.loads(LOCK.read_text())
    require(hashlib.sha256((ROOT/COMPOSE).read_bytes()).hexdigest()==value['composeSha256'],'DEMO_COMPOSE_MISMATCH')
    require(value['frontendSource']=='a15410f2eb2c7d987c142fd7e3758eb237c6c70d','DEMO_FRONTEND_SOURCE_MISMATCH')
    require(value['images']['frontend']=='bhupirao/paymesh-frontend@sha256:a3f7e6929ae7754bc1c45a6d84be626e659e68f72bc559c4a177a0029dbb25e5','DEMO_FRONTEND_DIGEST_MISMATCH')
    from release_artifact_e2e import release_lock
    old=release_lock()
    require(all(value['images'][k]==old['images'][k] for k in ('java','python','llama')),'DEMO_BACKEND_DIGEST_MISMATCH')
    return value

def validate_config(config):
    lock()
    require(set(config['services'])=={'java','python','frontend','llama','postgres'},'DEMO_SERVICE_SET_MISMATCH')
    require(set(config.get('volumes',{}))=={'container_pgdata'},'DEMO_VOLUME_SET_MISMATCH')
    for name,service in config['services'].items():
        require('build' not in service,'DEMO_BUILD_FORBIDDEN')
        if name!='postgres':require(service['image']==lock()['images'][name],'DEMO_IMAGE_MISMATCH')
        else:require(service['image']=='postgres:16.16-bookworm','DEMO_POSTGRES_MISMATCH')
        for port in service.get('ports',[]):
            require(name=='java' and port['host_ip']=='127.0.0.1' and str(port['published'])=='15500' and port['target']==15500,'DEMO_PORT_EXPOSED')

class DemoSuite(ReleaseSuite):
    def __init__(self):
        super().__init__();self.compose[-1]=COMPOSE;self.lock=lock()
    def identity(self):
        Suite.identity(self)
        ids=self.command(self.compose+['ps','-q']).decode().split()
        records=json.loads(self.command(['docker','inspect',*ids]))
        require(len(records)==5,'FIVE_HEALTHY_SERVICES_REQUIRED')
        for c in records:
            service=c['Config']['Labels']['com.docker.compose.service']
            if service=='postgres':
                require(c['Config']['Image']=='postgres:16.16-bookworm','DEMO_POSTGRES_MISMATCH');continue
            image=json.loads(self.command(['docker','image','inspect',self.lock['images'][service]]))[0]
            if service!='frontend':validate_image(c,image,service,self.lock)
            else:
                require(c['Config']['Image']==self.lock['images'][service] and c['Image']==image['Id']
                        and self.lock['images'][service] in image.get('RepoDigests',[])
                        and image['Os']=='linux' and image['Architecture']=='amd64'
                        and image['Config']['Labels']['org.opencontainers.image.revision']==self.lock['frontendSource'],'DEMO_FRONTEND_IDENTITY_MISMATCH')

def browser_gate(report):
    require(report.get('success') is True and report.get('modelInferenceVerified') is True
            and report.get('publishedImagesOnly') is True and report.get('retries')==0
            and report.get('infrastructureError') is False,'DEMO_BROWSER_GATE_FAILED')
    tests=report.get('tests',[]);steps=report.get('steps',[])
    require(len(tests)==3 and {t['code'] for t in tests}==TESTS
            and all(t['status']=='passed' and t['chromiumLaunchStatus']=='SUCCEEDED' for t in tests)
            and {s['code'] for s in steps if s.get('passed')}==STAGES,'DEMO_COMPLETE_CHROMIUM_REQUIRED')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None

def challenge(location,status):
    # A redirect alone is insufficient: require the pinned provider's Access
    # broker, HTTPS, no userinfo and an explicit login path. Never follow it.
    from urllib.parse import urlsplit
    try:p=urlsplit(location);port=p.port
    except ValueError:return False
    return status in (302,303,307) and p.scheme=='https' and p.hostname=='login.trycloudflare.com' and port in (None,443) and not p.username and p.path=='/authorize'

def terminate(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.kill();child.wait(timeout=3)
    require(child is None or child.poll() is not None,'DEMO_PUBLIC_PROCESS_STILL_RUNNING')

def closed(folder):
    path=folder/'demo-processes.json'
    if not path.exists():return not (folder/'public-access-starting.json').exists()
    record=json.loads(path.read_text())
    # PID reuse never authorizes signalling another process. A reused PID
    # remains conservatively unverified; no Docker deletion in that case.
    receipt=folder/'public-access-closed.json'
    return all(not Path('/proc/'+str(pid)).exists() for pid in record['pids']) and receipt.exists() and json.loads(receipt.read_text()).get('success') is True

def allowed_email(email):
    return len(email)<=254 and bool(re.fullmatch(r'[A-Za-z0-9.!#$%&\x27+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',email)) and ',' not in email

def serve(suite):
    folder=suite.folder
    browser_gate(json.loads((folder/'sanitized-browser.json').read_text()))
    require(json.loads((folder/'sanitized-browser-final.json').read_text()).get('success') is True,'DEMO_FINAL_COUNTS_REQUIRED')
    email=os.environ.pop('DEMO_ALLOWED_EMAIL','')
    require(allowed_email(email),'EXACT_DEMO_EMAIL_REQUIRED')
    minutes=os.environ.get('DEMO_MINUTES','10');require(minutes in ('5','10','15'),'DEMO_DURATION_INVALID')
    started=json.loads((folder/'demo-created.json').read_text())['created']
    remaining=started+45*60-time.time()
    require(remaining>=120,'DEMO_ADMISSION_DEADLINE_EXCEEDED')
    deadline=time.monotonic()+min(int(minutes)*60,remaining)
    spec=json.loads((ROOT/'deploy/cloudflared-demo.json').read_text());binary=folder/'cloudflared'
    require(hashlib.sha256(binary.read_bytes()).hexdigest()==spec['sha256'],'CLOUDFLARED_CHECKSUM_MISMATCH')
    result=subprocess.run([str(binary),'tunnel','--help'],capture_output=True,timeout=10)
    require(result.returncode==0 and b'--allowed-mail' in result.stdout,'QUICK_TUNNEL_EMAIL_AUTH_UNSUPPORTED')
    credentials=[('Admin','ci-admin@e2e.example.test',(folder/'secrets/admin_password').read_text()),('Merchant','browser-a@e2e.example.test',(folder/'secrets/merchant_password').read_text())]
    server=Edge(ROOT,credentials,deadline);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    child=None;stopped=threading.Event()
    def stop(*args):stopped.set()
    previous={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
    log=folder/'private-tunnel.log'
    try:
        with os.fdopen(os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as output:
            # No config file/account token; exact recipient, never a domain/wildcard.
            private_json(folder/'public-access-starting.json',{'attempted':True})
            child=subprocess.Popen([str(binary),'--no-autoupdate','tunnel','--config','/dev/null','--url','http://127.0.0.1:15501','--allowed-mail',email],stdout=output,stderr=output)
            private_json(folder/'demo-processes.json',{'pids':[child.pid]})
            until=time.monotonic()+90;url=None
            while time.monotonic()<until and not stopped.is_set():
                require(child.poll() is None,'DEMO_TUNNEL_EXITED')
                require(log.stat().st_size<=262144,'DEMO_TUNNEL_LOG_LIMIT')
                raw=log.read_text(errors='replace')
                matches=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',raw)
                if matches and 'Your protected quick Tunnel has been created!' in raw:
                    url=matches[0];break
                stopped.wait(.5)
            require(url is not None and not stopped.is_set(),'PROTECTED_TUNNEL_NOT_ESTABLISHED')
            server.host=public_host(url)
            # Server remains locked until the unauthenticated internet probe
            # proves the Access challenge is before the origin.
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            try:
                with opener.open(url+'/_demo/start',timeout=20) as response:status=response.status;location=response.headers.get('Location','')
            except urllib.error.HTTPError as response:status=response.code;location=response.headers.get('Location','');response.close()
            require(challenge(location,status),'OTP_ACCESS_GATE_UNVERIFIED')
            require(time.monotonic()<deadline and not stopped.is_set(),'DEMO_EXPIRED')
            server.active=True
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
                summary.write('## Temporary authenticated acceptance demo\n\nEmail OTP is required. Synthetic credentials are available only behind that gate.\n\n'+url+'/_demo/start\n\n'+url+'/merchant/login\n\n'+url+'/admin/login\n\n'+url+'/docs/\n\nMaximum access: '+minutes+' minutes; ends earlier on cancellation or failure.\n')
            # Step summaries may appear only after the blocking step ends.
            # This validated base entry URL is intentionally public; no email,
            # credential, auth state, payment link or checkout token is included.
            print('DEMO_AUTHENTICATED_ENTRY='+url+'/_demo/start',flush=True)
            print('DEMO_OTP_GATE_VERIFIED_ACCESS_OPEN',flush=True)
            while time.monotonic()<deadline and not stopped.wait(.5):
                require(child.poll() is None,'DEMO_TUNNEL_EXITED')
                require(log.stat().st_size<=262144,'DEMO_TUNNEL_LOG_LIMIT')
    finally:
        server.active=False
        terminate(child) # Public access closes before database/container teardown.
        server.shutdown();server.server_close();thread.join(timeout=3)
        private_json(folder/'public-access-closed.json',{'success':True,'reason':'expired_cancelled_or_finished','publicProcessExited':True})
        for s,handler in previous.items():signal.signal(s,handler)
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as summary:
            summary.write('\n**Session closed.** The temporary URL is no longer usable. Require the separate cleanup receipt for container/volume absence.\n')
        print('DEMO_PUBLIC_ACCESS_CLOSED',flush=True)

def main(action):
    guard();lock()
    if action=='fixtures':
        prepare()
        # GITHUB_ENV is consumed only by the NEXT Actions step.
        from ci_fixture_setup import runner_project
        folder=Path(os.environ['RUNNER_TEMP'])/runner_project()
        private_json(folder/'demo-created.json',{'created':time.time()});return 0
    suite=DemoSuite()
    if action in ('seed','final'):return verify(suite,action)
    if action=='serve':serve(suite);return 0
    if action=='cleanup':
        require(closed(suite.folder),'PUBLIC_ACCESS_CLOSURE_UNVERIFIED_NO_CLEANUP')
        return cleanup_project(suite.project,suite.folder,compose_file=COMPOSE,validate_config=validate_config)
    if action=='diagnostics':
        # Fixed fields only: no raw application/tunnel logs in public artifacts.
        private_json(suite.folder/'sanitized-demo-failure.json',{'success':False,'failureCode':'DEMO_STAGE_FAILED','rawLogsRetained':False});return 0
    require(False,'UNKNOWN_DEMO_ACTION')

if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1] if len(sys.argv)==2 else ''))
    except Exception:
        print('DEMO_GUARD_OR_OPERATION_FAILED_NO_RAW_OUTPUT');raise SystemExit(1)
