# Frontend candidate preparation — no publication

This adds a separate manual-only build verification workflow. It does not change the v1.0.0 release, existing browser/API workflows, Compose configuration or application code.

## Reviewed identities and security

- Approved frontend source: `a4171a5c090224622d584d45caa0d06e7997be9b`.
- Existing public frontend: `bhupirao/paymesh-frontend@sha256:388718b672a9b944348a40257a56d212f1a6e4cb6ad372376a4e03ba5b1b2412`.
- Java/Python/llama remain the exact references in `release-v1.0.0-images.json`.
- Read-only live checks confirmed main at the approved source, selected Actions and SHA enforcement active, all three required Action references permitted, the publication workflow disabled, and the anonymous Docker Hub frontend v1.0.0 manifest matching the locked digest.

The frontend Dockerfile independently copies frontend Python handlers, HTML/assets and `deploy/frontend_entry.py` onto `python:3.13-slim-bookworm`. No Java, Python AI-service or llama build is required. The helper constructs a context containing only 115 approved runtime files. It verifies both source commit and a fixed aggregate content fingerprint; the built app.js must match its approved hash. Credentials, dumps, model weights, VCS and local virtual environments are absent from this context. Static secret-pattern checks and image configuration checks are defense in depth, not a comprehensive vulnerability certification.

## Files

- `.github/workflows/frontend-candidate.yml`
- `deploy/frontend_candidate.py`
- `deploy/test_frontend_candidate.py`
- `deploy/FRONTEND-CANDIDATE.md`

The workflow uses `workflow_dispatch` only, main/repository guards, ubuntu-24.04, read-only contents permission, concurrency serialization and a 20-minute bound. There are no inputs that can replace the pinned source or destination. Both checkouts disable persisted credentials. The first checkout pins the workflow run's commit; the second checks out the fixed approved application revision under `candidate-source`.

Only the existing approved immutable checkout, setup-buildx and upload-artifact references are used. No deployment environment, Docker Hub login, publication secret, push command, model download or application stack exists in this workflow.

## Build and evidence

Following separate commit/push and manual-run approval, use GitHub Actions → **Frontend candidate build verification (no publication)** → Run workflow → main. Do not run the old publication workflow.

The helper builds exactly one local image:

`paymesh-frontend-candidate:paymesh-frontend-candidate-<run-id>-<attempt>`

Buildx uses linux/amd64, `--load`, `--provenance=false` and `--sbom=false` to avoid loading an attested manifest list into the classic Docker image store. Labels bind the application revision and candidate identity. These labels alone are not treated as proof: source/runtime-context checks and extraction/hash comparison of the actual image's app.js are also required.

A stopped, network-none, read-only inspection container is created without ports, mounts or volumes. It never starts a service. The image must specify non-root UID/GID10001, the reviewed entrypoint, no declared volumes, matching source/candidate labels and no sensitive environment variable names. The image archive is saved temporarily and hashed, but is never uploaded. Only bounded mode600 JSON evidence is retained for three days.

Evidence folder: `$RUNNER_TEMP/paymesh-frontend-candidate-<run-id>-<attempt>/`.

- `candidate.json`: source/workflow revisions, context/app hashes, platform, local tag, **image config digest**, **archive SHA-256**, `registryManifestDigest: null`, `published: false`, `browserTested: false`.
- `cleanup.json`: scoped container/image absence and temporary payload removal, or fixed-code failure.

A config digest is not an OCI manifest/index digest; an archive checksum is neither. No registry digest can be asserted before a separately approved registry publication. No model or browser success is inferred from a completed build.

Docker subprocess output is captured, never printed or uploaded. Failures produce fixed codes only. No environment files, raw logs, image archive, browser state or source context enter artifacts. The base tag is mutable; the resulting candidate digest records that actual build, not a bit-reproducible guarantee. Base-image vulnerability scanning/attestation would require separately reviewed tooling and is not claimed here.

## Cleanup and failure handling

Cleanup runs with `always()` after evidence retention. It validates the exact run-owned inspection container's name, label, local tag, stopped state and absence of mounts. Foreign/running/mounted containers are rejected. It removes only that container, then verifies the image's provenance, single candidate tag and absence of consumers before removing its tag with `--no-prune`. There is no force removal, global prune, volume deletion or unrelated container deletion.

Only fixed direct payload filenames and the validated context directory beneath the private owned run folder are removed. Container/image absence is checked afterward; cleanup failure fails the job and produces fixed-code evidence. Buildx's pinned Action removes its own builder during post-job cleanup; the disposable runner is the final boundary for any unremoved cache. No automatic retry or recovery occurs. If setup failed before a private candidate folder existed, cleanup reports that no candidate resources were created and does not touch Docker.

## Minimum future Chromium integration — not implemented here

No existing workflow needs changing for this build-only preparation. A full candidate Chromium job requires separately approved changes:

1. Extend a **separate candidate browser workflow**, keeping the published-only browser workflow intact. Build and verify the candidate in that same disposable job; no download-artifact Action or new allowlist entry is necessary. Defer candidate image cleanup until browser/stack teardown completes.
2. Pass the validated local image reference **and config digest** directly from private candidate evidence to an explicit candidate-only Compose override/contract. Enforce the unique identifier and exact image ID/source/content pins before startup. Do not accept an arbitrary dispatch-supplied image. Do not label this stack “published images only”: it contains three published application images and one source-built candidate.
3. Keep Java/Python/llama pinned exactly to the existing release digests and PostgreSQL as the fifth service. Preserve the shared Java network namespace, frontend-only 127.0.0.1:15500 publishing, fresh secrets and disposable database volume.
4. Add a separate identity/bootstrap adapter for this mixed candidate contract. The original `ReleaseSuite` and cleanup helper hard-code the old Compose path and shared source revision. Reusing them unchanged or monkey-patching their globals would either reject the candidate or misstate verification. Preserve the original v1.0.0 validator; explicitly validate the candidate frontend's config ID and new revision alongside registry RepoDigests and original source revision for the three published images.
5. Use that reviewed candidate adapter for the existing SQL-only Admin bootstrap/final-count checks, sanitized diagnostics and ownership-validated Compose teardown. Preserve the same strict database baseline, project-volume validation, foreign-consumer rejection and post-cleanup absence checks. Never run `down --volumes` against an unvalidated override.
6. Download the single checksum-verified Qwen model on the runner only; keep RAG_LLM, SUCCEEDED and knowledge-reference requirements. Install the locked Chromium dependency on the runner and run the **entire unchanged three-test browser suite** with one worker, zero retries, existing pacing and all UI assertions. Keep traces/videos/screenshots/HAR/auth-state exports disabled.
7. Retain sanitized browser, model-success, candidate identity and cleanup evidence. The local image config digest proves which loaded candidate ran; the archive checksum allows a later transfer/import check if a separately reviewed transport is introduced. Neither proves a registry artifact was tested.
8. After successful candidate verification, seek separate publication approval for a new unused tag. Record the actual new registry digest and verify that exact registry artifact in a new candidate/release contract before promoting it. Never move or overwrite v1.0.0 or reinterpret old successful runs as evidence for the changed frontend.

Thus build-only readiness does not imply candidate Chromium implementation or execution is complete. Existing publication gates remain fail-closed against this new source.

## Offline validation

Run `python3 -B -m unittest discover -s deploy -p 'test_*.py'`, Python AST checks, Ruby YAML parsing, JSON validation and `git diff --check`. Candidate tests mock Docker operations and cover context/source pinning, built-content identity evidence, permissions, manual triggers, allowed Actions, no publication credentials, cleanup on failure/success, foreign/shared resource rejection and unchanged browser/release contracts. No local Docker, browser or model is installed or executed.

Runner estimate: one Python-slim frontend build, one stopped inspection container and one temporary archive; admit at least2GiB free, build timeout10min, archive timeout2min, cleanup4min, job20min. Actual image size/build time are unknown until execution. Browser integration would additionally need the existing five-service/model/Chromium admission and55-minute planning budget.

### Actual preparation results

- **177 deployment tests passed**, including **17 new offline candidate tests**. Docker build/create/copy/save/removal operations in these tests were mocked; none executed against a Docker daemon.
- **50 existing browser helper/reporter tests passed**; **13 existing bootstrap integration tests passed**. These are offline modules, not Chromium.
- Python AST, YAML/JSON parsing, targeted secret checks and `git diff --check` passed. Existing publication/browser workflows and v1.0.0 locks remained unchanged.
- Compose CLI validation was not executed because Docker is unavailable locally; this preparation does not add or modify Compose files.
- Concurrent index changes appeared for the new workflow/helper/test paths despite no Git staging commands being issued. Those entries were preserved without reset or reconciliation; a later authorized commit must use a freshly reviewed isolated index. No commit, push, dispatch, local Docker operation, model download or publication occurred.

Ready for separately approved review/commit/push of this build-only preparation. Candidate build output, startup, health and complete Chromium behavior remain unverified until their separately authorized runner execution.
