# Disposable five-service container API E2E

## Verified image-build prerequisite

GitHub Actions run [44446484249](https://github.com/bhupirao/paymesh-ai/actions/runs/44446484249)
succeeded at `ab165fc2961ff11c1e5a9d2ff223e3dc8b8d0d10`. Authenticated read-only
API inspection confirmed validate and all four image jobs succeeded. Every image
job passed amd64 inspection and skipped registry login. No Docker Hub publication
was performed. Build success alone does not prove application E2E.

## Prepared runner-only execution

New manual workflow: `.github/workflows/container-e2e.yml`.
It runs on an ephemeral GitHub-hosted ubuntu-24.04 runner; Mac Docker is unnecessary.
It does not push images, log in to Docker Hub or use private local runtime files.

The earlier four matrix builds used separate temporary runners with no exported
image artifacts. Their loaded images are no longer reusable here. This workflow
therefore builds the same four source images together on one runner, sequentially,
with Docker-export-compatible attestations disabled. It starts the existing five-
service Compose model under `paymesh-e2e-RUN_ID-ATTEMPT`, on a new named volume.
It never imports a dump or attaches a host Postgres directory/port.

A single model is downloaded ONLY on the GitHub runner, not the Mac or image:

- Source: public Qwen/Qwen2.5-0.5B-Instruct-GGUF repository on Hugging Face.
- File: qwen2.5-0.5b-instruct-q4_k_m.gguf, 491,400,032 bytes.
- SHA-256: `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
- Public HEAD metadata matched this checksum/size during preparation; no body was
  downloaded locally. The runner enforces checksum, download size and timeout.

New credentials/JWT keys are generated in a private runner directory, never copied
from existing protected configuration. Non-root-readable secret files remain within
an owner-only source directory. SQL/proxy responses, passwords and tokens are never
printed or uploaded. Only a sanitized check/count/image-ID summary is retained in
GitHub's job summary. Raw service logs are deliberately not uploaded.

## Planned real checks — not yet executed

1. Exactly five healthy, correctly labelled containers; only frontend port published;
   Postgres uses the new project-owned volume.
2. Expected V1–V14 history and empty application/financial/conversation state before
   fixture seeding. A single synthetic bootstrap Admin is inserted transactionally
   using pgcrypto BCrypt in this empty database. No production bootstrap is added.
3. Public Merchant A/B signup, Admin approval, active profiles and real browser-style
   cookie login/refresh/logout over the frontend adapter.
4. Role separation, unauthenticated denial and cross-Merchant payment/link denial.
5. Payment creation, deliberate same-key replay, processing and status, using simulated
   INR routing; no automatic retries after failure or uncertainty.
6. Public USD/Card checkout, safe receipt/status, paid-link association and refusal
   of a second attempt after success.
7. Partial and full refunds with exact Decimal comparisons and authorization checks.
8. Java→Python shared-token authentication and RAG-backed knowledge chat for Merchant
   and Admin; conversation save/read/rename/delete and owner/role isolation.
9. Final counts:3 users,2 payments,2 refunds,1 link,1 checkout attempt,0 conversations;
   authenticated session logout followed by refresh denial.

The API suite uses actual containers, not mocks. It does not automate a native browser.
The manual `verify_qwen` input defaults true: Java/Python use RAG_LLM and the three
explicit knowledge questions (Merchant, Admin, saved turn) must return SUCCEEDED,
not fallback. There are no automatic retries. The questions contain no financial
records. With verify_qwen=false it uses RAG_ASSISTED and explicitly reports model
inference untested; that weaker run cannot establish full Qwen integration. Prior
local Qwen success remains separate evidence. No test success is claimed before execution.

Cleanup stops only the exact run-scoped Compose project. It does not issue volume-
removal or prune commands. Temporary storage disappears with the hosted runner.
The job has a55-minute deadline and bounded startup/network calls, without mutation
or inference retries. Failure outputs fixed stage names; preserve the sanitized job
summary and inspect runner-only logs privately if further diagnosis is needed.

## Next action and approval boundary

The workflow/scripts must first be published to main. This requires a new explicit
source-push approval; it is outside the prior README/workflow-fix approval. No push
or workflow dispatch occurred while preparing this E2E batch.

After approving that scoped push, use GitHub's web interface (no local gh required):
Actions → **Disposable container API E2E (no publication)** → Run workflow → main,
with verify_qwen=true for the full synthetic model path.
No registry credentials or private payment data are required for this test run.
A successful run must show `DISPOSABLE_CONTAINER_API_E2E_PASS`, all eight check groups
in sanitized-e2e.json/job summary, five healthy services and expected fixture counts.
A cancelled/failed/skipped run is not success; investigate before any publication.

## Docker Hub publication preparation — only after successful E2E

Destinations remain:

- bhupirao/paymesh-java:v1.0.0
- bhupirao/paymesh-python:v1.0.0
- bhupirao/paymesh-frontend:v1.0.0
- bhupirao/paymesh-llama:v1.0.0

Create/review these repositories and visibility. Configure GitHub environment
`dockerhub-publication` with required reviewers and secrets:

- `DOCKERHUB_USERNAME`: account authorized for those repositories (bhupirao).
- `DOCKERHUB_TOKEN`: Docker Hub access token with the least read/write permissions
  needed for these image pushes; deletion permission is unnecessary. Scope to the
  repositories where the account/token facilities support it.

Enter secrets through GitHub Settings → Environments → dockerhub-publication;
never put values in workflow inputs, URLs, source or terminal arguments. Normal
GitHub checkout uses GITHUB_TOKEN with contents:read. The E2E job needs neither
Docker Hub secret. Private repository hosted-runner minutes depend on the account's
available Actions allowance; no paid services are provisioned by this code.

Only after reviewing actual E2E evidence request a separate approval to run the
manual image workflow with publication enabled. Cite the exact tested source revision
and tags. E2E records local image IDs, not registry digests; a later rebuild is not
proof of byte-identical image promotion. Revalidate/pin the final publication artifacts
and record resulting registry digests. No image publication is authorized here.
