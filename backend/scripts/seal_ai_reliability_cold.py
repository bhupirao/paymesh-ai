"""Operator-assisted READ ONLY baseline comparison and immutable release sealing.
No backup, restore, application start, inference or credential persistence.
"""
import getpass,json,os,stat,sys,tempfile,time,warnings
from pathlib import Path
from phase673_otp_ops import Stop,protected
from ai_reliability_forward import digest
from ai_reliability_cold import Cold,empty_ports

def seal(path):
 private=protected(Path.home()/'.config/paymesh-demo',0o700);release=Path(path).resolve()
 if not release.is_relative_to(private) or not release.name.startswith('ai-reliability-cold-release-'):raise Stop('Unexpected release path.')
 protected(release,0o700);manifest=protected(release/'release-manifest.json');m=json.loads(manifest.read_text())
 if m.get('privateDatabaseVerificationAttempted'):raise Stop('A private authentication attempt already occurred; no automatic retry.')
 if not sys.stdin.isatty() or not sys.stdout.isatty():raise Stop('Use the operator Terminal for private /dev/tty input.')
 empty_ports()
 for name,sha in m['filePins'].items():
  if digest(release/name)!=sha:raise Stop('Staged release changed.')
 for name,sha in m['protectedConfigPins'].items():
  if digest(protected(Path(name)))!=sha:raise Stop('Protected configuration changed.')
 for name,sha in m['externalPins'].items():
  if digest(Path(name))!=sha:raise Stop('Pinned runtime/model changed.')
 if digest(protected(Path(m['backup']['path'])))!=m['backup']['sha256'] or digest(protected(Path(m['backupEvidence'])))!=m['backupEvidenceSha256']:raise Stop('Verified backup/evidence changed.')
 m['privateDatabaseVerificationAttempted']=True;manifest.write_text(json.dumps(m,indent=2)+'\n')
 print('Preparation only: read-only baseline comparison, then immutable sealing. No services will start.')
 with open('/dev/tty','w') as tty,warnings.catch_warnings():
  warnings.simplefilter('error',getpass.GetPassWarning)
  password=getpass.getpass('PostgreSQL password for paymesh_demo_user (not saved): ',stream=tty)
 if not password:raise Stop('Empty password; no connection attempted.')
 sys.path.insert(0,str(release/'ops'));from v14_backup_reader import snapshot
 data=snapshot(password);password=None
 if data['history']!=m['migrationHistory'] or data['fingerprints']!=m['databaseBaseline']['fingerprints'] or data['counts']!=m['databaseBaseline']['tableCounts']:raise Stop('V14 history or protected baseline changed; stop for review.')
 empty_ports()
 m.update(status='PREPARED_FROZEN_NOT_STARTED',databaseBaselineVerified=True,databaseBaselineVerifiedAtUtc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),gitIndexAfter=digest(Path.home()/'Developer/paymesh-ai/.git/index'))
 manifest.write_text(json.dumps(m,indent=2)+'\n')
 for p in sorted(release.rglob('*'),key=lambda x:len(x.parts),reverse=True):
  if p.is_symlink():continue
  p.chmod(0o500 if p.is_dir() else 0o400);os.chflags(p,stat.UF_IMMUTABLE)
 release.chmod(0o500);os.chflags(release,stat.UF_IMMUTABLE)
 Cold(release).check()
 folder=Path(tempfile.mkdtemp(prefix='ai-cold-release-preparation-',dir=private));os.chmod(folder,0o700)
 e={'success':True,'status':m['status'],'releaseDirectory':str(release),'manifestSha256':digest(manifest),'databaseBaselineVerified':True,'privateAuthenticationConfigurationMatches':m['privateAuthenticationConfigurationMatches'],'copiedRuntimeImportsPass':True,'backupChecksumVerified':True,'javaSha256':m['javaSha256'],'pythonManifestSha256':m['pythonManifestSha256'],'userImmutable':True,'servicesStarted':False,'inferencePerformed':False,'databaseWrites':False,'backupOrRestorePerformed':False,'gitIndexBefore':m['gitIndexBefore'],'gitIndexAfter':m['gitIndexAfter']}
 e['gitIndexUnchanged']=e['gitIndexBefore']==e['gitIndexAfter']
 with os.fdopen(os.open(folder/'evidence.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:json.dump(e,out,indent=2)
 print('FROZEN_COLD_RELEASE_PREPARED_NO_SERVICES_STARTED')
 print('Frozen release: '+str(release));print('Release manifest SHA-256: '+e['manifestSha256']);print('Protected evidence: '+str(folder/'evidence.json'))
if __name__=='__main__':
 try:
  if len(sys.argv)!=2:raise Stop('Expected protected staged release directory.')
  seal(sys.argv[1])
 except (Exception,KeyboardInterrupt):print('PREPARATION_STOPPED_NO_RETRY; retain staged bundle; no services started.',file=sys.stderr);sys.exit(1)
