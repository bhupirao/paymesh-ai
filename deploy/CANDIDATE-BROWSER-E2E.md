# Candidate frontend Chromium E2E — preparation only

## Verified previous build (not a browser result)

GitHub run [44871388560](https://github.com/bhupirao/paymesh-ai/actions/runs/44871388560) completed successfully at workflow/main commit `8916aefe386af0d90b64161e84c5b42bee0738b1`, using frontend source `a4171a5c090224622d584d45caa0d06e7997be9b`.

Sanitized artifact values independently retrieved:

- app.js SHA-256: `9b14131f8959e8bc8a393740ade4c43359243fc685d722c77a501e95e784e61e`.
- Runtime-context SHA-256: `27abd26312820b76229de8867f30674b50396d7f03dd2a8ca7d905dc79623a12`.
- Image configuration digest: `sha256:67c6445cc919cd483df714748fbdfe3a334ec6b17d1c778b30ebe75e2c11ad95`.
- Temporary archive SHA-256: `f5251831d31ad92ae3d5eb2c8e19d752e46ed303debdec57d1fc77ddeed894c6`.
- Platform: linux/amd64; registry manifest digest: null; published=false; browserTested=false.
- Cleanup success=true, containerAbsent=true, candidateImageAbsent=true, temporaryPayloadRemoved=true; no volumes were used by the build-only job.

That local candidate and archive were removed. They cannot be pulled from Docker Hub. The new browser workflow rebuilds only the same source-pinned frontend in its own disposable job. Its new unique label and possibly updated official base image can produce a different configuration digest; the prior config digest must not be substituted for that new run's actual identity.

## Separate workflow and mixed identity contract

New files:

- `.github/workflows/candidate-browser-e2e.yml`
- `deploy/compose.candidate-browser.yaml`
- `deploy/candidate_browser.py`
- `deploy/test_candidate_browser.py`
- `deploy/CANDIDATE-BROWSER-E2E.md`

Small shared-helper extensions:

- `release_artifact_e2e.cleanup_project`: optional explicit Compose path/config validator; original defaults unchanged. Candidate cleanup requires extra mixed-image validation before any destructive operation and reuses all original resource ownership checks.
- `capture_failure_diagnostics.collect`: one additional fixed allowlisted candidate Compose path, same bounded/redacted capture.
- `browser_bootstrap.verify`: shares unchanged identity/empty-V14/Admin-only bootstrap/final-count logic, with explicit candidate provenance. Existing `main` still constructs the published ReleaseSuite.
- Browser sanitized reporter: candidate reports say publishedImagesOnly=false and frontendArtifactKind=source-built-candidate. Default published-release reports retain their previous meaning. Offline reporter coverage and its expected test count are updated.

No application code, browser journey/accessibility scenario, pacing algorithm, Dockerfile, existing workflow, original Compose file or v1.0.0 lock changes.

The new workflow is workflow_dispatch-only, main-only, read-only contents, ubuntu-24.04, 55min, serialized, one Chromium worker and zero retries. It uses only existing approved SHA-pinned checkout/Buildx/upload-artifact Actions. There is no Docker Hub login, environment credential reference or push command.

## Runner execution after separate approval

1. Checkout the exact workflow-run revision and the fixed frontend source under candidate-source; disable persisted checkout credentials. Run offline regressions and pinned bootstrap tests.
2. Build only the frontend through `frontend_candidate.py build`, retaining its existing 115-file content pin, source/app hashes, platform/user/entrypoint checks, extracted-app comparison, config digest and temporary archive checksum. No Java/Python/llama build.
3. `candidate_browser.py fixtures` validates the private evidence against this run, source/context/app pins and the actually loaded image. It exports only the validated local image tag and a fixed provenance mode through GITHUB_ENV. The existing fixture generator creates new runner-only credentials and paths; no local demo configuration is accessed.
4. Compose uses the explicit candidate frontend reference with pull_policy=never. Only PostgreSQL and the three locked published backend images are pulled. Startup uses --no-build --pull never and a 240s readiness bound. Java retains the shared network namespace; only frontend port15500 is published on host127.0.0.1. PostgreSQL uses the unique project volume and no host port.
5. CandidateSuite verifies all five healthy containers, loopback exposure and database volume identity. For Java/Python/llama it uses the original registry digest/config/source validator unchanged. For frontend it checks exact local tag + image configuration digest + linux/amd64 + source/candidate labels + reviewed runtime configuration. The explicit source-built frontend does not need a fictitious RepoDigest.
6. Reuse strict V1–V14/empty-business-table/reference-role checks and SQL bootstrap of only the synthetic Admin. Merchant registration, login, approval, payment creation, checkout, refunds and conversations remain actual browser interactions.
7. Download the single checksum-verified Qwen model on the runner; install the existing locked Playwright/Chromium version there. Run the entire unchanged three-test suite. Preserve auth pacing, refresh/history assertions and actual RAG_LLM/SUCCEEDED/knowledge-reference validation. No fallback-only pass, test skipping or automatic retries.
8. Verify the exact final disposable fixture counts. On failure, collect existing bounded redacted service diagnostics before teardown. Retain only allowlisted JSON/log artifacts for three days; no prompts, answers, credentials, traces, screenshots, videos, HAR or auth-state files.
9. Always perform ownership-validated stack teardown, including scoped --volumes and post-teardown container/volume absence verification. The candidate path additionally requires the exact Compose hash and matching candidate/published image configuration. External/shared volumes, foreign consumers and unexpected mounts still fail closed.
10. After stack teardown, always invoke the original candidate-only image/inspection-container cleanup. It refuses image removal if stack consumers remain. Preserve separate stack-volume and candidate-image cleanup evidence. No global prune, unrelated resource deletion, registry change or automatic recovery.

Future operator entry: GitHub Actions → **Candidate frontend Chromium E2E (no publication)** → Run workflow → main, only after separately approving commit/push and dispatch. Do not run the original published-only workflow against an implicit frontend substitution.

## Evidence and failure interpretation

Build evidence lives in `$RUNNER_TEMP/paymesh-frontend-candidate-<run>-<attempt>/candidate.json`.
Stack/browser evidence lives in `$E2E_DIR`: candidate.json (mixed image identity), sanitized-browser-bootstrap.json, sanitized-browser.json, sanitized-browser-final.json and sanitized-cleanup.json. Candidate-image cleanup has a separate cleanup.json. Duplicate filenames in artifacts are separated by their run-directory paths; the independent build artifact also preserves the build proof when fixture setup fails.

No registry digest exists for this local candidate. Its config digest and source/content pins identify the image that ran. A successful browser result would validate this mixed candidate stack, not a newly published release. Any later publication needs a new unused tag, actual registry digest and separately approved published-artifact verification. All v1.0.0 tags, digests and historical evidence remain immutable.

If model, startup, authentication, UI or cleanup fails, retain sanitized evidence and stop. No retries, publication, local service changes or data restoration are performed. GitHub job cancellation/host failure can interrupt always steps; the disposable runner remains the final isolation boundary. Runtime memory/disk/model timing and full native browser behavior remain unverified until execution. Existing 8GiB free-disk admission and 55-minute job bound remain; frontend-only building adds a small image/archive to the previous five-service model/browser workload.

## Offline verification

Tests cover manual triggers, exact source/Action pins, private candidate metadata, tamper rejection, mixed registry/local identity, unchanged backend locks, enabled full browser suite, real-model requirements, explicit candidate evidence, and cleanup success/failure/external/shared-volume rejection. Existing deployment coverage continues exercising all original cleanup safeguards. No Docker operation, model download, browser install or inference is executed locally.

### Actual preparation results

- 191 deployment regression tests passed, including 14 new candidate-browser adapter/workflow/identity/cleanup tests. Docker, PostgreSQL and inference operations in these regressions are mocked; no local container ran.
- 51 browser helper/reporter tests passed (including explicit source-built-candidate labeling); 13 bootstrap module tests passed.
- 20 existing frontend JS suites passed 1,563 assertions; full frontend/proxy discovery passed59 tests using isolated mock loopback listeners.
- Syntax, YAML/JSON, targeted secret-pattern, protected-file fingerprints and git diff --check passed. Docker Compose CLI validation remains runner-only because Docker is unavailable locally.
- Read-only API verification found main unchanged at8916aefe386af0d90b64161e84c5b42bee0738b1, approved Action pins permitted, selected-actions/SHA enforcement active and publication disabled.
- The original published browser workflow, publication workflow, v1.0.0 locks/Compose, native journey/accessibility tests and auth pacing file remain byte-identical. No application source changed.
- Concurrent index changes appeared during preparation; no staging command was issued and no staged entry was reset/reconciled. A later authorized commit must inspect the current index and isolate the intended diff.

READY for separately approved review/commit/push of this candidate-browser preparation. No commit, push, dispatch, image build/publication, browser installation, local model download or inference was performed. Full candidate Chromium success remains UNKNOWN until a separately approved runner execution; the prior build-only success is not browser E2E evidence.
