# Phase 6.2 — Login, JWT authentication and role-based workspace

Implemented November 14, 2026. Scope ends at login/session lifecycle, role presentation and read-only payment lookup. No creation, processing, refund, gateway-history or investigation screens implemented.

## Inspection and reuse

Read Phase 6.1 report, frontend README, index.html, CSS, app.js, API configuration/client, session module, DOM helper and tests.js, together with actual Java AuthController, JwtTokenService and BusinessEndpointCatalog. Reused local Bootstrap 5.3.3, tokens/layout, ES modules, central API client, safe DOM helper, single HTML entry and existing static server. No proxy, route allowlist, CORS or backend security changes. No new dependencies or external asset requests.

The initial Git index had changed since Phase 6.1 through pre-existing user work; this phase recorded and preserved the **current** starting hashes, not the historical Phase 6.1 hashes. Initial status and unstaged diff were captured under /tmp before edits.

## Implemented features

- Responsive navy, white and blue login, local branding/system typography and simulation notice. Visible username/password labels, appropriate autocomplete, required/max-length validation, keyboard focus indicators, password show/hide with aria-pressed, generic feedback and disabled duplicate submissions.
- Password field cleared immediately upon submission and hidden again; no credentials or token values are rendered or logged. Native browser validity focuses invalid fields. Username whitespace is rejected and surrounding whitespace trimmed before login; password is never trimmed.
- HTTP 401 invalid-credential feedback, 429 Retry-After feedback (seconds or HTTP date, bounded to one day), 403 access-denied feedback, 400 input feedback, network/service error handling. No raw server messages are displayed. No automatic retry. Rate-limit feedback instructs waiting; it does not automatically resubmit or implement a countdown lockout.
- Single-entry authenticated workspace with supplied login identity, subject UUID, decoded roles, actual expiry timestamp and logout. ADMIN receives cross-merchant lookup presentation; MERCHANT receives membership-scoped presentation. Future supported features appear as labeled, noninteractive “not yet implemented” items.
- Read-only UUID lookup displays all eight implemented payment response fields, with loading/empty result/error behavior. Previous results clear before each new lookup. No statistics, fabricated feeds, profile, merchant dropdown or unsupported endpoint requests.

## Actual authentication contract

`POST /api/v1/auth/login`, JSON `{login:string,password:string}`. Java login must be nonblank and at most 255 characters. Password DTO is a nonnull char[] of at most 72 characters; frontend additionally requires a nonempty password. Success 200: `{accessToken:string,tokenType:"Bearer",expiresIn:900,expiresAt:ISO-8601 instant}`. Errors include 400, 401, 413, 429/Retry-After and 503. The proxy limits login bodies to 4096 bytes; unusual long Unicode input may exceed that byte limit even within character constraints.

JwtTokenService issues RS256 tokens with iss, aud, sub (user UUID), jti, iat, nbf, exp, authorization_version and roles. Login has no separate role or merchant fields; JWT has no merchant membership identity. There is no profile, refresh-token or server logout API.

Before accepting a response, session validation checks Bearer token type, exact 900-second expiresIn, bounded three-part base64url JWT shape, parseable header/payload, RS256 algorithm, canonical UUID subject, nonempty recognized roles, integer iat/exp with 900-second lifetime, UTC expiresAt matching exp, future expiry and bounded remaining lifetime. Malformed responses produce a fixed message and are never accepted. Decoding **does not verify the JWT signature**; this validation is defensive response-shape checking, not client authorization. Java remains the only authority and verifies signature, account, roles, authorization version and merchant membership. No keys are fetched or embedded.

## Session and role security

Token is retained only in the session module variable; public session snapshots omit it. No localStorage, sessionStorage, cookies, URL tokens or logging. Refresh loses the session. Login identity is the operator-entered name, not a profile API assertion. Subject is a user UUID, not a merchant ID. Merchant ID is displayed only when returned with an authorized payment.

Actual expiresAt drives a timer. Token access, window focus, visibility changes and pageshow check expiry; timers are rearmed when needed. Expiry clears session, private result, lookup state and identity presentation and returns to login. Logout clears session and private UI immediately. It is **client-side clearing, not server-side JWT revocation**: an issued token may remain valid until expiry or server-side account revocation. There is no invented logout/refresh call.

Protected 401 responses clear session even if error-body parsing fails. A failed login 401 leaves the login view with generic credential feedback. Protected 403 retains the session. Every session set/clear increments a version; API responses and workspace login/lookup completions are checked against that version and per-operation sequence. Responses after logout, expiry or replacement are ignored, including stale 401 responses that must not clear a new session. Duplicate requests are blocked in both state controller and API client. Pending requests are not retried; network cancellation/ignoring results is not server cancellation. Login credentials necessarily exist briefly in the browser request and cannot be reliably erased from JavaScript engine memory; they are never persisted or intentionally exposed.

Role checks only select labels/navigation. ADMIN may perform backend-authorized cross-merchant business access; merchant memberships are resolved by Java, never inferred. Settlement-token operations and sensitive actuator routes remain excluded from the proxy and UI.

## Payment lookup

Only `GET /api/v1/payments/{paymentId}` is invoked. Input requires the full canonical 8-4-4-4-12 hexadecimal UUID (case insensitive); whitespace, missing hyphens and query fragments are rejected before fetch. HTML pattern validation and module validation both enforce this. Bearer header is supplied by the existing client.

Response validation checks all string fields, matching paymentId, finite numeric amount and parseable createdAt. It is rendered with createElement/textContent as a definition list: paymentId, merchantId, amount, currency, customerId, paymentMethod, status, createdAt. The view performs no financial arithmetic; amount is shown from the parsed backend number with currency separately. Exact decimal computation/aggregation is not implemented and must not be added using binary floating-point arithmetic.

401 returns to login; 403 shows denial and preserves session; 404 says “Payment not found or not accessible to this account” without disclosing existence. Invalid UUID, malformed response, network failure, unavailable service and loading states are distinct. Lookup does not process or mutate the payment.

## Files created and changed

Changed:

- index.html — login, session/workspace and UUID lookup markup.
- assets/css/app.css — responsive login/form/detail styles, hidden handling, future-feature presentation.
- assets/js/app.js — form events, password toggle, lifecycle initialization and safe UI updates.
- assets/js/auth/session.js — validated memory session, presentation claims, timer/listeners/versioning.
- assets/js/api/client.js — session-aware duplicate keys and stale-response rejection; generic messages instead of raw upstream text.
- assets/js/tests.js — existing regression tests updated for validated synthetic token contract.
- assets/js/features/README.md — current module scope.
- tests/test_dev_server.py — shell-content assertion updated; security regression cases unchanged.
- README.md — current usage and test pages.

Created:

- assets/js/features/workspace.js — testable login/lookup state, feedback and role presentation.
- assets/js/components/payment.js — safe field renderer.
- assets/js/test-fixtures.js — synthetic unsigned test token shape and payment fixture; never valid Java credentials.
- assets/js/auth-tests.html and auth-tests.js — mocked authentication/lifecycle/lookup test page.
- PHASE-6.2-LOGIN-AUTHENTICATION-REPORT.md — this report.

Unchanged: dev_server.py, API configuration/route allowlist, DOM helper, Bootstrap files, Phase 6.1 report and all backend files.

## Automated verification

- Python proxy regressions: **12 tests passed** (0.583 seconds), using an ephemeral loopback listener and mocked Java responses. Initial restricted-shell attempt could not bind; approved test execution succeeded. No proxy implementation change or existing service restart required.
- Authentication/lifecycle/lookup: **34 assertions passed** in auth-tests.js. Covers valid/malformed responses, roles, login pending/duplicate prevention, generic credentials, 429, unavailable/network feedback, logout/pending login, canonical UUID rejection, exact lookup route/auth header, success, all eight fields, malicious markup rendered as text, 404 concealment, 403 retention, 401 clearing, stale 401/replacement, late success after logout, focus/visibility expiry, timer delay and expiry callback.
- Existing API client regressions: **10 assertions passed** in tests.js, including origin/path restriction, redirect policy, JSON, duplicate prevention, 401 clearing and expired session.
- JavaScript tests used mocked fetch and minimal DOM/event test doubles in the available JavaScript runtime. No Node build system, dependency or package file was introduced. These are module/state tests; they do not establish full browser layout/native form validation behavior.
- In-app browser skill connection returned unavailable. No live account logins or authenticated lookup runs were performed by the agent. Browser test pages and the exact manual checks below remain for user verification. Earlier user-confirmed browser results for Phase 6.1 are historical, not a claimed Phase 6.2 browser run.
- Read-only health checks: existing frontend shell served updated HTML; proxied payment health RUNNING; Java readiness UP; Python UP with configured RAG_LLM (health reports modelConnectivity NOT_VERIFIED); llama.cpp status ok. No protected business request was made to a live backend.

## Exact startup and manual browser verification

Existing frontend listener is PID 85275 on port 5500. **Reuse it**: reload http://127.0.0.1:5500/ to receive updated static assets. Do not start a second server or restart any service. Only if no frontend listener exists in a later session, start from repository root with `python3 frontend/dev_server.py`.

Automated checks available to the operator:

```bash
python3 -m unittest discover -s frontend/tests -v
curl --fail http://127.0.0.1:5500/ -o /dev/null
curl --fail http://127.0.0.1:5500/api/v1/payments/health
```

Open test pages in separate tabs (mocked fetch only, no password needed):

1. http://127.0.0.1:5500/assets/js/tests.html — expect `PASS: 10 assertions`.
2. http://127.0.0.1:5500/assets/js/auth-tests.html — expect `PASS: 34 assertions`.

Live manual checks use existing provisioned accounts. Enter credentials privately in the form; do not print or copy them into reports, screenshots, console commands or test fixtures. Username/password values are intentionally not included here.

1. Reload the main page. Confirm simulation notice, username/password labels, password toggle, required-field feedback, keyboard Tab/Shift-Tab/Enter operation and visible focus. Submit an intentionally incorrect password once: generic invalid-credentials feedback, cleared password and enabled retry. Avoid deliberately flooding the live login rate limiter; mocked tests cover 429.
2. Sign in as Merchant A. Confirm Merchant workspace, entered login identity, MERCHANT role and expiry timestamp. Lookup `c072351f-4646-4288-b8ca-6758d4e521f3`; confirm actual fields, merchant identity from response and SUCCESS if unchanged. Lookup `f1c5e798-fa14-438c-972d-d1a6247a5ffb`; confirm actual refunded record (no refund operation). Compare all eight fields to authorized backend data without editing records.
3. Still Merchant A, lookup Merchant B payment `c6f797c0-c810-4730-bac2-19cb8504a87d`. Expect the shared missing/inaccessible message and no previous payment details. Session remains active for a normal 404. Try a malformed UUID; expect validation and no API request.
4. Sign out. Confirm login appears immediately, identity/results clear and the password remains empty. Use any open in-flight mocked-test scenario to verify late responses cannot restore the private workspace. Browser Back must not restore authenticated data; hash navigation stays within the entry page.
5. Sign in as Merchant B. Lookup `c6f797c0-c810-4730-bac2-19cb8504a87d`; confirm authorized fields. Sign out.
6. Sign in as Admin. Confirm Admin workspace and cross-merchant wording. Lookup Merchant A `c072351f-4646-4288-b8ca-6758d4e521f3`, then Merchant B `c6f797c0-c810-4730-bac2-19cb8504a87d`; both should be authorized by Java. No settlement/reconciliation controls should appear. Sign out.
7. Login again and reload. Expect fresh login, no authenticated view and no saved password from application state (browser password-manager behavior is independent). For real expiry testing, leave a session until the shown expiry, including an unfocused/background interval; return and confirm sign-in-required feedback and cleared private details. Mocked tests cover 401, 403 and immediate clock-driven expiry without altering services or credentials.
8. At roughly 375px width and desktop width, verify no clipped forms/UUIDs, usable password toggle, stacked lookup controls and readable labels. Test keyboard-only flow and screen-reader status announcements. Confirm future features are explicitly unavailable and no fabricated totals or feeds appear.

Do not create/process/refund payments, invoke AI, deliberately stop services, or use the original port 8080/application database while verifying.

## Limitations

Browser visual/mobile/accessibility QA and actual-account authorization checks remain manual and unclaimed. UI role claims are not cryptographically verified in the browser. In-memory access reduces persistence but does not make JavaScript immune to XSS; retain CSP/local assets and safe DOM rendering. Loopback HTTP proxy remains development-only, with shared login rate limit by proxy IP. Timer precision depends on browser scheduling; focus/visibility/token access recheck wall-clock expiry. No automatic refresh, server revocation/logout endpoint, profile API, merchant list, payment list or aggregate API exists. Complete business workflows and timeline/investigation UI remain outside this phase.

## Preservation confirmation

Initial and final index SHA-256: `b1520b2e8de23f70fe3ecd1730359027f76d28da4cb019bc576461fa7f5b3187`.
Initial and final staged binary diff SHA-256: `dc76251c1d38002ad665e1cb88e23ea985389cb05303742fa7aca8cd6c9d0227`.
Non-frontend unstaged binary diff matched the initial snapshot. All task writes were under frontend/. Existing staged content is preserved; no git add/commit/push/reset/clean was issued.

Listeners and PIDs before/after are unchanged: frontend 85275/5500, Java 83515/18080, Python 80995/8000, llama.cpp 79855/8082. Existing frontend static serving was reused. No service stop or restart occurred. No backend implementation, protected configuration, migrations, database schema, financial records, backups or archives were changed. No database connections or access to paymesh_db/port 8080 occurred. Automated fetches used synthetic credentials against mocks; live checks were public health/static GETs only. No live login, payment mutation or AI investigation was executed.

Phase 6.2 ends here. Subsequent payment creation, processing, refund and investigation work awaits explicit instruction.
