# PayMesh isolated containers and image publication

Status: remote builds and all **eight disposable container API E2E stages passed**
in [run 44652430877](https://github.com/bhupirao/paymesh-ai/actions/runs/44652430877)
on source `cefa7df83a5bf16d011e82041c95e2d93b9c637b`. Actual Qwen inference was
verified with `modelInferenceRequested=true` and `modelInferenceVerified=true`.
The complete isolated Java suite separately passed **415 tests**. These are
recorded results, not newly rerun application suites for this readiness update.
All four v1.0.0 images are now public. Three native Chromium tests and ten journey
stages passed in [run 44877848710](https://github.com/bhupirao/paymesh-ai/actions/runs/44877848710),
using the corrected source-built frontend with unchanged published backends.
**Frontend v1.0.1 is prepared, not published.** See [release evidence](RELEASE-EVIDENCE.md),
[frontend-only publication](FRONTEND-V1.0.1-RELEASE.md) and [synthetic demo](PORTFOLIO-DEMO.md).

Repository: `bhupirao/paymesh-ai`, branch `main`. The GitHub repository is public. New image publication requires separate explicit approval. Docker, Colima/Podman and
GitHub CLI remain unavailable on the inspected Mac; builds/E2E run on GitHub-hosted
Linux runners without attaching local PostgreSQL data, protected files or models.

## Architecture

Five linux/amd64 services: Java 21, Python FastAPI, PostgreSQL 16, llama.cpp b4514
(ec7f3ac9ab33e46b136eb5ab6a76c4d81f57c7f1), and the existing frontend/proxy.
Multi-stage Java/Python/llama builds ship runtime artifacts only. Frontend requires
only Python's standard library. Qwen2.5 model weights are NOT included in any image.
The existing single GGUF is bind-mounted read-only, without copying/downloading it.
The llama context excludes local build directories, Git objects and model files.

Java/Python/llama/frontend share Java's network namespace to preserve existing
loopback-only AI validation and the fixed frontend upstream. PostgreSQL has its own
private internal-network endpoint and a NEW named volume `paymesh-containers_container_pgdata`.
The shared application namespace also uses an edge bridge for host port publication;
PostgreSQL remains attached only to the internal database network.
No database port is published. No host PostgreSQL URL, data directory or volume is
mounted. Flyway V1–V14 applies ONLY to this new disposable container database; host
Flyway/configuration/data is untouched. Do not import host dumps or credentials.
Only frontend port **127.0.0.1:15500** is published (local host services remain on
5500/18080/8000/8082). Compose defines five health checks; the hosted disposable API E2E verified
container health and API workflows. The original API E2E is distinct from the later corrected-candidate Chromium evidence linked above.

Local HTTP cookie policy is preserved, not relaxed: Java uses development profile,
loopback 18080 and its existing fixed port-5500 Origin. The container edge checks
Host/Origin against port15500 using the existing handler, then translates only an
already validated Origin to the private fixed Java Origin. A second explicit check
rejects hostile/duplicate Origins before forwarding. CSRF headers, auth-cookie
allowlist, checkout cookie stripping, CSP, safe logging and endpoint catalogs are
reused. This adapter is for private local development, not arbitrary public hosting.
Public HTTPS ingress needs its own reviewed deployment configuration.

Chat/inference defaults OFF. RAG_ASSISTED knowledge/investigation configuration is
available; enabling Qwen requires both `CHAT_ENABLED=true` and `ANALYSIS_MODE=RAG_LLM`
in the NEW external container environment, not the host configuration. No inference
is performed by startup or the metadata smoke tool. Demo OTP, gateway timeout and
checkout fault controls and settlement/retention scheduling stay disabled.

## Storage and runtime prerequisites

Measured free space: approximately **13 GiB** before and after source preparation.
No cleanup or image/model downloads occurred. Measured existing directories:
Maven repository1.5GiB, host caches2.9GiB, model469MiB (one GGUF), ai-service venv47MiB,
Java target66MiB, llama local build25MiB, protected demo releases/backups271MiB.
These are NOT deletion approvals. Protected artifacts and models are never cleanup
candidates. No Docker cache exists to measure without a Docker installation.

First-build planning estimate: **6–10 GiB additional**, possibly more for base
layers/toolchains/caches/VM; this is not a measured image size. `build.sh` requires
at least16GiB free as conservative headroom. With13GiB free, prefer remote GitHub
Actions builds. They download/build source on ephemeral runners, never a second
model on this Mac. Remote builds do not remove the need for a local Linux runtime
and disk space to pull/test images. Image pulls alone may require roughly1–3GiB;
verify real registry sizes after the first successful build.

For an open-source Intel-compatible runtime, Colima supports an x86_64 Linux VM
and configurable CPU/memory/disk. See https://github.com/abiosoft/colima . After a
separately reviewed installation, an example limited VM is:

```sh
colima start --cpu 2 --memory 3 --disk 16
```

The disk setting is VM capacity, not proof that16GiB physical space is available.
Service memory limits total about2.2GiB; allow VM overhead. Running both existing
local AI and container AI concurrently may cause memory pressure on8GiB RAM.
Do not stop local services automatically to compensate. Do not start/build a VM
until its installation and disk budget are acceptable.

## External configuration (never reuse host runtime secrets)

1. Copy `container.env.example` OUTSIDE Git to a new private file and replace paths,
   Docker Hub namespace and reviewed tag. Do not overwrite existing protected files.
2. Supply a NEW container-only directory with db_password, ai_token, razorpay_secret,
   stripe_secret, settlement_token, jwt_private (PKCS#8 RSA) and jwt_public (X.509).
   Shared ai_token must be64–128 URL-safe characters. PostgreSQL and Java share the
   db_password file. Java/Python share ai_token. Never include values in CLI args.
3. Parent secret directory must be private (0700). Confirm the NEW mounted files
   are readable by container UID10001 and PostgreSQL's entrypoint without changing
   existing host credentials. Compose file-backed secret uid/mode remapping is not
   portable; do not assume it fixes a host0600 file owned by another UID. One local
   approach is dedicated read-only0444 files INSIDE the private0700 source directory,
   never reusable secrets in a public/shared directory. Validate mounted permissions
   in the disposable stack. See Docker Compose secret documentation.
4. Keep the exact existing model file and reviewed llama source path in configuration.
   No model is automatically fetched. Containers do not need your host DB password.

Never show `docker inspect` environment output, raw logs or secret contents publicly.
Spring configtree mounts secrets at runtime; neither build args nor image layers
contain these values. Application tokens exist only in the Python process environment.

## Commands after prerequisites and destination approval

Set values to the actual reviewed paths; the following commands are NOT yet run:

```sh
export PAYMESH_CONTAINER_ENV_FILE="$HOME/.config/paymesh-containers/container.env"
export LLAMA_CPP_SOURCE_DIR="$HOME/Developer/paymesh-tools/llama.cpp"
# For local builds only, after runtime/disk gates pass:
sh deploy/build.sh

# Validate the actual Docker Compose schema without printing expanded configuration:
docker compose --env-file "$PAYMESH_CONTAINER_ENV_FILE" -f deploy/compose.yaml config --quiet
# Start ONLY the dedicated new container stack; no existing host data is attached:
docker compose --env-file "$PAYMESH_CONTAINER_ENV_FILE" -f deploy/compose.yaml up -d --wait --wait-timeout 180
# Metadata checks run INSIDE containers, not against host 8000/18080/8082:
docker compose --env-file "$PAYMESH_CONTAINER_ENV_FILE" -f deploy/compose.yaml exec -T python python /app/container_smoke.py
```

Do not rename the Compose project to an existing database project or attach an old
volume. Recreating Java's namespace requires recreating its dependent application
containers together; no independent rolling-Java replacement is promised.

## Remote build and publication

Use [the current controlled v1.0.0 guide](DOCKERHUB-V1-PUBLICATION.md);
`PUBLICATION-PLAN.md` records earlier preparation. The manual `container-images.yml` workflow defaults to
build-only. After the exact GitHub URL/branch/files are approved and published,
Actions → Container images → Run workflow → approved namespace/tag → publish OFF.
If GitHub CLI is installed and authenticated later, equivalent build-only dispatch:

```sh
gh workflow run container-images.yml --repo bhupirao/paymesh-ai --ref main \
  -f namespace=bhupirao -f tag=v1.0.0 \
  -F publish_images=false -F disposable_e2e_verified=false
```

Confirmed destination is bhupirao/paymesh-ai on main; Docker Hub namespace is
bhupirao with v1.0.0 tags. Do not
run a push until actual repositories, visibility, branch and exact file list have
been shown and approved. Configure required reviewers for `dockerhub-publication`
and scoped registry credentials before any publishing dispatch. Do not publish
`latest` implicitly. Four proposed image repositories are listed in the publication
plan; PostgreSQL remains the upstream official image.

## Disposable E2E gates before publishing

Build/image architecture checks alone are insufficient. Verify in the NEW database:

- V1–V14 succeeds; financial/conversation tables start empty; only synthetic fixtures
  are provisioned. Existing host accounts/records must not be copied.
- Container health, frontend routes, cookie login/refresh/logout and Origin/CSRF
  rejection; unauthenticated Merchant/Admin boundaries and private AI ports hidden.
- Synthetic Merchant A/B and Admin ownership isolation, payment links and checkout,
  exact amounts/refunds, conversation create/restore/rename/delete and stale sessions.
- Explicit synthetic knowledge question through Java→Python→Qwen, honest fallback,
  customer wording and technical-details access. Never print prompts or credentials.
- Verify persistence after stopping/starting this project WITHOUT volume deletion.
- Record actual image digests, architecture, test totals and results. Confirm no host
  services or data changed. The metadata smoke tool does not claim these checks.

Local build/start commands do not provision accounts or publish images. The
hosted E2E has passed eight API stages using its guarded synthetic fixture writer.
Container stop/start persistence and native browser E2E are separate checks not
established by that run; neither should be inferred from API-level history retrieval.

## Safe cleanup — later approval only

After approved publication and verified pulls/digests, inventory:

```sh
df -h .
docker system df
docker buildx du
docker ps -a
docker image ls --filter dangling=true
```

Show exact candidate cache records/container/image IDs and dependencies before
requesting deletion approval. Keep tagged working images, every database volume,
all PostgreSQL data, backups, model files and source. No `system prune --volumes`,
no volume removal and no broad host-cache deletion. No cleanup was executed here.

## Actual preparation verification

- **96 offline deployment/workflow tests passed** for this public-release update,
  including unchanged publication-gate tests and a new all-workflow SHA-pin check.
- Compose/workflow YAML, embedded shell/Python syntax, documentation links and
  security/diff checks passed. No local Docker build or service startup was run.
- The previously verified hosted E2E applied V1–V14 only to a fresh disposable
  database and passed all eight API stages with Qwen inference required and verified.
- The previous complete isolated Java suite passed **415 tests** with no failures,
  errors or skips; it was not rerun for these documentation/Action-pin changes.
- Public-release scans covered 13 reachable commits, 605 unique blobs, 14 retained
  Actions run-log archives and eight artifacts. No confirmed live credential was
  identified; heuristic scanning is not a security certificate. No history was rewritten.

## Public portfolio security checklist

The project is source-available, not open source; see the [copyright notice](../README.md#copyright-and-permitted-access).
Third-party licenses remain applicable. No project open-source license is added.

Before the separately approved private-to-public change, review the existing author
email and operational metadata in historical reports. Prior reachable-history and
retained Actions log/artifact scans found no confirmed live credentials; scanning
cannot prove absence of every secret. Removing a current file would not erase its
historical versions. No history rewrite or credential rotation is presently indicated.
Ownership and absence of confidential employer/client material are owner-confirmed.
The author email and operational paths remain in history; consent to their public
exposure is still required. A new commit cannot remove those older disclosures.

Recommended Settings → Actions → General, before enabling public workflows:

- Keep Actions disabled across the visibility transition until protection settings
  below have been verified. Disabling/changing GitHub settings requires approval.
- Allow GitHub-authored actions plus only the reviewed Docker actions:
  `docker/setup-buildx-action`, `docker/login-action`, `docker/build-push-action`.
  Require full-length commit SHA pins where the setting is available; all checked-in
  `uses:` dependencies are pinned. Keep this allowlist narrow when adding workflows.
- Set **Require approval for all external contributors** for fork pull-request
  workflows. Keep all jobs on GitHub-hosted runners, never a personal/self-hosted Mac.
- Set workflow permissions to **Read repository contents and packages**; leave
  **Allow GitHub Actions to create and approve pull requests** unchecked. Existing
  workflow-specific permissions remain `contents: read` and, for publication metadata
  verification only, `actions: read`.
- Never send write tokens or secrets to fork PRs. Do not introduce a privileged
  `pull_request_target` path that checks out or executes contributor-controlled code.
- Keep Docker Hub credentials only in `dockerhub-publication`, not PR-accessible
  repository secrets. Preserve its single selected branch policy: branch `main`.
- After public visibility makes Required reviewers available, configure a trusted
  reviewer before re-enabling publication. Prevent self-review if a second reviewer
  is available, and disallow administrator bypass where supported. Do not remove
  the fail-closed reviewer check from `publication_gate.py`.
- Enable/review secret scanning, push protection and dependency alerts where available.
  Protect `main` and require review for workflow, Dockerfile and publication-gate
  changes. Any visibility-change impact on existing rules must be checked explicitly.

The publication gate and approved source SHA remain unchanged. A public repository
is not approval to dispatch the publishing workflow. Retain registry read/write
least privilege without delete permission and obtain separate publication approval.
