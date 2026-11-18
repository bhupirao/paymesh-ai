"""Read-only pre-publication tripwire. Reports names/categories, never matching text.
Heuristics cannot certify absence of secrets; review findings before publishing.
"""
import json, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BLOCKED = {'.gguf','.safetensors','.onnx','.dump','.pgdump','.backup','.p12','.pfx','.jks','.keystore'}
def findings(path, data):
    result=[]
    if len(data)>10*1024*1024: result.append('OVER_10_MIB')
    if path.suffix.lower() in BLOCKED:result.append('PRIVATE_OR_LARGE_ARTIFACT')
    if path.name.startswith('.env') and path.name!='.env.example':result.append('ENVIRONMENT_FILE')
    if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data):result.append('PRIVATE_KEY_PATTERN')
    if re.search(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16}|dckr_pat_[A-Za-z0-9_-]{20,})',data):result.append('ACCESS_TOKEN_PATTERN')
    if any(p in ('.venv','venv','target','__pycache__') for p in path.parts):result.append('GENERATED_DIRECTORY')
    return result

def main():
    paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).split(b'\0')
    results=[];checked=0
    for item in sorted(set(paths)):
        if not item:continue
        relative=Path(item.decode());p=ROOT/relative
        if not p.is_file() or p.is_symlink():continue
        checked+=1
        if p.stat().st_size>10*1024*1024:codes=['OVER_10_MIB']
        else:codes=findings(relative,p.read_bytes())
        if codes:results.append({'file':str(relative),'categories':codes})
    print(json.dumps({'filesChecked':checked,'findings':results,'scope':'index paths + working tree; staged blobs/history require separate review','notASecretSafetyCertification':True},indent=2))
    return 1 if results else 0
if __name__=='__main__':raise SystemExit(main())
