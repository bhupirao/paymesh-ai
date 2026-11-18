# PayMesh isolated containers and image publication

Status: source preparation/offline validation complete; **Docker builds, startup,
container E2E and registry publication NOT executed**. Docker, Colima/Podman and
GitHub CLI are not installed/available on the inspected host. Git origin is https://github.com/bhupirao/paymesh-ai.git; the source checkout
remains on unborn `main`. Namespace bhupirao and v1.0.0 tags are confirmed; actual
publication still requires approval.

## Architecture

Five linux/amd64 services: Java 21, Python FastAPI, PostgreSQL 16, llama.cpp b4514
(ec7f3ac9ab33e46b136eb5ab6a76c4d81f57c7f1), and the existing frontend/proxy.
Multi-stage Java/Python/llama builds ship runtime artifacts only. Frontend requires
only Python's standard library. Qwen2.5 model weights are NOT included in any image.
The existing single GGUF is bind-mounted read-only, without copying/downloading it.
The llama context excludes local build directories, Git objects and model files.

Java/Python/llama/frontend share Java's network namespace to preserve existing
loopback-only AI validation and the fixed frontend upstream. PostgreSQL has its own
private network endpoint and a NEW named volume `paymesh-containers_container_pgdata`.
No database port is published. No host PostgreSQL URL, data directory or volume is
mounted. Flyway V1–V14 applies ONLY to this new disposable container database; host
Flyway/configuration/data is untouched. Do not import host dumps or credentials.
Only frontend port **127.0.0.1:15500** is published (local host services remain on
5500/18080/8000/8082). Images include five health checks; actual readiness remains
untested until a Docker runtime is available.

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

Read `PUBLICATION-PLAN.md`. The manual `container-images.yml` workflow defaults to
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

No automatic database/account fixture writer or image publication is included in
local build/start commands. Docker absence currently blocks these runtime checks.

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

-12 offline unit tests passed for fixed Origin translation/rejection/restoration,
 safe logging and publication scanner checks.
-Compose and workflow YAML parse; five services and five health checks verified.
 This is not a successful `docker compose config`, build or startup result.
-Shell/Python syntax and `git diff --check` passed.
-Index/working-tree tripwires found only reviewed literal PEM delimiter test helpers;
 no indexed file exceeded10MiB. This is heuristic scanning, not a credential audit
 certificate. Existing staging and unrelated workflow were not rewritten.
