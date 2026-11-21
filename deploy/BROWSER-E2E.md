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

Offline implementation verification: **153 deployment Python tests passed**, including **18 browser-policy/bootstrap/syntax tests**. The Node helper/reporter suite has **32 passing tests** and is also invoked by one deployment test (do not add those counts as independent runtime E2E checks). JS/Python syntax, YAML/JSON and lockfile checks, targeted publication scanning and whitespace checks passed. Playwright package/browser execution was not run locally because Node 18 is below the required runtime; no local browser, Docker or model was installed or executed. The existing API/publication workflows, Compose/image locks, fixture generator and cleanup helper are byte-identical to the reviewed release baseline. No commit, push or dispatch occurred.

## First native run: safe failure diagnostics

Run `44798083129` used commit `1288bbf7b2fabc1917e652ece146aacb0d57ffc9`. Installation, published-image startup, Admin-only bootstrap, and explicit container/volume cleanup passed. The desktop keyboard test and complete journey failed with reported durations of zero; mobile was skipped and the artifact retained no journey stages. This does **not** establish whether Chromium launched. It also does not demonstrate an application, selector, authentication, financial-flow or AI defect. The old reporter discarded the error details needed to establish the precise cause. Complete retained job logs contained no corresponding browser/fixture error signature.

The diagnostic-only correction leaves the workflow, Playwright launch/configuration options, test assertions, image digests and application unchanged. Each test now reports its allowlisted identifier, last failed named stage or fixed setup/body/teardown identifiers, bounded duration/elapsed milliseconds, fixed error category/code, fixed timeout/assertion category and (only when available) a reviewed source-file basename and numeric line. The classifier inspects at most 8192 characters of error text in memory solely to select approved constants; it never stores or emits message text, stack, snippets, matcher values, URLs, prompts or responses. Unknown errors stay `UNCLASSIFIED_TEST_FAILURE`; no guessed cause is recorded.

An automatic test fixture observes the already-required Playwright browser. Only a connected Chromium object can create the exclusive mode-600, test-specific `browser-launch-TESTCODE.json` witness under the existing private run directory. It neither launches an additional browser nor changes launch settings. The reporter accepts only an owner-owned, private, bounded witness matching that test's fixed identifier. Raw witnesses are not uploaded. Their validated status is copied into the existing sanitized report as `SUCCEEDED`; a recognized launch failure is `FAILED`; absent/malformed/untrusted evidence is `NOT_OBSERVED`, never proof that launch failed. Other critical pass requirements remain unchanged.

Offline tests cover launch/configuration/worker errors, timeouts, UI assertions, runtime/unknown errors, setup failures, named stages, secret canaries and mismatched/unprotected witnesses. Another separately approved GitHub run is required to identify the original failure. Do not rerun automatically, expose raw Playwright output, relax assertions or interpret these offline tests as browser success.

## Secure handling of Playwright output-directory recreation

The exact live cause of run `44862755587` remains unproven: both failed tests reported `HOOK_OR_FIXTURE_SETUP`, `fixtures.js:5`, `UNKNOWN`, and no validated Chromium witness. This patch corrects an independently demonstrated lifecycle incompatibility and makes the next run diagnosable; it does not claim the original run is fixed or that Chromium has now executed successfully.

`privateDirectory()` now validates the canonical mode-700, runner-owned run directory and accepts only its single fixed `browser-private-output` leaf. It rejects traversal, external names, symlinks, non-directories and foreign ownership. Creation is non-recursive. The helper opens the leaf with `O_DIRECTORY | O_NOFOLLOW`, checks inode/device identity and ownership against path metadata, applies mode 0700 to that validated descriptor only, and verifies permissions and path identity afterward. This accommodates Playwright deleting/recreating the leaf with an ordinary umask without weakening the private-parent boundary. It never recursively chmods, changes the parent/secrets/worker subdirectories, deletes paths, or repairs unknown directories. The optional environment argument supports isolated unit fixtures; production configuration still defaults to the real hosted-runner environment and retains all existing guards. Concurrent hostile same-user mutation is outside the dedicated-runner threat model; detectable identity changes fail closed.

Reporter guard-code coverage now includes `PRIVATE_OUTPUT_REQUIRED`, `FIXED_OUTPUT_DIRECTORY_REQUIRED` and `FIXED_CREDENTIAL_REQUIRED`. ANSI decoration is removed in memory; only a complete allowlisted first line, optionally prefixed by `Error:`, is accepted as a guard code. Arbitrary prefixes, suffixes or later-line mentions remain unknown. No message/stack text is retained or emitted.

Each failed test now prints a `BROWSER_FAILURE_DIAGNOSTIC=` JSON line with only fixed test/stage/category/error codes, bounded elapsed milliseconds, launch status and fixed assertion/timeout categories. Global infrastructure failures use fixed identifiers. The existing exclusive mode-600 `sanitized-browser.json` remains the retained source of detailed sanitized results; raw errors, paths, URLs, credentials, cookies, checkout tokens, prompts and answers are never copied into these stdout lines. The final result marker remains unchanged. New tests reproduce recreation with mode 0755, repair to 0700, nonrecursive behavior, symlink/type/ownership/path rejection, post-chmod verification, decorated codes, unknown errors and safe stdout output.

Implementation/offline checks only: 152 deployment tests and 26 Node tests pass. Node tests are also invoked inside one deployment test, so these are not additive native-browser results. No browser installation, local Docker, model download, workflow dispatch, commit or push was performed. Workflow definitions, scenario/assertion files, launch configuration and release digest locks remain unchanged. A separately approved commit/push and new manual run are required to verify live behavior.

## Registration-stage URL assertion diagnosis

Run `44864454565` on `e91ef12fb72c4df8756374087f34cfc06ac07a32` passed both responsive/keyboard tests and proved Chromium launch. The journey failed in `MERCHANT_REGISTRATION_VALIDATION` at the helper's `expect(page).toHaveURL(ORIGIN + '/merchant/dashboard')` after registration, during the first explicit Merchant login. Its safe location was `fixtures.js:99`, not a signup redirect assertion. Reaching that line means both registration POSTs returned 201/PENDING_APPROVAL and both success links were visible. Registration itself intentionally stays on signup with an explicit sign-in link; successful pending Merchant login is routed to the dashboard and displays the pending-approval panel. The actual frontend registration and router modules are now exercised in offline regression fixtures to preserve those distinct contracts.

The dashboard URL assertion is retained unchanged: source does not support accepting another URL or simply waiting longer. The original artifact did not retain the login HTTP result, actual route classification or visible login-feedback classification, so the cause of login not reaching that route remains **UNKNOWN**. No released application change or image rebuild is justified by this evidence.

On a future login assertion failure, the helper observes only the browser's existing login response status (no body/token/header access), classifies the current location into a small route enum plus a suffix-present boolean, and maps known visible feedback to fixed codes. It records only those typed fields, the portal role and fixed test identifier in an exclusive private per-test witness; unknown routes/feedback remain generic. It never records the URL, query, hash, checkout token, account login, password, JWT, cookie, raw feedback or response body. The original assertion is rethrown. The reporter validates witness ownership/mode/size/test identity and value allowlists before copying safe `loginState` fields into JSON/stdout diagnostics. Raw witness files are not uploaded. No navigation retry, additional API call, altered assertion or skipped scenario is introduced.

Offline verification after this diagnostic-only addition: 153 deployment tests and 32 Node helper/reporter tests passed (Node is also invoked within one deployment test). Syntax/security/whitespace checks passed. Existing browser scenario files, route assertions, workflow, Playwright configuration and release image locks are unchanged. Another separately approved manual run is required to determine whether the login response was rejected, frontend validation failed, session state changed, or the route differed. No actual URL or root cause is invented.
