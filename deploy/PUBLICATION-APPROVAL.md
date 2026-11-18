# Initial publication approval — v1.0.0

Confirmed source destination: https://github.com/bhupirao/paymesh-ai.git, main.
Confirmed image destinations (separate approval later):

- bhupirao/paymesh-java:v1.0.0
- bhupirao/paymesh-python:v1.0.0
- bhupirao/paymesh-frontend:v1.0.0
- bhupirao/paymesh-llama:v1.0.0

No source push, image publication or live service operation is approved by this
file. The main branch did not exist remotely at read-only inspection. Recheck it
before pushing; never force-push or replace an unexpected branch.

## Commit candidate

An initial main commit is prepared in a separate temporary bare Git repository.
It uses the complete reviewed WORKING versions, not stale staged versions. Exact
paths and SHA-256 are in files.tsv/files.json in the external publication review
directory identified in the handoff. This source checkout's branch and mixed index
remain untouched. No source files are copied into a second worktree; Git objects
provide a small frozen candidate. The review output is not included in the commit.

Proposed message: `Initial PayMesh AI release with isolated container deployment`.
Includes application source/tests, V1–V14 migrations, vendored licenses/assets,
phase documentation, Docker configuration and workflows. Excludes credentials,
model weights, venv/build outputs, protected runtime state, backups and archives.
Historical phase reports retain their original evidence limitations; newer operator
browser-test confirmations are not retroactively claimed as automated evidence.

Existing staged blobs were scanned separately. The Java PEM markers are dynamic
in-memory key-generation helpers, not embedded PEM payloads. The scanner fixture
contains only a delimiter. Additional assignment-pattern findings were secure-input
placeholders and a validation message. Classifications do not blanket-ignore test
files: unknown key payloads, tokens or artifacts must still block publication.
Full-tree heuristic scanning is not a claim of manual line-by-line review or a
formal guarantee that no secret can exist.

## Approval boundary

Review the exact candidate hash and files.tsv first. Approval should name:
`Approve publishing candidate COMMIT to bhupirao/paymesh-ai main`.
Only then push that exact candidate (without force) from the isolated repository.
Do not stage/commit the existing mixed source index blindly. Attaching this source
checkout to the published commit can be reviewed separately without discarding any
staged changes. A temporary candidate must be retained until publication completes.

Git authentication, if needed, uses Git credential handling/private prompts. Never
put a personal access token in the origin URL or command arguments.

## Build-only Actions run after approved source push

GitHub web alternative (no local gh or Docker required):
https://github.com/bhupirao/paymesh-ai/actions/workflows/container-images.yml

Select Run workflow, main, namespace bhupirao, tag v1.0.0, publish_images=false,
disposable_e2e_verified=false. This builds four amd64 images on remote runners and
validates Compose; it does not claim container E2E or upload images to Docker Hub.
The existing backend CI also runs on source push; it builds/tests remotely without
publishing registry images. Required GitHub plan/Actions availability is not assumed.

Before later Docker Hub publication configure the dockerhub-publication environment
with required reviewers, scoped DOCKERHUB_USERNAME/DOCKERHUB_TOKEN secrets, and verify
actual disposable-container E2E. Any registry publication requires a new explicit
approval with exact namespace/tags/digests. No real/local database is used by these
container build commands. Models are not in Git, images or CI download steps.
