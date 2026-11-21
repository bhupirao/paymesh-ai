"""Explicit mixed-source browser stack. Never changes the v1.0.0 identity contract."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import browser_bootstrap
import frontend_candidate as candidate
from ci_fixture_setup import prepare
from container_e2e import Suite, require
from release_artifact_e2e import ReleaseSuite, guard, release_lock, validate_image, cleanup_project

COMPOSE = 'deploy/compose.candidate-browser.yaml'
COMPOSE_SHA256 = 'd66379a4d995548da79e95fc5ec0077d04014e9f6752f95f5fbbcef7bee860b4'


def metadata():
    identifier, folder = candidate.scope()
    candidate.private(folder)
    file = folder/'candidate.json'
    stat = file.lstat()
    require(file.is_file() and not file.is_symlink() and stat.st_uid == os.getuid()
            and not stat.st_mode & 0o077 and stat.st_size <= 8192, 'PRIVATE_CANDIDATE_EVIDENCE_REQUIRED')
    value = json.loads(file.read_text())
    require(value.get('success') is True and value.get('candidateId') == identifier
            and value.get('sourceRevision') == candidate.SOURCE
            and value.get('workflowRevision') == os.environ.get('GITHUB_SHA')
            and bool(re.fullmatch('[a-f0-9]{40}', value.get('workflowRevision', '')))
            and value.get('platform') == 'linux/amd64'
            and value.get('imageTag') == 'paymesh-frontend-candidate:'+identifier
            and bool(re.fullmatch(candidate.DIGEST, value.get('imageConfigDigest', '')))
            and bool(re.fullmatch('[a-f0-9]{64}', value.get('imageArchiveSha256', '')))
            and value.get('appSha256') == candidate.APP_SHA256
            and value.get('contextSha256') == candidate.CONTEXT_SHA256
            and value.get('registryManifestDigest') is None and value.get('published') is False
            and value.get('browserTested') is False and value.get('otherApplicationImagesBuilt') is False,
            'CANDIDATE_EVIDENCE_MISMATCH')
    return value


def compose_guard():
    require(hashlib.sha256(Path(COMPOSE).read_bytes()).hexdigest() == COMPOSE_SHA256, 'CANDIDATE_COMPOSE_MISMATCH')


def validate_config(config, value):
    services = config.get('services', {})
    require(set(services) == {'java','python','llama','frontend','postgres'}, 'CANDIDATE_SERVICES_MISMATCH')
    lock = release_lock()
    for name in ('java','python','llama'):
        require(services[name].get('image') == lock['images'][name], 'PUBLISHED_BACKEND_DIGEST_MISMATCH')
    require(services['postgres'].get('image') == 'postgres:16.16-bookworm', 'POSTGRES_VERSION_MISMATCH')
    require(services['frontend'].get('image') == value['imageTag']
            and services['frontend'].get('pull_policy') == 'never', 'CANDIDATE_FRONTEND_REQUIRED')
    require(all(not item.get('build') for item in services.values()), 'STACK_BUILD_FORBIDDEN')


def validate_frontend(container, image, value):
    candidate.validate_image(image, value['candidateId'])
    require(container['Config']['Image'] == value['imageTag']
            and container['Image'] == image['Id'] == value['imageConfigDigest'], 'RUNNING_CANDIDATE_IDENTITY_MISMATCH')


class CandidateSuite(ReleaseSuite):
    def __init__(self):
        guard()
        compose_guard()
        Suite.__init__(self)
        require(Path(os.environ.get('E2E_DIR','')).resolve() == self.folder
                and Path(os.environ.get('E2E_ENV','')).resolve() == self.folder/'container.env', 'FIXTURE_PATH_MISMATCH')
        self.compose[-1] = COMPOSE
        self.lock = release_lock()
        self.candidate = metadata()
        require(os.environ.get('CANDIDATE_FRONTEND_IMAGE') == self.candidate['imageTag']
                and os.environ.get('E2E_FRONTEND_KIND') == 'source-built-candidate', 'CANDIDATE_ENVIRONMENT_MISMATCH')

    def identity(self):
        Suite.identity(self)  # Existing five-service health, loopback and volume checks.
        config = json.loads(self.command(self.compose+['config','--format','json']))
        validate_config(config, self.candidate)
        ids = self.command(self.compose+['ps','-q']).decode().split()
        states = json.loads(self.command(['docker','inspect',*ids]))
        require(len(states) == 5 and {c['Config']['Labels']['com.docker.compose.service'] for c in states}
                == {'java','python','llama','frontend','postgres'}, 'SERVICE_SET_MISMATCH')
        for container in states:
            service = container['Config']['Labels']['com.docker.compose.service']
            if service == 'postgres':
                require(container['Config']['Image'] == 'postgres:16.16-bookworm'
                        and not container['HostConfig'].get('PortBindings'), 'DATABASE_EXPOSURE_OR_VERSION')
                continue
            ref = self.candidate['imageTag'] if service == 'frontend' else self.lock['images'][service]
            images = json.loads(self.command(['docker','image','inspect',ref]))
            require(len(images) == 1, 'IMAGE_INSPECT_MISMATCH')
            if service == 'frontend':validate_frontend(container, images[0], self.candidate)
            else:validate_image(container, images[0], service, self.lock)
        candidate.evidence(self.folder, 'candidate.json', {
            'success':True,'frontendArtifactKind':'source-built-candidate','publishedImagesOnly':False,
            'frontendConfigDigest':self.candidate['imageConfigDigest'],
            'frontendSource':candidate.SOURCE,'frontendRegistryManifestDigest':None,
            'publishedBackends':{name:self.lock['images'][name] for name in ('java','python','llama')},
            'fiveServicesHealthy':True,'browserTested':False})


def main(action):
    try:
        project = guard()
        compose_guard()
        if action == 'fixtures':
            value = metadata()
            image = json.loads(candidate.command(['docker','image','inspect',value['imageTag']]))[0]
            candidate.validate_image(image, value['candidateId'])
            require(image['Id'] == value['imageConfigDigest'], 'CANDIDATE_LOCAL_IMAGE_CHANGED')
            prepare()
            with open(os.environ['GITHUB_ENV'],'a') as out:
                out.write('CANDIDATE_FRONTEND_IMAGE='+value['imageTag']+'\nE2E_FRONTEND_KIND=source-built-candidate\n')
            return 0
        if action in ('seed','final'):
            return browser_bootstrap.verify(CandidateSuite(), action, candidate=True)
        folder = Path(os.environ['RUNNER_TEMP']).resolve()/project
        require(os.environ.get('E2E_PROJECT') == project and Path(os.environ.get('E2E_DIR','')).resolve() == folder
                and Path(os.environ.get('E2E_ENV','')).resolve() == folder/'container.env', 'CANDIDATE_PATH_MISMATCH')
        value = metadata()
        require(os.environ.get('CANDIDATE_FRONTEND_IMAGE') == value['imageTag'], 'CANDIDATE_ENVIRONMENT_MISMATCH')
        if action == 'diagnostics':
            from capture_failure_diagnostics import collect
            collect(COMPOSE)
            return 0
        if action == 'cleanup':
            return cleanup_project(project, folder, compose_file=COMPOSE,
                                   validate_config=lambda config:validate_config(config,value))
        raise ValueError('FIXED_ACTION_REQUIRED')
    except Exception:
        print('CANDIDATE_BROWSER_GUARD_OR_OPERATION_FAILED_NO_RAW_OUTPUT')
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else ''))
