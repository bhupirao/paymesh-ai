"""Manual hosted-runner frontend candidate only; never logs raw Docker output."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

SOURCE = 'a15410f2eb2c7d987c142fd7e3758eb237c6c70d'
CONTEXT_SHA256 = 'd8ccb142df61fbe71c16bc7f65f761230e0c83e80cd762f9724b34703273c01e'
APP_SHA256 = '9b14131f8959e8bc8a393740ade4c43359243fc685d722c77a501e95e784e61e'
PRESENTATION_SHA256 = '8f1bec53de24ee2d9aa5301d47f11513959cc816071d1ca69467abcca1b78780'
REVISION = 'org.opencontainers.image.revision'
OWNER = 'io.paymesh.frontend-candidate'
DIGEST = r'sha256:[a-f0-9]{64}'
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}')


class Invalid(Exception):
    pass


def require(ok, code):
    if not ok:
        raise Invalid(code)


def command(args, timeout=30):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    require(result.returncode == 0, 'CANDIDATE_COMMAND_FAILED')
    require(len(result.stdout) <= 4_194_304, 'CANDIDATE_OUTPUT_LIMIT')
    return result.stdout


def scope(env=os.environ):
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_OS') == 'Linux'
            and env.get('RUNNER_ENVIRONMENT') == 'github-hosted', 'HOSTED_RUNNER_REQUIRED')
    require(env.get('GITHUB_REPOSITORY') == 'bhupirao/paymesh-ai'
            and env.get('GITHUB_REF') == 'refs/heads/main'
            and env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'MANUAL_MAIN_REQUIRED')
    require(env.get('DOCKER_HOST', '') in ('', 'unix:///var/run/docker.sock'), 'LOCAL_DOCKER_REQUIRED')
    run, attempt = env.get('GITHUB_RUN_ID', ''), env.get('GITHUB_RUN_ATTEMPT', '')
    require(bool(re.fullmatch(r'[0-9]+', run) and re.fullmatch(r'[0-9]+', attempt)), 'RUN_ID_REQUIRED')
    identifier = 'paymesh-frontend-candidate-' + run + '-' + attempt
    return identifier, Path(env['RUNNER_TEMP']).resolve() / identifier


def private(folder):
    stat = folder.lstat()
    require(folder.is_dir() and not folder.is_symlink() and stat.st_uid == os.getuid()
            and stat.st_mode & 0o7777 == 0o700, 'PRIVATE_CANDIDATE_DIRECTORY_REQUIRED')


def evidence(folder, name, value):
    require(name in ('candidate.json', 'cleanup.json'), 'FIXED_EVIDENCE_REQUIRED')
    private(folder)
    raw = json.dumps(value, sort_keys=True, indent=2).encode()
    require(len(raw) <= 8192, 'EVIDENCE_LIMIT')
    with os.fdopen(os.open(folder/name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'wb') as out:
        out.write(raw + b'\n')


def runtime_path(name):
    path = Path(name)
    return name in ('.dockerignore', 'deploy/Dockerfile.frontend', 'deploy/frontend_entry.py',
                    'frontend/index.html', 'frontend/checkout.html') or name.startswith('frontend/assets/') or (
                    path.parent == Path('frontend') and path.suffix == '.py')


def fingerprint(source, files):
    source = source.resolve()
    rows = []
    for name in sorted(files):
        path = source/name
        require(runtime_path(name) and not path.is_symlink() and path.is_file(), 'CONTEXT_FILE_REQUIRED')
        require(path.resolve().is_relative_to(source.resolve())
                and not any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(source)), 'CONTEXT_CONTAINMENT_REQUIRED')
        require(not any(part.startswith('.env') for part in path.relative_to(source).parts)
                and path.suffix.lower() not in ('.pem', '.key', '.gguf', '.dump', '.backup', '.pyc'), 'CONTEXT_SECRET_PATH')
        raw = path.read_bytes()
        require(len(raw) <= 4_194_304 and not SECRET.search(raw), 'CONTEXT_SECURITY_CHECK_FAILED')
        rows.append([name, hashlib.sha256(raw).hexdigest()])
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def validate_image(image, identifier):
    require(image.get('Os') == 'linux' and image.get('Architecture') == 'amd64', 'IMAGE_PLATFORM_MISMATCH')
    require(bool(re.fullmatch(DIGEST, image.get('Id', ''))), 'IMAGE_CONFIG_ID_REQUIRED')
    config = image.get('Config') or {}
    require((config.get('Labels') or {}).get(REVISION) == SOURCE
            and (config.get('Labels') or {}).get(OWNER) == identifier, 'IMAGE_PROVENANCE_MISMATCH')
    require(config.get('User') == '10001:10001' and config.get('Entrypoint') == ['python', '-B', '/app/container_entry.py']
            and not config.get('Volumes'), 'IMAGE_RUNTIME_CONFIG_MISMATCH')
    require(not any(re.search(r'password|secret|token|credential', entry.split('=', 1)[0], re.I)
                    for entry in config.get('Env', [])), 'IMAGE_SECRET_ENVIRONMENT')


def build():
    identifier, folder = scope()
    folder.mkdir(mode=0o700, exist_ok=False)
    private(folder)
    source = Path(os.environ['GITHUB_WORKSPACE']).resolve()/'candidate-source'
    require(source.is_dir() and not source.is_symlink(), 'SOURCE_DIRECTORY_REQUIRED')
    require(command(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip() == SOURCE, 'SOURCE_COMMIT_MISMATCH')
    files = [name for name in command(['git', '-C', str(source), 'ls-files', '-z']).decode().split('\0') if name and runtime_path(name)]
    require(fingerprint(source, files) == CONTEXT_SHA256, 'SOURCE_CONTEXT_MISMATCH')
    app = source/'frontend/assets/js/app.js'
    require(hashlib.sha256(app.read_bytes()).hexdigest() == APP_SHA256, 'SOURCE_BOOTSTRAP_MISMATCH')
    context = folder/'context'
    context.mkdir(mode=0o700)
    for name in files:
        target = context/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/name, target)
    tag = 'paymesh-frontend-candidate:' + identifier
    command(['docker', 'buildx', 'build', '--platform', 'linux/amd64', '--file', str(context/'deploy/Dockerfile.frontend'),
             '--label', REVISION+'='+SOURCE, '--label', OWNER+'='+identifier, '--provenance=false', '--sbom=false',
             '--load', '--tag', tag, str(context)], timeout=600)
    image = json.loads(command(['docker', 'image', 'inspect', tag]))[0]
    validate_image(image, identifier)
    command(['docker', 'create', '--name', identifier, '--label', OWNER+'='+identifier,
             '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', tag])
    for name, image_path, expected, code in (
            ('built-app.js', '/app/assets/js/app.js', APP_SHA256, 'BUILT_BOOTSTRAP_MISMATCH'),
            ('built-presentation.js', '/app/assets/js/chat/presentation.js', PRESENTATION_SHA256, 'BUILT_PRESENTATION_MISMATCH')):
        extracted = folder/name
        command(['docker', 'cp', identifier+':'+image_path, str(extracted)])
        require(extracted.is_file() and not extracted.is_symlink()
                and hashlib.sha256(extracted.read_bytes()).hexdigest() == expected, code)
    archive = folder/'frontend-candidate.tar'
    command(['docker', 'image', 'save', '--output', str(archive), tag], timeout=120)
    archive.chmod(0o600)
    sha = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b''):
            sha.update(chunk)
    evidence(folder, 'candidate.json', {'success': True, 'candidateId': identifier, 'sourceRevision': SOURCE,
             'workflowRevision': os.environ.get('GITHUB_SHA'), 'platform': 'linux/amd64', 'imageTag': tag,
             'imageConfigDigest': image['Id'], 'imageArchiveSha256': sha.hexdigest(), 'registryManifestDigest': None,
             'contextSha256': CONTEXT_SHA256, 'appSha256': APP_SHA256,
             'presentationSha256': PRESENTATION_SHA256, 'published': False,
             'browserTested': False, 'otherApplicationImagesBuilt': False})
    print('FRONTEND_CANDIDATE_BUILT_AND_CONTENT_VERIFIED_NOT_PUBLISHED')


def cleanup():
    identifier, folder = scope()
    if not folder.exists():
        print('NO_CANDIDATE_RESOURCES_CREATED')
        return
    private(folder)
    tag = 'paymesh-frontend-candidate:' + identifier
    ids = command(['docker', 'ps', '-aq', '--filter', 'name=^/'+identifier+'$']).decode().split()
    require(len(ids) <= 1, 'CLEANUP_AMBIGUOUS_CONTAINER')
    if ids:
        container = json.loads(command(['docker', 'inspect', ids[0]]))[0]
        require(container.get('Name') == '/'+identifier and (container['Config'].get('Labels') or {}).get(OWNER) == identifier
                and container['Config']['Image'] == tag and not container.get('Mounts')
                and not container.get('State', {}).get('Running'), 'CLEANUP_FOREIGN_CONTAINER')
        command(['docker', 'container', 'rm', ids[0]])
    images = command(['docker', 'image', 'ls', '--no-trunc', '--quiet', tag]).decode().split()
    require(len(set(images)) <= 1, 'CLEANUP_AMBIGUOUS_IMAGE')
    if images:
        image = json.loads(command(['docker', 'image', 'inspect', tag]))[0]
        validate_image(image, identifier)
        require(image.get('RepoTags') == [tag], 'CLEANUP_SHARED_IMAGE')
        require(not command(['docker', 'ps', '-aq', '--filter', 'ancestor='+image['Id']]).strip(), 'CLEANUP_IMAGE_IN_USE')
        command(['docker', 'image', 'rm', '--no-prune', tag])
    require(not command(['docker', 'ps', '-aq', '--filter', 'name=^/'+identifier+'$']).strip(), 'CLEANUP_CONTAINER_REMAINS')
    require(not command(['docker', 'image', 'ls', '--quiet', tag]).strip(), 'CLEANUP_IMAGE_REMAINS')
    # Only fixed direct leaves inside the validated private run directory.
    for name in ('frontend-candidate.tar', 'built-app.js', 'built-presentation.js'):
        path = folder/name
        if path.exists():
            require(path.is_file() and not path.is_symlink(), 'CLEANUP_UNEXPECTED_FILE')
            path.unlink()
    context = folder/'context'
    if context.exists():
        require(context.is_dir() and not context.is_symlink(), 'CLEANUP_UNEXPECTED_CONTEXT')
        shutil.rmtree(context)
    evidence(folder, 'cleanup.json', {'success': True, 'candidateId': identifier, 'containerAbsent': True,
                                    'candidateImageAbsent': True, 'temporaryPayloadRemoved': True, 'volumesUsed': False})
    print('FRONTEND_CANDIDATE_PROJECT_CLEANUP_PASS')


def main(action):
    try:
        require(action in ('build', 'cleanup'), 'FIXED_ACTION_REQUIRED')
        build() if action == 'build' else cleanup()
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, Invalid) else 'CANDIDATE_OPERATION_UNAVAILABLE'
        code = code if re.fullmatch('[A-Z0-9_]{1,80}', code) else 'CANDIDATE_UNCLASSIFIED_FAILURE'
        try:
            identifier, folder = scope()
            name = 'cleanup.json' if action == 'cleanup' else 'candidate.json'
            if folder.exists() and not (folder/name).exists():
                evidence(folder, name, {'success': False, 'candidateId': identifier, 'failureCode': code})
        except Exception:
            pass  # Never replace the failure with raw diagnostic text.
        print(code)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else ''))
