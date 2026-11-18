"""Stage a NEW frozen cold-start release. No service start, backup or inference.
Final baseline verification/sealing is operator-assisted through /dev/tty.
"""
import hashlib,hmac,json,os,shutil,stat,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
from phase673_otp_ops import Stop,protected
from ai_reliability_forward import digest
from ai_reliability_cold import env_file,configs,empty_ports
JAVA='6f6a2e27659ff338fb01163819a1a8cf2112d694e579515e7d64256eac0d96ba'
PYTHON='9ef4ccc9e6ed7a989eea1d924f2ddcbffa93e124ce0b63cb9598dbb481f68006'
BACKUP='581740dd25113f463096f00177d8f4db4c33b6e7f578c92b318936d246dbefe2'
BINARY='8a48b6c90204b752021adbd99ddb66c9b447d71f6ce4333a205be0527ab2bcc8'
MODEL='74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db'

def cmd(args,**kwargs):
 r=subprocess.run([str(x) for x in args],capture_output=True,**kwargs)
 if r.returncode:raise Stop('Preparation metadata/import check failed.')
 return r.stdout

def stage():
 root=Path(__file__).resolve().parents[2];private=protected(Path.home()/'.config/paymesh-demo',0o700);empty_ports();index=digest(root/'.git/index')
 backup_evidence=protected(private/'v14-pre-cold-start-backup-20261118T161201Z-sg04p91w/evidence.json');baseline=json.loads(backup_evidence.read_text());archive=protected(Path(baseline['backup']['path']))
 if not baseline.get('success') or not baseline.get('beforeAfterFingerprintsMatch') or digest(archive)!=BACKUP:raise Stop('Approved V14 backup differs.')
 cmd(['/Library/PostgreSQL/16/bin/pg_restore','--list',archive]);cmd(['/Library/PostgreSQL/16/bin/pg_restore','--file=/dev/null',archive])
 jar=root/'backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar'
 paths=[*sorted((root/'ai-service/app').rglob('*.py')),*sorted((root/'ai-service/app').rglob('*.json')),*sorted((root/'ai-service/knowledge_base').glob('*.md')),root/'ai-service/requirements.txt']
 source={str(p.relative_to(root)):digest(p) for p in paths}
 if digest(jar)!=JAVA or len(source)!=40 or hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=PYTHON:raise Stop('Approved release fingerprint differs.')
 model=Path.home()/'Developer/paymesh-tools/models/qwen2.5-0.5b-instruct-q4_k_m.gguf';llama=Path.home()/'Developer/paymesh-tools/llama.cpp/build/bin/llama-server';java=Path('/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java')
 if digest(llama)!=BINARY or digest(model)!=MODEL:raise Stop('Reviewed model/server artifact differs.')
 version=cmd([llama,'--version']);help_text=cmd([llama,'--help'])
 for flag in (b'--host',b'--port',b'--alias',b'--ctx-size',b'--threads',b'--parallel',b'--n-gpu-layers',b'--log-disable'):
  if flag not in help_text:raise Stop('Required local model launch flag unavailable.')
 staged=private/'otp-step17-phase697a-stage-enable-20261117T014704Z-y04_6166'
 # Preserve the reviewed launch's property-file ordering, with explicit CLI safety overrides.
 locations=[private/'activation-673-20261114T165645Z.BOzvsG/sessions.properties',private/'otp-step17-deploy-20261114T181004Z-5kbrnbq_/otp.properties',private/'otp-step17-activate-20261114T181150Z-exy1_tap/otp.properties',private/'otp-step17-disable-20261114T192418Z-f2y4hrzi/otp.properties',private/'otp-step17-activate-phase674-20261115T045625Z-yd6r_0kn/otp.properties',private/'otp-step17-activate-phase681-20261115T070224Z-62yoz_bv/otp.properties',private/'otp-step17-redeploy-phase681-analytics-20261115T103656Z-kuu2z8f7/otp.properties',private/'otp-step17-phase697a-v14-20261117T013809Z-a0rd__3j/otp.properties',staged/'java-chat.properties']
 config_files=locations+[private/'demo.env',private/'secrets.env',staged/'python-chat.env']
 configpins={str(p):digest(protected(p)) for p in config_files}
 demo=env_file(private/'demo.env')
 configpins[demo['PAYMESH_JWT_PRIVATE_KEY_FILE']]=digest(protected(Path(demo['PAYMESH_JWT_PRIVATE_KEY_FILE'])))
 public=Path(demo['PAYMESH_JWT_PUBLIC_KEY_FILE']);info=public.lstat()
 if public.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:raise Stop('Public key ownership/write permissions differ.')
 public_pins={str(public):{'sha256':digest(public),'mode':stat.S_IMODE(info.st_mode)}}
 # Verify keypair correspondence without exposing either key.
 pub=cmd(['/usr/bin/openssl','pkey','-in',demo['PAYMESH_JWT_PRIVATE_KEY_FILE'],'-pubout'])
 canonical=cmd(['/usr/bin/openssl','pkey','-pubin','-in',demo['PAYMESH_JWT_PUBLIC_KEY_FILE'],'-pubout'])
 if pub!=canonical:raise Stop('Existing JWT keypair mismatch.')
 release=Path(tempfile.mkdtemp(prefix='ai-reliability-cold-release-',dir=private));os.chmod(release,0o700)
 (release/'java').mkdir();shutil.copyfile(jar,release/'java/paymesh.jar')
 for p in paths:
  dest=release/'python'/p.relative_to(root/'ai-service');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 shutil.copytree(root/'ai-service/.venv',release/'python/.venv',symlinks=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 front=release/'frontend';front.mkdir()
 for p in (root/'frontend').glob('*.py'):shutil.copyfile(p,front/p.name)
 for name in ('index.html','checkout.html'):shutil.copyfile(root/'frontend'/name,front/name)
 shutil.copytree(root/'frontend/assets',front/'assets')
 ops=release/'ops';ops.mkdir()
 for name in ('ai_reliability_cold.py','ai_reliability_forward.py','ai_reliability_python_launch.py','phase673_otp_ops.py','phase697a_process.py','phase697a_diagnostic.py'):
  shutil.copyfile(root/'backend/scripts'/name,ops/name)
 reader=Path('/private/tmp/paymesh-v14-backup-preflight/verify_backup.py')
 if not reader.is_file():raise Stop('Previously reviewed read-only baseline reader missing.')
 shutil.copyfile(reader,ops/'v14_backup_reader.py')
 flags={'spring.config.location':'classpath:/application.properties','spring.config.additional-location':','.join('file:'+str(p) for p in locations),'spring.profiles.active':'demo','spring.datasource.url':'jdbc:postgresql://127.0.0.1:5432/paymesh_demo','spring.datasource.username':'paymesh_demo_user','spring.flyway.enabled':'false','spring.flyway.target':'14','spring.flyway.validate-on-migrate':'true','spring.jpa.hibernate.ddl-auto':'validate','spring.sql.init.mode':'never','spring.jpa.properties.hibernate.default_schema':'public','server.address':'127.0.0.1','server.port':'18080','server.forward-headers-strategy':'none','server.ssl.enabled':'false','paymesh.sessions.origin':'http://127.0.0.1:5500','paymesh.sessions.local-http':'true','paymesh.settlement.scheduling-enabled':'false','paymesh.demo.password-recovery.enabled':'false','paymesh.demo.checkout-controls.enabled':'false','paymesh.conversations.cleanup-enabled':'false','paymesh.ai.enabled':'true','paymesh.ai.base-url':'http://127.0.0.1:8000','paymesh.ai.chat.response-timeout-ms':'25000'}
 python_settings={'PAYMESH_AI_ANALYSIS_MODE':'RAG_LLM','PAYMESH_AI_GENERATION_ENABLED':'true','PAYMESH_AI_INFERENCE_URL':'http://127.0.0.1:8082/v1/chat/completions','PAYMESH_AI_MODEL_NAME':'paymesh-qwen','PAYMESH_AI_GENERATION_TIMEOUT':'30','PAYMESH_AI_MAX_OUTPUT_TOKENS':'128','PAYMESH_AI_CONTEXT_CHARS':'12000'}
 # New, explicitly reviewed cold-start configuration; not a claim to recover the old environment.
 m={'status':'AWAITING_READ_ONLY_DATABASE_BASELINE_AND_SEAL','preparedUtc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'trueRollbackAvailable':False,'postgresSecurityExceptionAccepted':True,'javaSha256':JAVA,'pythonManifestSha256':PYTHON,'pythonFileCount':40,'sourcePins':source,'protectedConfigPins':configpins,'javaExecutable':str(java),'javaFlags':['--'+k+'='+v for k,v in flags.items()],'javaChatFile':str(staged/'java-chat.properties'),'pythonChatFile':str(staged/'python-chat.env'),'pythonSettings':python_settings,'frontendPython':str(release/'python/.venv/bin/python'),'llamaCommand':[str(llama),'--model',str(model),'--host','127.0.0.1','--port','8082','--alias','paymesh-qwen','--ctx-size','4096','--threads','2','--parallel','1','--n-gpu-layers','0','--log-disable'],'ports':{'llm':8082,'ai':8000,'java':18080,'frontend':5500},'cwd':{'llm':str(llama.parents[2]),'ai':'python','java':str(root/'backend'),'frontend':'frontend'},'startupTimeoutSeconds':{'llm':90,'ai':60,'java':90,'frontend':30},'migrationHistory':baseline['migrationHistory'],'backup':baseline['backup'],'backupEvidence':str(backup_evidence),'backupEvidenceSha256':digest(backup_evidence),'databaseBaseline':{'fingerprints':baseline['fingerprints'],'tableCounts':baseline['tableCounts'],'entityCounts':baseline['entityCounts']},'gitIndexBefore':index}
 configs(release,m,'SYNTHETIC_NOT_USED',True)
 # Copied-runtime import checks only: never bind an HTTP port or call inference.
 clean={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'}
 smoke="import pathlib,sys;from app.services.chat_routing import decide;assert pathlib.Path(sys.prefix)==pathlib.Path(sys.argv[1])/'python/.venv';assert decide('What is payment orchestration?').intent=='KNOWLEDGE'"
 cmd([release/'python/.venv/bin/python','-B','-c',smoke,release],cwd=release/'python',env=clean)
 smoke="from dev_server import allowed;assert allowed('GET','/api/v1/merchant/ai/conversations?page=0&size=5');assert allowed('GET','/api/v1/admin/ai/conversations?page=0&size=5')"
 cmd([release/'python/.venv/bin/python','-B','-c',smoke],cwd=front,env=clean)
 external={str(java):digest(java),str(llama):BINARY,str(model):MODEL};pins={};links={}
 for p in release.rglob('*'):
  if p.is_symlink():
   links[str(p.relative_to(release))]=os.readlink(p);target=p.resolve()
   if not target.is_relative_to(release):
    if not target.is_relative_to('/Library/Frameworks/Python.framework/Versions/3.13'):raise Stop('Unreviewed copied runtime symlink.')
    external[str(target)]=digest(target)
  elif p.is_file():pins[str(p.relative_to(release))]=digest(p)
 m.update(publicConfigPins=public_pins,filePins=pins,symlinks=links,externalPins=external,privateAuthenticationConfigurationMatches=True,jwtKeypairMatches=True,modelMetadata={'architecture':'qwen2','name':'qwen2.5-0.5b-instruct','fileType':15,'llamaCommit':'ec7f3ac'},copiedPythonAndProxyImportChecksPass=True)
 if digest(jar)!=JAVA or any(digest(root/k)!=v for k,v in source.items()):raise Stop('Source changed during release copy.')
 (release/'release-manifest.json').write_text(json.dumps(m,indent=2)+'\n');os.chmod(release/'release-manifest.json',0o600)
 print('STAGED_NOT_FROZEN_NOT_ACTIVATED '+str(release))
 return release
if __name__=='__main__':
 if sys.argv[1:]!=['--stage-only']:raise SystemExit('Use --stage-only. No service start is implemented by this preparer.')
 try:stage()
 except (Exception,KeyboardInterrupt):print('PREPARATION_STOPPED; preserve any partial new bundle; no services started.',file=sys.stderr);raise SystemExit(1)
