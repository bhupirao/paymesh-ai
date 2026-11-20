# Controlled Docker Hub v1.0.0 publication

Status: PREPARED, NOT PUBLISHED. No workflow was dispatched during this review.

## Verified release and destinations

Approved application source: `cefa7df83a5bf16d011e82041c95e2d93b9c637b`.
[Disposable E2E run 44652430877](https://github.com/bhupirao/paymesh-ai/actions/runs/44652430877)
completed successfully on that commit. Its logs contain all eight stage pass
markers, `E2E_VERIFY_QWEN: true` and `DISPOSABLE_CONTAINER_API_E2E_PASS`.
The checked-in E2E contract requires successful RAG_LLM generation for both roles
and saved-message generation when this flag is true. The complete isolated Java
suite separately passed 415 tests. Native browser testing is a separate scope.

Publish exactly these four linux/amd64 images:

- `bhupirao/paymesh-java:v1.0.0`
- `bhupirao/paymesh-python:v1.0.0`
- `bhupirao/paymesh-frontend:v1.0.0`
- `bhupirao/paymesh-llama:v1.0.0`

The publication workflow revision and application source revision are intentionally
separate: the reviewed workflow adds release gates, while image jobs check out the
full tested application SHA, even if main subsequently advances. Each checkout is
verified before building. Build-only mode still builds the dispatched revision.
Publishing another namespace, tag or source requires a separately reviewed gate
change; a checkbox alone cannot authorize it.

## Blockers observed during preparation

GitHub environment enumeration succeeded and listed only `container-build-only`.
`dockerhub-publication` does not exist. Repository secret enumeration succeeded
and returned no secrets. No credentials were read, created or configured. Docker
Hub access rights, tag availability and registry settings remain operator checks.

## Operator configuration (no credentials in source or terminal output)

1. Review the preparation diff and approve its normal GitHub push separately.
2. In repository Settings → Environments, create `dockerhub-publication`.
3. Add a required reviewer. Prevent self-review if a second authorized reviewer is
   available; disable administrator bypass where supported. If the account plan
   cannot enforce required reviewers, STOP: this gate must not be bypassed.
4. Select custom deployment branch policies and add exactly one policy: branch
   `main`. Do not allow tags, wildcard patterns or additional branches.
5. Add **environment secrets**, not repository credentials:
   `DOCKERHUB_USERNAME` = `bhupirao`, and `DOCKERHUB_TOKEN` = a Docker Hub access
   token with read/write permission to the four repositories. Do not grant delete
   permission. Enter its value only through GitHub's secret UI.
6. Confirm repository ownership/visibility and that `v1.0.0` is unused. Configure
   immutable release tags in Docker Hub where available. Do not overwrite a
   previously published release; request a separately approved version instead.
7. Recheck these settings immediately before approval. The read-only workflow gate
   rejects a missing reviewer, wrong branch policy or unsuccessful/mismatched E2E
   run before registry login. Secret presence and username are checked without
   printing values. GitHub enforces the environment approval before image jobs run.

See [GitHub environment protections](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
for plan-dependent reviewer availability. A protected environment's name alone is
not approval protection.

## Publication procedure — requires separate operator approval

After the reviewed workflow changes are on main and all blockers above are cleared:

1. Open [Container images workflow](https://github.com/bhupirao/paymesh-ai/actions/workflows/container-images.yml).
2. Select **Run workflow**, branch **main**; inspect the workflow revision.
3. Enter `namespace=bhupirao`, `tag=v1.0.0`, `publish_images=true` and
   `disposable_e2e_verified=true`. These inputs initiate publication, so do not
   submit them until publication itself is explicitly approved.
4. Confirm validation pins image source to `cefa7df83a5bf16d011e82041c95e2d93b9c637b`
   and checks E2E run `44652430877` through GitHub's read-only API.
5. Review and approve the protected `dockerhub-publication` deployment jobs.
   The four image matrix jobs run sequentially; required reviews may be presented
   separately. Do not approve an unexpected source, destination or workflow revision.
6. Require success for all four jobs and their post-push verification steps.
   Each step compares the registry tag's digest with Buildx's emitted digest,
   pulls by that immutable digest on the hosted runner, checks amd64 architecture
   and the source revision label, and records the reference in the job summary.
7. Save all four verified digest references from the summaries. Deployment should
   use `bhupirao/paymesh-<component>@sha256:<verified-digest>`, not rely solely on
   a mutable version tag. Do not invent digest values before publication.

For a build-only rehearsal, use the same namespace/tag but set both booleans false.
This neither logs into Docker Hub nor publishes images. It builds the dispatched
workflow revision, not necessarily the approved release application SHA.

## Contents and limitations

The reviewed Dockerfiles copy application source/dependencies, static assets and
the pinned llama.cpp server binary. They do not copy protected host settings, local
PostgreSQL data, backups or Qwen weights. Secrets are runtime file mounts; Qwen is
a separate read-only model mount. A heuristic security scan of 345 relevant input
files at the approved source found no findings. This is not a post-build filesystem
or vulnerability attestation. Provenance remains minimal and SBOM remains disabled.

Publication rebuilds the tested source; mutable base-image tags and package
repositories mean byte-identical E2E image artifacts are not guaranteed. Registry
pull/digest checks prove published artifact identity, not a new container E2E run.
All builds and pulls remain on hosted runners; no Docker/model downloads on the Mac.

Registry publication is not atomic across four repositories. If a job fails after
another image was pushed, report partial publication and preserve its digests.
Do not automatically retry, overwrite tags, delete images or roll back anything.
Resolve the failure and obtain approval for the next action. No database, local
service or backup changes are part of this procedure.

## Offline preparation checks

95 deployment tests passed, including 14 new publication-gate tests. YAML parsing,
all embedded shell syntax, Python syntax, changed-file security checks and diff
checks passed. Java/Python application source was unchanged; their full suites
were not rerun for this preparation. No registry authentication, build or push was
executed here.
