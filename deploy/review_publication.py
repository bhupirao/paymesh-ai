"""Review working files AND staged blobs without writing the source Git index.
Records names, sizes, hashes and fixed categories, never secret matching values.
This is a heuristic review aid, not a guarantee that arbitrary secrets are absent.
"""
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path
from check_publication import findings, ROOT
KEY_MARKER = b'-'*5 + b'BEGIN PRIVATE KEY' + b'-'*5
JAVA_HELPERS = {
 'backend/src/test/java/com/paymesh/backend/security/accounts/AdminPasswordRecoveryIntegrationTest.java',
 'backend/src/test/java/com/paymesh/backend/security/accounts/SessionRecoveryIntegrationTest.java',
}
def digest(data):return hashlib.sha256(data).hexdigest()
def review(path,data):
    codes=findings(Path(path),data)
    if Path(path).suffix in {'.pem','.key','.bin','.ggml','.ckpt','.sqlite','.sqlite3','.zip','.tgz'}:codes.append('EXCLUDED_ARTIFACT')
    if any(part in {'.aws','.ssh','.codex','.config','.docker'} for part in Path(path).parts):codes.append('LOCAL_CONFIGURATION')
    if data.startswith(b'PGDMP') or b'\x00' in data:codes.append('BINARY_REQUIRES_REVIEW')
    # A delimiter alone in a generator is different from a stored key payload.
    payload=bool(re.search(rb'(?:MII[A-Za-z0-9+/]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s*\n[A-Za-z0-9+/]{48,})',data))
    if payload:codes.append('ENCODED_KEY_OR_CERTIFICATE_REVIEW')
    if re.search(rb'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',data):codes.append('LITERAL_JWT_REVIEW')
    reviewed=[]
    if 'PRIVATE_KEY_PATTERN' in codes and not payload:
        if path in JAVA_HELPERS and all(x in data for x in (b'generateKeyPair()',b'getPrivate().getEncoded()',b'Base64.getMimeEncoder')):
            reviewed.append('DYNAMIC_TEST_KEY_DELIMITER')
            codes.remove('PRIVATE_KEY_PATTERN')
        elif path=='deploy/test_container_preparation.py' and data.count(KEY_MARKER)==1 and b"b'"+KEY_MARKER+b"'" in data:
            reviewed.append('SCANNER_DELIMITER_ONLY_FIXTURE')
            codes.remove('PRIVATE_KEY_PATTERN')
    return sorted(set(codes)),reviewed

def run(out):
    out=Path(out).resolve()
    if out.is_relative_to(ROOT):raise SystemExit('Keep review output outside the publication tree')
    out.mkdir(mode=0o700,parents=True,exist_ok=False)
    before=digest((ROOT/'.git/index').read_bytes())
    names=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).split(b'\0')
    records=[];issues=[];accepted=[]
    for raw in sorted(set(names)):
        if not raw:continue
        name=os.fsdecode(raw);p=ROOT/name
        if p.is_symlink() or not p.is_file():issues.append({'file':name,'scope':'working','codes':['NON_REGULAR_PATH']});continue
        data=p.read_bytes();codes,reviewed=review(name,data)
        records.append({'path':name,'bytes':len(data),'sha256':digest(data)})
        if codes:issues.append({'file':name,'scope':'working','codes':codes})
        if reviewed:accepted.append({'file':name,'scope':'working','codes':reviewed})
    staged=0
    for raw in subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT).split(b'\0'):
        if not raw:continue
        meta,path=raw.split(b'\t',1);mode,oid,stage=meta.split();name=os.fsdecode(path);staged+=1
        if mode not in (b'100644',b'100755') or stage!=b'0':issues.append({'file':name,'scope':'index','codes':['NON_REGULAR_OR_CONFLICTED_INDEX']});continue
        data=subprocess.check_output(['git','cat-file','blob',oid],cwd=ROOT);codes,reviewed=review(name,data)
        if codes:issues.append({'file':name,'scope':'index','codes':codes})
        if reviewed:accepted.append({'file':name,'scope':'index','codes':reviewed})
    report={'status':'PASS_HEURISTIC_REVIEW' if not issues else 'BLOCKED','workingFilesReviewed':len(records),'stagedBlobsReviewed':staged,'issues':issues,'reviewedFixtures':accepted,'indexBefore':before,'indexAfter':digest((ROOT/'.git/index').read_bytes()),'sourceIndexWritePerformed':False,'totalBytes':sum(x['bytes'] for x in records),'largestFileBytes':max(x['bytes'] for x in records),'scope':'Every selected working file and every staged blob; focused classification of findings. Not manual line-by-line certification.'}
    for name,data in [('files.json',records),('security-review.json',report)]:
        with os.fdopen(os.open(out/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:json.dump(data,f,indent=2)
    with os.fdopen(os.open(out/'files.tsv',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
        for row in records:f.write(row['sha256']+'\t'+str(row['bytes'])+'\t'+row['path']+'\n')
    print(json.dumps(report,indent=2));return 1 if issues else 0
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();raise SystemExit(run(args.output))
