# Published PayMesh AI v1.0.0 artifact verification

Status: implemented and offline-tested. **No published-artifact runtime E2E run has been executed by this change.** A green offline test is not container, model, or native-browser proof.

## Release and architecture

`release-v1.0.0-images.json` locks the four public Docker Hub application images by immutable digest, platform `linux/amd64`, source `cefa7df83a5bf16d011e82041c95e2d93b9c637b`, and successful source-built E2E run `44652430877`. Reviewed main before this tooling change was `c3bb92e971b17da2188e96172b16b7b001ec4ba4`. The new harness necessarily runs from a later reviewed commit; it does not rebuild that commit's applications.

`compose.release-verify.yaml` has no build sections. It preserves the source Compose service configuration except image references and the descriptive project name. PostgreSQL uses official `postgres:16.16-bookworm` (a version tag, not an immutable PostgreSQL digest). Four application images are pulled by digest. Java owns a shared network namespace with Python, llama.cpp and frontend. Only frontend is reachable from the runner at `127.0.0.1:15500`; Java/Python/model listeners remain loopback-private. PostgreSQL has an internal network and a fresh project-scoped volume. Application containers retain non-root image users, read-only filesystems, bounded memory/tmpfs, dropped capabilities and health checks.

This is production-style disposable verification of the existing **development/demo HTTP architecture**, not a production TLS, PCI, disaster-recovery or real-bank certification.

## Operator approval and execution

1. Review and separately approve committing/pushing these tooling files. Preserve the existing source-built E2E workflow, publication workflow, released digests and prior evidence.
2. Confirm the repository's Actions selected-action allowlist still permits the exact checkout and upload-artifact references in the new workflow. No new Action providers or environment secrets are required. Keep image publication disabled.
3. After the separately approved push, open **Actions → Published v1.0.0 artifact API E2E (no publication) → Run workflow → main**. This workflow has no inputs and cannot disable real model verification. Do not dispatch a second run automatically after failure.
4. Inspect the completed run and its `published-artifact-e2e-RUN-ATTEMPT` artifact. Success requires the job and every check to pass, `success=true`, `verificationKind=PUBLISHED_ARTIFACTS`, `modelInferenceVerified=true`, and `applicationImagesBuilt=false`. Confirm `releaseImages` matches the approved lock.
5. Treat a startup, pull, checksum, model fallback, authorization or API failure as failure. Preserve sanitized diagnostics and investigate before separately authorizing a new run. Never rebuild images to get this verification green.

The workflow performs these commands on a fresh GitHub-hosted Linux VM, not on a Mac:

```sh
python3 -B -m unittest discover -s deploy -p 'test_*.py'
python3 -B deploy/release_artifact_e2e.py fixtures
# Workflow downloads exactly one model and verifies its checksum here.
docker compose --project-name "$E2E_PROJECT" --env-file "$E2E_ENV" -f deploy/compose.release-verify.yaml config --quiet
docker compose --project-name "$E2E_PROJECT" --env-file "$E2E_ENV" -f deploy/compose.release-verify.yaml pull
docker compose --project-name "$E2E_PROJECT" --env-file "$E2E_ENV" -f deploy/compose.release-verify.yaml up -d --no-build --pull never --wait --wait-timeout 240
python3 -B deploy/release_artifact_e2e.py run
# Failure-only diagnostics and evidence upload precede teardown.
python3 -B deploy/release_artifact_e2e.py cleanup
```

These commands are **not a local-run procedure**. The runner guard requires GitHub-hosted Linux, this repository, manual dispatch, main, a unique run/attempt project and mandatory real-model verification. Do not spoof these safeguards locally.

## Disposable configuration and resources

The existing fixture generator creates an owner-only temporary directory, fresh synthetic account passwords, database/HMAC/AI secrets, and an RSA-2048 PKCS8/X509 key pair. File mounts must remain readable by runtime UID 10001: secret files are read-only inside a mode-700 parent, and the environment file is mode 600. No deployment environment, host credentials, personal configuration or existing database is used. The Admin bootstrap is the existing guarded SQL fixture; Merchants, payments, refunds and conversations use APIs.

Flyway is enabled **only for the fresh disposable database**, targeted at V14; Hibernate validates, SQL initialization is disabled. Existing database and backup paths are never mounted. Gateway-timeout simulation, settlement scheduling, conversation cleanup, password recovery and checkout fault controls stay disabled. Mock gateways perform no external payment processing. AI chat/generation are enabled only within this synthetic stack; matching private service tokens are fresh per run.

The one free local model is Qwen2.5-0.5B-Instruct Q4_K_M, approximately 469 MiB, downloaded on the runner from the existing Qwen Hugging Face URL, with SHA-256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`. The bounded download has no automatic retry. No paid API, local model download or llama.cpp source checkout is needed.

Budget: Ubuntu 24.04 x64 public GitHub-hosted runner; container memory limits total 2208 MiB, plus runner/OS overhead. The job checks at least 6 GiB free before pulls; this is a conservative admission gate, not a measured peak-storage guarantee. Startup is bounded to 240 seconds and the whole job to 55 minutes. Model generation retains the released 30-second timeout. CPU inference performance and registry/download availability remain runtime risks.

## Automatic verification matrix

| Check | Required result |
|---|---|
| Artifact identity | Exactly five healthy project containers; each application uses its locked manifest reference, matching local image config identity, source label and linux/amd64 platform |
| Database | Fresh project volume, exactly 14 successful versioned migrations, no failed migration, empty initial business tables; exact migration-seeded ADMIN/MERCHANT role reference data |
| Authentication/authorization | Registration → pending → attested Admin approval → ACTIVE login; HttpOnly refresh cookie; refresh/logout; wrong-role and Merchant A/B denial |
| Frontend connectivity | HTTP Merchant/Admin routes and real API traffic through the fixed frontend proxy |
| Payment/idempotency | INR 13.25 creation; same idempotency key returns same payment; processing reaches SUCCESS; cross-Merchant denial |
| Public checkout | USD 25.00 synthetic link checkout, receipt/status, paid-state replay rejection and private-field exclusion |
| Refunds | INR 3.25 + 10.00 recorded refunds, exact 13.25 total, REFUNDED state and ownership denial |
| Signed webhook | Private mock-Razorpay endpoint rejects invalid HMAC, accepts one signed terminal-state event as IGNORED, returns the same receipt on duplicate, records one event/attempt and leaves payment SUCCESS |
| Investigation | Merchant and Admin authorized payment investigation; evidence/knowledge references, correct payment and COMPLETED + RAG_LLM/SUCCEEDED; Merchant B denied |
| Chat | Merchant/Admin knowledge question must return KNOWLEDGE + RAG_LLM/SUCCEEDED + knowledge references; fallback fails |
| Conversations | Create, completed server-owned turn, retrieve, rename with current version, delete; Merchant B and mismatched Admin portal ownership denied; saved generation also requires RAG_LLM/SUCCEEDED |
| Final state | Exactly the existing synthetic fixture counts; created conversation removed; logout invalidates refresh |

The webhook request runs inside the existing Python container to the fixed private Java endpoint `/api/v1/webhooks/mock-razorpay`, using HMAC-SHA256 over `timestamp + '.' + exact_body`. Its secret is passed through subprocess standard input, never arguments or logs. This does not expose Java or add an unrestricted proxy route. The test verifies terminal-state safety and inbox deduplication, **not** PROCESSING recovery or the Stripe ingress path.

`docker inspect` is consumed in memory, never uploaded raw. Docker's container image ID is the image **config digest**, not the manifest/index digest; the harness compares the correct identities and RepoDigests separately. OCI labels provide traceability, not an independently signed provenance guarantee.

## Failure evidence, cleanup and recovery

Only fixed result codes, allowlisted request metadata, image identities, source/lock identifiers and fixture counts enter the bounded sanitized JSON. Questions, answers, passwords, cookies, JWTs, HMAC credentials and raw responses are excluded. Diagnostic collection uses the existing bounded/redacted collector with an explicit allowlist of the two reviewed Compose files. Failure logs are captured before teardown; if secret inventory cannot be validated, log collection fails closed. Artifacts retain only the explicit JSON/log allowlist for three days; `.env`, keys, dumps and model weights are never uploaded.

Teardown runs with `always()`, validates exact project and temporary paths, stops only that project with a bounded timeout and does not use volume deletion or prune. The temporary named volume and files disappear when the dedicated hosted VM is discarded. Hard job cancellation or runner failure can interrupt in-job teardown; GitHub's VM disposal is the final isolation boundary. No shared/self-hosted runner is supported.

No rollback of published images is necessary: this job never pushes or alters them. On partial failure, do not change tags, restart local services or restore any database. Read sanitized evidence, fix only confirmed tooling defects, and request approval for another manual run. Do not automatically retry mutation or inference requests.

## Native browser limitations

API success does not establish rendered UI interaction, screenshots, mobile 375px layout, keyboard/focus behavior, clipboard, cross-tab session events, browser cache behavior or refresh-driven conversation restoration. Those need separately authorized native-browser E2E. Container restart persistence, concurrent conversation races, timeout fault injection, real gateway credentials and settlement are also outside this workflow's runtime coverage; existing offline/source tests are not substituted as proof.

## Offline validation

Run the deployment unittest suite, AST syntax checks, Ruby/Psych YAML parsing, JSON parsing and `git diff --check`. Docker Compose configuration validation requires Docker CLI with Compose; when unavailable locally, record it as not executed. The workflow performs real Compose validation on the runner before pulling/starting. No offline result may be reported as published-artifact runtime success.

Verified during implementation: all **125 deployment tests passed**, including **29 published-artifact tests**. Python AST, YAML/JSON parsing, the targeted seven-file publication scanner and whitespace checks passed. Existing source-build and publication workflow bytes were unchanged. Docker CLI/Compose was unavailable locally, so real Compose config validation and all runtime/container/model checks were **not executed**. No Java, application Python or frontend suite was rerun because their application sources were unchanged.

## First published-artifact run: confirmed seed-check correction

Run `44787046258` used harness commit `3f56cca2d5612fd35922985cc4f6309983e73a0a`. All five containers were healthy, identity checks passed, and the failure-only PostgreSQL log retained `relation "gateway_transactions" does not exist` with statement `SELECT count(*) FROM gateway_transactions;`. V4 creates `payment_gateway_transactions`; the release harness now checks that actual table. This was a verification SQL naming defect, not a demonstrated application or migration failure.

A second source-confirmed assumption in the new blanket empty-table check would reject V8's intentional `roles` reference rows. The corrected check requires exactly `ADMIN` and `MERCHANT` before excluding `roles` and Flyway history from its all-business-table scan. Extra/missing roles fail closed, as does any populated business table. Admin bootstrap still runs only after these checks. The successful source-built harness did not contain either new assumption and remains unchanged.

The failed operation was Compose `exec -T postgres psql -X -U paymesh_container_user -d paymesh_container -Atq -v ON_ERROR_STOP=1`, with the failing SELECT provided through standard input. The Compose project was `paymesh-e2e-44787046258-1`, using its runner-temp `container.env` and `deploy/compose.release-verify.yaml` from the checked-out workspace. The workflow process exited 1; the inner psql/Compose exit code and stderr were captured in memory but discarded by the inherited command helper, so their exact historical values cannot be recovered from these artifacts. The PostgreSQL server error independently establishes the failed statement.

No additional generic diagnostic layer is necessary to establish this cause. If a different container operation fails later, a narrowly scoped follow-up can record a fixed operation category, target service, numeric exit code and allowlisted PostgreSQL error category. It must never log stdin, raw SQL, command arguments containing credentials, or arbitrary stderr. This correction performs no retry, skips no check, and does not claim that the remaining runtime stages have passed.
