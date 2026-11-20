# Native Chromium E2E against published PayMesh AI v1.0.0

Status: implementation/offline verification only. **No Chromium run, workflow dispatch, image build, or local Docker execution was performed to prepare this suite.** A green offline regression does not prove browser success.

## Verified baseline and release identity

Published-image API E2E run [44793055710](https://github.com/bhupirao/paymesh-ai/actions/runs/44793055710) succeeded on tooling commit `57a737520c1095195e7549e132ad8de87a388f64`. Its separate cleanup artifact confirmed `success=true`, `volumesAbsent=true`, and `containersAbsent=true`. Preserve this evidence as API proof; this suite adds actual browser proof only when it runs successfully.

The new manual-only workflow reuses `compose.release-verify.yaml`, `release-v1.0.0-images.json`, the runner fixture generator, image identity/empty-database validation, and guarded project-only cleanup. All four public application image digest locks remain unchanged, with source `cefa7df83a5bf16d011e82041c95e2d93b9c637b`. No application files are mounted over the images and there are no build steps. PostgreSQL 16 is the fifth service and is always a fresh project-scoped volume. Public repositories are pulled anonymously; no Docker Hub login, publication environment or deployment secrets are needed.

## Dependencies and execution limits

`browser-e2e/package.json` pins `@playwright/test` **1.65.1** exactly. The npm lockfile includes registry URLs and SHA-512 integrity for transitive dependencies. Playwright is third-party Apache-2.0 software; this does not change the project's source-available copyright terms.

Only an Ubuntu 24.04 GitHub-hosted runner is supported, using its preinstalled Node 22 or 24. The admission check fails if that changes; it never installs an unreviewed runtime automatically. The whole job is limited to 55 minutes, the test suite to 30 minutes, and the serial journey to five minutes. Chromium is the only browser; one worker and zero retries prevent overlapping financial/inference intent. Browser actions have 15-second bounds, navigation 30 seconds, and observed AI responses 55 seconds. Existing server inference limits remain unchanged.

Budget at least 8 GiB free before browser/image installation. The public runner has 4 CPUs/16 GB RAM/14 GB SSD, while existing container limits total 2208 MiB; browser/OS overhead is additional and not yet measured for this suite. Only the runner downloads Chromium and one approximately 469 MiB Qwen2.5-0.5B Q4_K_M file. The existing bounded Qwen download and checksum are unchanged. No paid API, duplicated local model, Firefox or WebKit is used.

The development Mac's Node 18 is below this suite's declared runtime. Only syntax and dependency-free helper tests run there; Playwright discovery and browser execution are not claimed. Lockfile preparation used npm's package-lock-only/ignore-scripts mode without browser installation.

## Workflow and fixture lifecycle

`.github/workflows/browser-e2e.yml` accepts manual dispatch on main only, with `contents: read`, fixed published Compose, and mandatory real Qwen verification. It uses only the existing allowlisted SHA-pinned checkout/upload-artifact actions. No existing workflow or repository setting is changed.

1. Run offline deployment regressions.
2. Create run/attempt-specific credentials in an owner-only runner temporary directory.
3. Verify Node and disk, install the locked package (`npm ci --ignore-scripts`) and Chromium with Linux dependencies.
4. Download/checksum the single model; pull immutable application images.
5. Start with `--no-build --pull never` and bounded health checks.
6. `browser_bootstrap.py seed` reuses image/namespace/port/volume guards, verifies fresh V14 and reference roles, then creates **only the synthetic Admin** through the existing guarded SQL fixture. It does not pre-register Merchants or replace UI actions with APIs.
7. Run three real Playwright tests: two responsive/keyboard cases and one serial multi-role journey. All registration, login, approval, payment/refund/checkout and conversation operations happen through Chromium UI actions.
8. A read-only final query requires exactly 3 users, 2 payments, 2 refunds, 1 link, 1 checkout attempt and 0 conversations. It does not change business data.
9. Capture bounded redacted service diagnostics on failure before teardown and upload only allowlisted evidence.
10. Always invoke the existing ownership-validated cleanup, including `down --volumes`, then retain its independent volume/container-absence report even after a failed browser run.

Use a fresh isolated BrowserContext for Admin, Merchant A, Merchant B and public customer. Credentials are read only from fresh fixture files into runner memory, never CLI arguments. No pre-authenticated storageState is saved. Refresh checks reuse the same browser context's HttpOnly refresh cookie; a second page in the Merchant context exercises BroadcastChannel logout invalidation. Other identities never share that context.

## Coverage matrix

| Native case/stage | Assertions |
|---|---|
| Desktop / 375px keyboard and validation | Login tab order, password-toggle Enter activation, required-input focus, signup errors/aria-invalid, no document-level horizontal overflow |
| Registration | Two synthetic registrations through the form, empty-input feedback, PENDING_APPROVAL, pending Merchant UI and logout |
| Approval | Admin login, filtered lookup/Open, ownership reference/attestation, focusable review dialog, cancel and confirm, ACTIVE Merchant sign-in |
| Dashboard/session/roles | Merchant dashboard, refresh restoration without filling credentials again, denied cross-role routes, restored authorized dashboard |
| Payments | Review/cancel/confirm UI, INR 13.25 creation and SUCCESS processing, listing and native Open payment detail selection |
| Merchant isolation | Merchant B's UI lookup of A's UUID returns denied/not-accessible without rendering payment data |
| Investigation | Explicit button click; observed authorized response must be scoped to the payment and RAG_LLM/SUCCEEDED with knowledge references; customer-view report renders |
| Refunds | Explicit partial 3.25 and remaining 10.00 refund review/confirmation; exact displayed totals 13.25 INR, remaining 0.00 INR, REFUNDED status |
| Payment link/customer | USD 25.00 link UI; validate URL origin/path in memory; anonymous checkout review/cancel/confirm, receipt, paid-state refresh and mobile overflow |
| Merchant/Admin chat | No automatic AI submission, Shift+Enter newline, Merchant Enter send/Admin Send button, observed saved-turn response requires RAG_LLM/SUCCEEDED and knowledge references; actual answer element renders |
| Saved history | Creation on first explicit send, native list/select/rename, confirmation dialog, page-refresh restoration with no inference resubmission, delete and private-content removal |
| History isolation | Merchant B and Admin list their own empty histories while Merchant A's saved conversation still exists |
| Cross-tab logout | Same-session second tab clears after sign-out; protected AI route returns to login; Admin/B sign-out complete through browser |

Selectors come from the released vanilla frontend: existing IDs and accessible labels/names, scoped to the current workspace/dialog/row. No test IDs, injected application hooks, access-token injection, DOM-only fake responses, or application rebuilds are used. Response observation verifies status/contract after UI actions; it never drives API mutations itself. Financial checks normalize fixture decimal text, not arithmetic with JavaScript floating-point values.

## Privacy and result acceptance

Traces, video, screenshots, HAR, downloads and storageState exports are disabled/not used. Playwright private failure output stays in an owner-only runner directory and is never uploaded. Browser requests are restricted to the frontend origin `http://127.0.0.1:15500`; direct Java/Python/model access and third-party browser requests are blocked. The runner separately downloads packages/model before browser execution.

The custom reporter never serializes exceptions, browser console/stdout/stderr, response bodies, attachments, checkout URLs, passwords, cookies, JWTs, generated answers or database rows. It emits a bounded, exclusive mode-600 JSON with only allowlisted test/stage codes, status and numeric duration plus fixed flags. The full suite requires all three named tests and every expected journey stage; a partial run cannot report success. Existing service diagnostics retain their bounded redaction/fail-closed behavior and run before cleanup.

Only these outputs are uploaded, for three days:

- `sanitized-browser.json`
- `sanitized-browser-bootstrap.json`
- `sanitized-browser-final.json`
- Existing redacted service diagnostic `.log` files and status JSON on failure
- Separate `sanitized-cleanup.json`

Successful acceptance requires a green job, all browser tests/stages passing, `nativeBrowserTested=true`, `modelInferenceVerified=true`, matching published artifact bootstrap, final synthetic counts, and cleanup `success=true`, `volumesAbsent=true`, `containersAbsent=true`. A successful screenshot, model HTTP 200, offline mock or API-only result cannot replace these checks.

## Operator procedure after separate approval

Review/approve the tooling diff, then separately authorize a focused commit/push. Open **Actions → Native Chromium published-image E2E (no publication) → Run workflow → main** only after execution approval. There are no toggles to disable model verification and no publication input. Do not rerun automatically after failure.

The runner executes:

```sh
python3 -B -m unittest discover -s deploy -p 'test_*.py'
python3 -B deploy/release_artifact_e2e.py fixtures
# Node/disk admission, locked npm/Chromium install and checksum-verified model.
# Pull and start the existing image-only Compose project.
python3 -B deploy/browser_bootstrap.py seed
(cd deploy/browser-e2e && npm test)
python3 -B deploy/browser_bootstrap.py final
# Failure diagnostics and sanitized artifact retention occur before cleanup.
python3 -B deploy/release_artifact_e2e.py cleanup
# Always retain the separate cleanup JSON.
```

These are workflow-stage descriptions, not permission to run Docker locally or spoof the hosted-runner guards. No Mac service, database, volume, model or backup is targeted.

## Offline validation and known limits

Run the full deployment unittest suite, `node deploy/browser-e2e/offline.test.mjs`, `node --check` for the JS files, Python AST checks, Ruby YAML parsing, npm-lock JSON checks, targeted publication scanning and `git diff --check`. Helper tests run without Playwright or Chromium; their mocked reporter success is not native browser evidence.

The three Chromium tests remain **unexecuted** until the separately approved GitHub run. Browser binary installation/discovery, exact runtime focus/layout/race behavior and the 8 GiB admission budget have not been validated locally. Auto-waiting and explicit response/UI readiness replace sleeps, but a genuine released UI defect must fail and be investigated rather than bypassed. Existing stale landing-page descriptions are not silently corrected by this suite. It is functional keyboard/mobile coverage, not a WCAG certification or pixel-perfect visual baseline.

This suite does not prove real bank settlement, live gateway integration, external HTTPS deployment, every error/fault-injection branch, every Admin account-management mutation, clipboard behavior, Firefox/WebKit behavior or full accessible-screen-reader operation. Unresolved financial navigation safeguards remain intact; tests wait for actual completion rather than force navigation. On failure, retain only sanitized artifacts, preserve published images and prior evidence, and request review before another manual attempt. No automatic retries, image rebuilds, local recovery or destructive database restore is permitted.

Offline implementation verification: **149 deployment Python tests passed**, including **14 new browser-policy/bootstrap/syntax tests**. The Node helper/reporter suite has **12 passing tests** and is also invoked by one deployment test (do not add those counts as independent runtime E2E checks). JS/Python syntax, YAML/JSON and lockfile checks, targeted publication scanning and whitespace checks passed. Playwright package/browser execution was not run locally because Node 18 is below the required runtime; no local browser, Docker or model was installed or executed. The existing API/publication workflows, Compose/image locks, fixture generator and cleanup helper are byte-identical to the reviewed release baseline. No commit, push or dispatch occurred.
