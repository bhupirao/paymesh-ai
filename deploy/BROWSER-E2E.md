# Native Chromium E2E against published PayMesh AI v1.0.0

Status: implementation/offline verification only. **No Chromium run, workflow dispatch, image build, or local Docker execution was performed to prepare this suite.** A green offline regression does not prove browser success.

## Verified baseline and release identity

Published-image API E2E run [44793055710](https://github.com/bhupirao/paymesh-ai/actions/runs/44793055710) succeeded on tooling commit `57a737520c1095195e7549e132ad8de87a388f64`. Its separate cleanup artifact confirmed `success=true`, `volumesAbsent=true`, and `containersAbsent=true`. Preserve this evidence as API proof; this suite adds actual browser proof only when it runs successfully.

The new manual-only workflow reuses `compose.release-verify.yaml`, `release-v1.0.0-images.json`, the runner fixture generator, image identity/empty-database validation, and guarded project-only cleanup. All four public application image digest locks remain unchanged, with source `cefa7df83a5bf16d011e82041c95e2d93b9c637b`. No application files are mounted over the images and there are no build steps. PostgreSQL 16 is the fifth service and is always a fresh project-scoped volume. Public repositories are pulled anonymously; no Docker Hub login, publication environment or deployment secrets are needed.

## Dependencies and execution limits

`browser-e2e/package.json` pins `@playwright/test` **1.65.1** exactly. The npm lockfile includes registry URLs and SHA-512 integrity for transitive dependencies. Playwright is third-party Apache-2.0 software; this does not change the project's source-available copyright terms.

Only an Ubuntu 24.04 GitHub-hosted runner is supported, using its preinstalled Node 22 or 24. The admission check fails if that changes; it never installs an unreviewed runtime automatically. The whole job is limited to 55 minutes, the test suite to 30 minutes, and the serial journey to fifteen minutes (including auth-budget admission waits). Chromium is the only browser; one worker and zero retries prevent overlapping financial/inference intent. Browser actions have 15-second bounds, navigation 30 seconds, and observed AI responses 55 seconds. Existing server inference limits remain unchanged.

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

Offline implementation verification: **156 deployment Python tests passed**, including **21 browser-policy/bootstrap/syntax tests**. The Node helper/reporter suite has **41 passing tests** and is also invoked by one deployment test (do not add those counts as independent runtime E2E checks). JS/Python syntax, YAML/JSON and lockfile checks, targeted publication scanning and whitespace checks passed. Playwright package/browser execution was not run locally because Node 18 is below the required runtime; no local browser, Docker or model was installed or executed. The existing API/publication workflows, Compose/image locks, fixture generator and cleanup helper are byte-identical to the reviewed release baseline. No commit, push or dispatch occurred.

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

## Respecting the published authentication rate limit

Run `44865570006` on `b49762aea51d79b1f1723f7dfb77f3ffc3f11151` confirmed the first Merchant login received 429 and remained on MERCHANT_LOGIN. The producing component is Java `LoginRateLimitFilter`, backed by `LoginRateLimiter`. Published defaults are 10 admitted requests per client in a 60-second fixed bucket, with at most 10000 client buckets. The key is `getRemoteAddr()` only (bounded fallback `unknown`); username, endpoint and role are not part of the key. All five POST endpoints—login, register, refresh, logout, logout-all—share this limiter. Successful and rejected authentication requests consume admission slots before controller authorization. `Retry-After` reports remaining window seconds. Client-supplied forwarding headers are not trusted.

The fixed frontend proxy connects to Java through 127.0.0.1 and does not forward X-Forwarded-For. Therefore all disposable browser roles/contexts share one Java IP budget. This is an existing private-demo security boundary, not a demonstrated authentication defect; production trusted-proxy identity/capacity design would require a separate architecture/security review, not forged headers in tests.

The accessibility tests plan six full portal loads; each released app startup attempts cookie refresh. Two signup loads add two refreshes and successful registrations add two more admissions. The subsequent Merchant login-page load attempts another refresh before the first explicit login. Thus the source-derived pre-login plan exceeds ten auth admissions in a few seconds even though the accessibility forms submit no valid credential requests. Bootstrap performs SQL only, not login. The journey plans four credential logins in total (pending A, Admin, active A/B), but failed on the first; exact wire totals/extra focus-driven refreshes were not retained. No claim of an independently captured complete request ledger is made.

The correction is entirely test-side scheduling in `auth-budget.js`. It shares one driver-side budget across contexts and auth endpoint kinds in a worker. Native navigation/reload and valid registration/login/logout submits reserve capacity **before** the browser initiates their auth request. Existing network observers count unplanned auth requests too, avoid double-counting a matched reservation, and update activity on request completion/failure. After nine planned/observed slots, admission waits for 61 seconds without auth activity: the unchanged 60-second server window plus one second for epoch-second granularity. This conservative quiet period starts from the latest request/response, rather than assuming the server bucket began at a client timestamp. Individual admission waits are capped at 90 seconds. No HTTP request is held behind a network interception delay; existing browser API timeouts begin only when the admitted UI action runs.

This is not an arbitrary sleep or Retry-After login retry: every UI action/request executes at most once, no submitted credentials or financial/inference intent is resubmitted, and the server limit is neither disabled nor increased. A witnessed 429, tracking failure or unexpected long-running auth activity fails closed. Public checkout has no portal auth startup and consumes no reserved auth slots. All five real server endpoints remain unmocked and authentication/authorization assertions remain intact. The journey timeout is explicitly raised to 900 seconds to budget the necessary window waits; operation timeouts, one worker, zero retries, the 30-minute suite ceiling and the 55-minute job ceiling are unchanged.

The test module is worker-local; if a worker fails/restarts, the job already failed and the replacement worker might encounter residual server budget. That must remain a failure, not trigger an automatic retry or a fresh Java process. A new separately approved workflow run always has a fresh isolated stack.

Offline verification: 156 deployment tests pass, including a temporary JDK-only harness compiling the unchanged production Java limiter and exercising 16 checks for allowed admissions, excess rejection, Retry-After, expiry and distinct clients. No Spring/Maven build, database or local service is started. The 41 Node tests include fake-clock pacing, mixed roles/endpoints, unplanned refreshes, response-completion timing, no double counting, bounded waits and rejection without retry. Existing Java integration tests already cover forwarded-header spoofing and endpoint roles; the complete Java and AI-service Python suites were not rerun because their sources are unchanged. The new browser run remains pending. No backend, proxy, security configuration, workflow, Compose, package dependency or release digest was changed, and no image rebuild is required for this test-side correction.

## Coordinated journey audit after run 44867570752

Reviewed runner commit: `6245d7794397dbb7dd1727e6865cc550a1952c15`.
Published application contract: `cefa7df83a5bf16d011e82041c95e2d93b9c637b` (the four image locks remain unchanged).
This is an offline correction and source audit, **not a successful browser run**.

### Exact latest failure and evidence

The sanitized artifact identifies `journey.spec.js:39`: filling the Admin `Search` input with `getByLabel('Search', {exact:true})`. Chromium launched. Desktop and mobile tests passed; registration/pending login/logout passed in 64,107 ms; the Admin stage failed in 16,320 ms. Overall journey elapsed time was 80,577 ms. This was an action timeout, not exhaustion of the 900,000 ms test budget. The previous stage included legitimate auth-budget waiting.

Admin login's dashboard assertions completed before line 39. The artifact has no login-failure witness or recorded Admin HTTP status; do not claim a measured Admin 200/429. The source reproducer establishes the navigation defect: cold loading `/admin/merchants` with an initially empty in-memory session rewrites the route to `/admin/login`, then restoration sends it to `/admin/dashboard`. The dashboard also has an enabled **Apply / Look up** control, but deliberately has no **Search** field. Thus the old enabled-button assertion could pass on the wrong view. The exact live URL was not retained, but the published router's transition reproduces this mismatch offline.

### Corrections and retained requirements

- Authenticated deep links now use the actual `#portal-nav-extra` buttons (Merchant Management, Payments, AI Assistant, etc.) and assert the resulting route. Payment-link creation uses Payment Links followed by the real Create Payment Link control. No injected router calls, API-only replacement or synthetic successful responses.
- Hard-load/session tests still use real navigation/reload, wait for the single native refresh response and require its intended status. Login waits for its one native response; credential requests are never retried. Cross-role hard navigation is retained to verify denial.
- The ownership denial assertion accepts the actual 403 **Access denied** wording in addition to existing inaccessible/not-permitted wording. The required 403/404 status and empty payment display remain.
- Admin approval still requires unique email search, native detail selection, ownership reference, attestation, cancel/reopen and explicit confirmation. It now also requires the returned Merchant ID and ACTIVE status.
- Response observers attach rejection handling immediately so an action failure does not leave an unhandled response-wait rejection. Original caller-visible failure is preserved.
- Auth-budget reservation now covers the waiting interval. A second admission for the same page fails instead of overwriting the first reservation. Different-page requests share the same budget; excess concurrent waiters fail at the existing bounded wait limit.
- Named browser contexts explicitly use 15-second action and 30-second navigation deadlines. No server, model, credentials, limiter configuration, dependency or published image changed.

### Complete contract matrix

PASS below means source/contract review passed, not an unexecuted browser result. FIXED denotes a test-side defect corrected in this patch. UNKNOWN requires actual Chromium execution. BLOCKED denotes a demonstrated published-application gap that is intentionally still asserted.

| Journey | Route, controls and response contract | Authentication/data dependency | Audit |
|---|---|---|---|
| Desktop/mobile validation | `/merchant/login`, `/merchant/signup`, `/admin/login`; stable login/signup IDs, native Tab/Enter, inline errors | Three startup refreshes per test, no valid login submissions | PASS; both passed latest run. Pixel/layout checks outside these viewports remain UNKNOWN |
| Registration | `/merchant/signup`; `#signup-check`, required fields, `#signup-success-link`; POST register 201, PENDING_APPROVAL | Two synthetic accounts, fresh DB; two refreshes + two registrations | PASS; passed latest run |
| Pending Merchant | `/merchant/login` → `/merchant/dashboard`; `#pending-onboarding`; logout 200 | Pending-role token, no financial access; refresh/login/logout share IP budget | PASS; passed latest run |
| Admin login | `/admin/login` → `/admin/dashboard`; identity and Admin workspace visible | SQL-bootstrap Admin only; one refresh and one login | PASS source; reached subsequent failing action, exact live HTTP status UNKNOWN |
| Merchant search/detail | SPA `/admin/merchants` → `/admin/merchant`; Search, Apply / Look up, exact email row/Open; GET items + authorized detail | ADMIN; two actual registered profiles; reads do not consume auth budget | FIXED hard-load/dashboard mismatch |
| Native approval | Ownership reference, attestation, Review approve, focused confirmation, cancel/reopen, Confirm approve; POST 200 ACTIVE | ADMIN; PENDING_APPROVAL + registrationUserId; exact Merchant ID required | PASS contract; runtime UNKNOWN |
| Active Merchant/dashboard | Fresh login for A/B, dashboard refresh, workspace visibility, role-denied hard routes | New active sessions after approval; login/refresh/logout count globally | FIXED restore-response synchronization; runtime UNKNOWN |
| Payment create/process/list | `#nav-create`, review/confirm IDs, POST payment 201 CREATED, process 200 SUCCESS, SPA Payments/Open payment | Merchant A membership; synthetic 13.25 INR payment; idempotency remains frontend-owned | FIXED list deep-link navigation; runtime UNKNOWN |
| Merchant B isolation | Known payment lookup, 403/404, denial feedback, empty result | Separate B browser context, A-owned UUID | FIXED valid 403 feedback wording; runtime UNKNOWN |
| AI investigation | `#investigate-button`; POST investigate, matching payment scope, visible Customer view | Authorized current selected payment; RAG_LLM + SUCCEEDED + knowledge references | FIXED response deadline; real inference UNKNOWN in this browser run |
| Refunds | Refresh details, Review refund/focus, Confirm refund; 201 SUCCESS; 3.25 then 10.00 INR, total13.25, remaining0, REFUNDED | Fresh 30-second refund snapshot, complete authorized history; no automatic mutation retries | PASS contract; runtime UNKNOWN |
| Payment link/customer checkout | SPA create route; 201 link + generated token URL; unauthenticated native checkout, review/back/confirm; 200 PAID, receipt reload | Synthetic25.00 USD/CARD; isolated customer context; checkout has no portal refresh | FIXED link-route navigation; runtime UNKNOWN |
| Merchant/Admin chat | SPA AI routes; textarea Enter/Shift+Enter, explicit Send; completed saved turn response200; visible nonempty answer | Current role eligibility/profile; creation20s + chat45s; actual model success required | FIXED navigation, readiness and response budget; runtime UNKNOWN |
| Saved list/open/rename/delete | History details, exact title, search and selected row; GET lists/messages, POST rename/delete200, visible version/title/cleared transcript | Owner/role/context checks and expectedVersion preserved; no inference on load | PASS contract apart from refresh below; runtime UNKNOWN |
| AI refresh restoration | Actual reload must retain AI route and visible saved answer without another send | Session bootstrap + history-state bookmark | **BLOCKED** by released router; assertion retained, no explicit-load workaround |
| Cross-tab logout/protected route | Same-context second dashboard tab, native logout, both login forms, protected workspace hidden | HttpOnly refresh cookie, BroadcastChannel revocation; no exported auth state | PASS source; real ordering UNKNOWN |
| Teardown | Existing diagnostics first, scoped container/volume ownership checks and cleanup on both outcomes | Unique disposable project; no external/shared volume deletion | PASS existing offline regressions; latest run artifact reports containersAbsent=true, volumesAbsent=true |

### Published-application blocker (not silently patched)

`frontend/assets/js/portals/router.js` calls `history.replaceState(null, '', loginPath)` during cold protected-route resolution before `persistence.restore()` completes. The original AI route and its `history.state.paymeshConversation` pointer are lost. Restoration then selects the dashboard. An offline test executes the actual router with the same unauthenticated→restored lifecycle and proves both losses. The automatic-history-refresh assertion remains, with an additional explicit AI-route assertion to expose this contract failure early. There is no test-side workaround that can honestly prove automatic restoration of the original pointer after it was erased.

A separately approved frontend application fix and new frontend image/digest are needed to satisfy that full requirement. Existing released images are preserved. The test-side corrections can be reviewed/committed separately; a claim that the entire unchanged-image journey is now expected to pass is blocked. An investigative run could collect later runtime evidence, but is not a substitute for addressing this known gap.

### Bounded time budget

- Auth limiter remains10 requests/60s per remote IP, all five auth endpoints shared. Test admission remains9 planned slots,61s quiet window,90s maximum per admission. The pacing wait occurs before starting login/register/logout response observers. No sleeps are added inside browser click/navigation timeouts.
- Source-counted planned auth operations are approximately31 across all three tests after SPA navigation replaces unnecessary cold deep links. Normal case: three quiet-window resets ×61s =183s across the suite. These are planning counts, not a recorded wire ledger; timers/focus refreshes are observed and counted conservatively. Continued unexpected auth traffic produces a bounded failure, not unlimited waiting.
- Ordinary response observers:25s =20s normal client deadline +5s reporting margin. POST investigation:70s =65s client deadline +5s. POST conversation send:70s covers creation20s + chat45s +5s. GET history remains25s. AI composer readiness25s covers its eligibility read20s +5s.
- Single browser action15s, navigation30s and ordinary expect15s remain unchanged. Each additional native context explicitly receives the same action/navigation limits.
- Complete journey900s is retained: planning allowance of up to four ordinary quiet windows244s, three AI waits210s, plus446s for native interactions and bounded reads. It is not extended to hide the latest missing selector. Accessibility tests remain300s, suite global1800s, job55min, one worker, zero retries. None of these is an unlimited wait or a guarantee that the sum of all worst-case deadlines fits; the outer deadline deliberately stops a stalled run.

### Safe action diagnostics

The reporter retains only allowlisted last-completed and pending action codes, latest observed numeric HTTP status, existing timeout/assertion categories, elapsed time, Chromium witness and allowlisted source basename/line. Action codes cover login, search input/results, detail, approval review/dialog/cancel/submit/confirmation, payments, refunds, checkout, AI/history and logout. Nested checkpoints preserve the innermost failed action. The last observed status is **not** asserted to belong to a pending action when concurrent requests exist. No payload, actual URL, error message/stack, token, cookie, prompt or answer is emitted. Evidence stays in the existing mode600 sanitized report and stdout schema; raw browser artifacts remain disabled.

Offline results for this coordinated patch: **160 deployment Python tests passed** (including the unchanged production limiter's **16 isolated Java checks**) and **50 Node helper/reporter tests passed**. The Node suite is also invoked by one deployment test; these counts are not additive browser cases. JavaScript/Python syntax, YAML/JSON parsing, targeted secret-pattern checks, retained UI assertion checks and `git diff --check` passed. The Git index and original status/staging were preserved. No Chromium, Docker, inference, service change, image build, commit, push or workflow dispatch was performed. Full Java and AI-service Python suites were not rerun because application sources were unchanged. Runtime readiness remains **BLOCKED for a complete successful journey on the existing frontend digest** by the refresh/bootstrap defect described above; the test-side patch is ready for review.
