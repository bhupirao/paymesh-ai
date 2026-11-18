"""Preparation only: snapshots verified NEW artifacts; never starts/stops a service.

One read-only V14 metadata transaction; no backup, restore, model calls or app APIs.
"""
import hashlib,json,os,shutil,stat,subprocess,sys,tempfile,time,zipfile,zlib
from pathlib import Path
from phase673_otp_ops import Stop,protected
from phase697a_process import MacOS,snapshot,assert_same
from phase697a_diagnostic import credentials,read_sink
from ai_reliability_forward import env_digest,Forward
JAVA_SHA='6f6a2e27659ff338fb01163819a1a8cf2112d694e579515e7d64256eac0d96ba'
PY_SHA='9ef4ccc9e6ed7a989eea1d924f2ddcbffa93e124ce0b63cb9598dbb481f68006'
EXPECTED={'java':[43617,1794882016,867215,501],'ai':[53060,1794939639,206098,501],'frontend':[56916,1794968084,702544,501],'llm':[79855,1794629619,200196,501]}
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def command(args,env=None,data=None):
 r=subprocess.run([str(a) for a in args],capture_output=True,input=data,env=env)
 if r.returncode:raise Stop('Preparation check failed; no service changes performed.')
 return r.stdout

def prepare():
 root=Path(__file__).resolve().parents[2];private=protected(Path.home()/'.config/paymesh-demo',0o700)
 before=digest(root/'.git/index');native=MacOS();services={};saved={}
 specs={'java':(18080,root/'backend'),'ai':(8000,root/'ai-service'),'frontend':(5500,root),'llm':(8082,Path.home()/'Developer/paymesh-tools/llama.cpp')}
 for name,(port,cwd) in specs.items():
  lines=command(['/usr/sbin/lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-Fpn']).decode().splitlines()
  if [x for x in lines if x.startswith('p')]!=['p'+str(EXPECTED[name][0])] or [x for x in lines if x.startswith('n')]!=['n127.0.0.1:'+str(port)]:raise Stop('Unexpected listener; stop preparation.')
  s=snapshot(EXPECTED[name][0],native);saved[name]=s
  if list(s.identity)!=EXPECTED[name]:raise Stop('Native process identity changed.')
  actual=command(['/usr/sbin/lsof','-a','-p',str(s.identity[0]),'-d','cwd','-Fn']).decode().splitlines()
  if [x[1:] for x in actual if x.startswith('n')]!=[str(cwd)]:raise Stop('Working directory changed.')
  services[name]={'identity':list(s.identity),'port':port,'cwd':str(cwd),'argvDigest':hashlib.sha256(json.dumps(s.argv).encode()).hexdigest(),'environmentDigest':env_digest(s.environment)}
 java=saved['java'];python=saved['ai'];sink=Path(python.environment['PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE'])
 credentials(python,java,private,sink);read_sink(sink,private)
 if (root/'ai-service/.env').exists() or any(python.environment.get(k) for k in ('PYTHONPATH','PYTHONHOME')):raise Stop('Unexpected Python configuration/import override.')
 jar=root/'backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar'
 if digest(jar)!=JAVA_SHA:raise Stop('Approved Java artifact differs.')
 paths=[*sorted((root/'ai-service/app').rglob('*.py')),*sorted((root/'ai-service/app').rglob('*.json')),*sorted((root/'ai-service/knowledge_base').glob('*.md')),root/'ai-service/requirements.txt']
 if any(p.is_symlink() for p in paths):raise Stop('Source symlinks are unreviewed.')
 sources={str(p.relative_to(root)):digest(p) for p in paths}
 if len(sources)!=40 or hashlib.sha256(json.dumps(sources,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=PY_SHA:raise Stop('Approved Python source manifest differs.')
 config={}
 for arg in java.argv:
  if arg.startswith(('--spring.config.location=','--spring.config.additional-location=')):
   for location in arg.split('=',1)[1].split(','):
    if location=='classpath:/application.properties':continue
    if not location.startswith('file:'):raise Stop('Unreviewed configuration location.')
    p=protected(Path(location[5:]));config[str(p)]=digest(p)
 with zipfile.ZipFile(jar) as z:
  history=[]
  for version in range(1,15):
   matches=[n for n in z.namelist() if n.startswith(f'BOOT-INF/classes/db/migration/V{version}__')]
   if len(matches)!=1:raise Stop('Migration inventory differs.')
   crc=0
   for line in z.read(matches[0]).decode('utf-8-sig').splitlines():crc=zlib.crc32(line.encode(),crc)
   history.append({'version':str(version),'checksum':crc if crc<2**31 else crc-2**32,'success':True})
  if z.read('BOOT-INF/classes/ai-chat/contract.json')!=(root/'backend/src/main/resources/ai-chat/contract.json').read_bytes():raise Stop('Java/Python contract build differs.')
 # Fresh metadata verification only. No table content, account or conversation reads.
 env={'PATH':'/usr/bin:/bin','PGPASSWORD':java.environment['PAYMESH_DB_PASSWORD'],'PGCONNECT_TIMEOUT':'5','PGOPTIONS':'-c default_transaction_read_only=on -c statement_timeout=5000'}
 sql="""BEGIN READ ONLY;
DO $$BEGIN IF current_database()<>'paymesh_demo' OR current_user<>'paymesh_demo_user' OR inet_server_addr()<>'127.0.0.1'::inet OR inet_server_port()<>5432 OR current_setting('transaction_read_only')<>'on' THEN RAISE EXCEPTION 'identity'; END IF; END$$;
SELECT json_agg(json_build_object('version',version,'checksum',checksum,'success',success) ORDER BY installed_rank) FROM public.flyway_schema_history;
ROLLBACK;"""
 actual=json.loads(command(['/Library/PostgreSQL/16/bin/psql','-X','-w','-h','127.0.0.1','-p','5432','-U','paymesh_demo_user','-d','paymesh_demo','-Atq','-v','ON_ERROR_STOP=1'],env=env,data=sql.encode()).decode())
 if actual!=history:raise Stop('Live migration history does not match reviewed V14; no migration authorized.')
 pg=command(['/bin/ps','-p','148','-o','pid=,ppid=,uid=,lstart=,comm=']).decode().strip()
 if '/Library/PostgreSQL/16/bin/postgres' not in pg:raise Stop('PostgreSQL OS metadata differs.')
 release=Path(tempfile.mkdtemp(prefix='ai-reliability-forward-',dir=private));os.chmod(release,0o700)
 (release/'java').mkdir();shutil.copyfile(jar,release/'java/paymesh.jar')
 for p in paths:
  dst=release/'python'/p.relative_to(root/'ai-service');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
 shutil.copytree(root/'ai-service/.venv',release/'python/.venv',symlinks=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 ops=release/'ops';ops.mkdir()
 for name in ('ai_reliability_forward.py','ai_reliability_python_launch.py','phase697a_process.py','phase697a_diagnostic.py','phase673_otp_ops.py'):
  shutil.copyfile(root/'backend/scripts'/name,ops/name)
 external={java.executable:digest(Path(java.executable)),str(Path(python.executable)):digest(Path(python.executable))}
 filepins={};links={}
 for p in sorted(release.rglob('*')):
  if p.is_symlink():
   links[str(p.relative_to(release))]=os.readlink(p);target=p.resolve()
   if not target.is_relative_to(release):
    if not target.is_relative_to('/Library/Frameworks/Python.framework/Versions/3.13'):raise Stop('Unreviewed external release link.')
    external[str(target)]=digest(target)
  elif p.is_file():filepins[str(p.relative_to(release))]=digest(p)
 if filepins['java/paymesh.jar']!=JAVA_SHA or any(digest(root/n)!=sha for n,sha in sources.items()):raise Stop('Source/artifact changed during copy.')
 manifest={'status':'PREPARED_NOT_ACTIVATED','preparedAtUtc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'trueRollbackAvailable':False,'postgresExceptionAccepted':True,'postgresRisk':'wildcard5432/TLS-off/HBA-and-filtering-unverified; unchanged','javaSha256':JAVA_SHA,'pythonSourceManifestSha256':PY_SHA,'pythonSourcePins':sources,'services':services,'postgresOsIdentity':pg,'migrationHistory':history,'privateAuthenticationConfigurationMatches':True,'databaseBackupPerformed':False,'testRestorePerformed':False,'filePins':filepins,'symlinks':links,'externalPins':external,'protectedConfigPins':config,'gitIndexBefore':before,'gitIndexAfter':digest(root/'.git/index')}
 m=release/'release-manifest.json';m.write_text(json.dumps(manifest,indent=2)+'\n')
 # Check import provenance using the copied runtime, no protected credentials or app calls.
 smoke="import pathlib,sys; from app.services.chat_routing import decide; assert pathlib.Path(sys.prefix)==pathlib.Path(sys.argv[1])/'python/.venv'; assert decide('What is payment orchestration?').intent=='KNOWLEDGE'; print('COPIED_RUNTIME_IMPORT_PASS')"
 # subprocess cwd is essential: import only the copied app, never the workspace app.
 result=subprocess.run([str(release/'python/.venv/bin/python'),'-B','-c',smoke,str(release)],cwd=release/'python',env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True)
 if result.returncode:raise Stop('Copied Python runtime import check failed; bundle retained for review.')
 for s in saved.values():assert_same(s,native)
 if command(['/bin/ps','-p','148','-o','pid=,ppid=,uid=,lstart=,comm=']).decode().strip()!=pg:raise Stop('PostgreSQL OS identity changed.')
 for p in sorted(release.rglob('*'),key=lambda x:len(x.parts),reverse=True):
  if p.is_symlink():continue
  p.chmod(0o500 if p.is_dir() else 0o400);os.chflags(p,stat.UF_IMMUTABLE)
 release.chmod(0o500);os.chflags(release,stat.UF_IMMUTABLE)
 # This performs file-pin checks only; it cannot stop/start services or call the database.
 Forward(release).check()
 print(json.dumps({'status':'PREPARED_NOT_ACTIVATED','releaseDirectory':str(release),'manifestSha256':digest(m),'payloadFiles':len(filepins),'pythonFileCount':len(sources),'privateAuthenticationMatches':True,'v14ChecksumsMatch':True,'copiedRuntimeImportPass':True,'userImmutable':bool(release.stat().st_flags&stat.UF_IMMUTABLE),'gitIndexUnchanged':digest(root/'.git/index')==before}))
 return release
if __name__=='__main__':
 if sys.argv[1:]!=['--prepare-only']:raise SystemExit('Preparation requires --prepare-only; no activation is implemented here.')
 try:prepare()
 except (Exception,KeyboardInterrupt):print('PREPARATION_BLOCKED; no service activation performed; retain any partial protected bundle.',file=sys.stderr);raise SystemExit(1)
