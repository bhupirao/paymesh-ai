# Phase 6.7.1 — Landing page and role-based portals

Date: November 14, 2026. Scope: existing frontend extension only. No Java/Python business logic, account registration backend, live financial operation or Docker implementation.

## 1. Architecture and routing

Read root README.md, PROGRESS.md, frontend README and Phase 6.6 QA report before changes. Inspected the existing HTML/CSS, app, memory-session, API/workspace and payment/detail modules, proxy/allowlist and tests, plus actual Java AuthController and JwtTokenService. Reused completed payment, refund, gateway and investigation workflows.

One index.html and ES module graph now support six explicit frontend routes:

| Path | View / guard |
|---|---|
| `/` | Public B2B PayMesh AI landing page |
| `/merchant/signup` | Public registration structure; local validation only |
| `/merchant/login` | Merchant sign-in; requires actual MERCHANT role before accepting session |
| `/merchant/dashboard` | Guarded Merchant workspace |
| `/admin/login` | Admin sign-in; requires actual ADMIN role before accepting session |
| `/admin/dashboard` | Guarded Admin workspace |

Same-document History API navigation (pushState/replaceState/popstate) keeps the existing module-memory access token alive between views. State contains no token, password, form payload or role selector. Refresh creates a new JavaScript session, so a dashboard URL redirects to its matching sign-in until authenticated. Successful sign-in replaces the login history entry with the matching dashboard. Back/Forward reevaluates access and cannot reveal a logged-out dashboard. Public navigation does not silently log out an active session. Changing portal while sign-in is pending invalidates that response and blocks overlapping login submission until it settles.

The frontend Python development server now serves the same shell **only** for these six exact GET paths, preserving the existing `/index.html` alias and `/assets/...` test/asset restrictions. No wildcard shell/file fallback was added. A direct unknown route receives sanitized HTTP 404; an unknown same-document route displays a public not-found view. Case/trailing-slash/encoded/query variants are not silently normalized into supported pages. API paths never fall through to the shell.

Serving static dashboard markup does not authorize data: it contains no financial/user records or tokens. Java remains the authority for every protected business request.

### Frontend activation requirement

The old running Python process serves changed static files immediately but does not reload Python handler code. A read-only check observed `/` = 200 (new shell) and `/merchant/login` = 404 on the existing PID 85275, while the **new handler** passed all six-route/direct-refresh tests on a temporary listener. Activating direct routes therefore requires a **frontend-only server restart with explicit user approval**, as required by the user's preservation rule. No backend restart is needed. Activation was subsequently approved and completed; the final record below confirms live route serving. Do not start a duplicate listener.

## 2. Created and modified files

Created:

- assets/js/portals/router.js — explicit route resolver, role guards, same-document history and session updates.
- assets/js/portals/signup.js — pure local preview validation, fixed country/business-type choices.
- assets/js/portals/view.js — public/portal view orchestration, role-specific navigation and signup preview events.
- assets/js/portal-tests.html and portal-tests.js — mocked portal/role/history/signup tests.
- tests/test_portal_routes.py — six additional server-route test methods.
- PHASE-6.7.1-PORTALS-REPORT.md — this report.

Modified:

- index.html — local landing page, signup structure, guarded shell wrappers, role-aware login labels, dashboard overview/placeholder areas and preserved workspace controls.
- assets/css/app.css — responsive B2B public layout, architecture illustration, onboarding form and portal navigation styles.
- assets/js/app.js — connects routing, role-specific login and logout to existing modules; captures credentials before deliberately replacing an existing session.
- assets/js/features/workspace.js — optional required-role acceptance and cancelled-login response guards; default legacy test callers remain compatible.
- assets/js/features/payments-view.js — exposes existing read-view navigation to portal sections without replacing financial behavior.
- dev_server.py — exact frontend GET route set only; business API proxy behavior unchanged.
- frontend README — route URLs, activation requirement, current test counts and next-phase boundaries.

Historical phase reports and existing tests are retained. No Java/Python AI/payment service implementation, protected configuration, migrations, schema, database records, model assets, backups or archives were changed.

## 3. Implemented versus planned features

Landing page: branding/navigation; hero and explicit Merchant CTA/sign-in/Admin link; payments, exact simulated refunds, backend gateway recovery visibility and AI investigation; labeled upcoming payment links/customer checkout/chatbot; six-step How It Works with register/approval/checkout explicitly marked upcoming; local technology/security highlights and simulation footer. The flow illustration contains architecture labels, not fabricated transactions/statistics.

Merchant sign-in: email-or-username text entry, password, existing visibility toggle, autocomplete, required constraints, loading/duplicate guard, fixed errors and signup navigation. The entered value is the existing provisioned login; email works only if that is the account login. No unsupported email lookup API is invented.

Admin sign-in: separate route/context using the same real authentication API, actual ADMIN role check and no signup link. `/admin/signup` remains denied. Merchant-only and ADMIN-only accounts cannot enter the other role's dashboard merely by choosing its URL. A dual-role account may enter a portal only because the corresponding actual role is present; Admin role alone never substitutes for MERCHANT.

Merchant dashboard: overview; Payments plus existing Create payment; Payment Links placeholder; existing selected-payment Refunds; current-payment AI Investigation Reports; planned chatbot/profile/settings. No complete payment/report list or aggregate API is fabricated.

Admin dashboard: overview; planned Merchant Management/Pending Approvals; supported known-UUID Payment Monitoring and Refund Monitoring; current-payment investigation; planned chatbot and Audit/Settings. Backend-authorized cross-merchant operations remain available; merchant management/approval/audit browsing/signing/settlement controls are not invented. Creation remains subject to Java's existing verified-merchant rules.

Signup preview: first/last/business names, business email, mobile, business type/country choices, password/confirmation visibility, terms/privacy acknowledgment, signup navigation and accessible local errors. The button says Check form · preview only. Valid fields produce an explicit **registration unavailable; no account created; nothing sent** message. There is no signup network request, fake success, account or approval. Passwords clear after a valid preview; the form resets on leaving its route. Choices and 8–72-character validation are preview UX constraints, not a new backend registration policy. The notice instructs users not to enter real passwords; no binding production terms/privacy policy is claimed.

## 4. Security decisions and limitations

Authentication still posts only `{login,password}` to `/api/v1/auth/login`, consumes the real `{accessToken,tokenType,expiresIn,expiresAt}` contract and validates token shape/expiry. The optional required role checks actual decoded claims before installing a new session. No role field is sent to Java. JWT signature/current account/membership checks remain server-side; frontend role checks are presentation guards, not a security boundary.

Memory-only JWT storage, automatic expiry/focus/visibility checks, logout clearing, session versioning and stale financial/investigation response rejection remain. Public routing retains a valid session, but submitting a replacement login deliberately clears the prior session/private recovery state; the wrong-role login notice explains that consequence. No persistent sessions, refresh token, cookies, local/session storage, IndexedDB or URL tokens were added. Page refresh still requires sign-in. Existing unresolved financial intents remain in memory during ordinary same-document navigation; no operation or retry runs automatically.

Signup is local-only and uses safe fixed validation messages. No password is logged or placed in history. Login's native fallback is POST rather than URL-query form submission; all functioning login behavior still uses the API client. Signup has no working submit endpoint and a preview button; the server denies POST frontend routes. Java cannot be bypassed by the frontend route choice.

Proxy Host/Origin/cross-site/path/framing checks, CSP, no-store, request/response limits, redirect denial, fixed upstream, header policy and API allowlist are preserved. Only six frontend GET paths were added. No direct Python/LLM, database, settlement-token or webhook-signing browser access was added. All dynamic labels and errors use textContent/createElement; assets are local Bootstrap/system fonts/CSS. No framework, paid service or dependency was installed.

Desktop/mobile CSS and semantic navigation/forms were reviewed statically: responsive public navigation, single-column forms/cards at narrow widths, table-local scrolling, visible focus, labels/error associations, section focus and active overview/placeholder navigation. Actual rendering/assistive-technology results remain manual, because the browser skill reported unavailable. Existing Phase 6.6 manual release gates remain open unless separately confirmed.

## 5. Actual test results

| Suite | Result |
|---|---|
| Original proxy tests | 12 passed |
| API client | 10 assertions passed |
| Authentication/session | 34 assertions passed |
| Payment workflows | 94 assertions passed |
| Gateway/refund workflows | 125 assertions passed |
| Investigation | 149 assertions passed |
| Phase 6.6 QA | 18 assertions passed |
| New explicit server-route tests | 6 passed |
| New portal/history/role/signup tests | 73 assertions passed |

All existing **442 checks** remain green. New work adds 6 Python test methods plus 73 JavaScript assertions (18 Python tests and 503 JavaScript assertions overall). Python discovery initially reported **18 tests passed in 1.188 seconds**; the final rerun passed all 18 in 1.148 seconds. A sandbox-restricted rerun could not bind test sockets (zero tests executed); the approved loopback rerun passed. Individual per-route/subtest assertions are not inflated into test-method counts.

Existing/new JavaScript modules ran with mocked fetch, history and DOM/event doubles in the available JavaScript runtime. The actual assembled app was also exercised with mocked login: landing visibility, Merchant dashboard and nav, public navigation retaining memory token, deliberate Admin session replacement with credentials captured before clearing, Admin dashboard/nav, logout and wrong-role rejection. Those observations are not browser visual certification or live account login.

New tests cover exact routes, GET-only access, direct URLs/repeated refresh requests, unknown/encoded/nested routes, retained test pages/legacy alias, denied signup APIs, public navigation, matching/wrong/dual roles, actual login request fields, malformed token, cancelled/duplicate sign-in, Back/Forward, unauthenticated dashboard, logout/expiry, fresh-document session loss and signup required/type/password/consent constraints. Existing financial and investigation suites continue testing exact money, idempotency, stale results and safe DOM without live financial requests.

## 6. Exact URLs and manual verification

The approved frontend handler reload is complete. Use:

- http://127.0.0.1:5500/
- http://127.0.0.1:5500/merchant/signup
- http://127.0.0.1:5500/merchant/login
- http://127.0.0.1:5500/merchant/dashboard
- http://127.0.0.1:5500/admin/login
- http://127.0.0.1:5500/admin/dashboard

Tests (mocked requests only): `/assets/js/tests.html` (10), `auth-tests.html` (34), `payment-tests.html` (94), `refund-tests.html` (125), `investigation-tests.html` (149), `qa-tests.html` (18), `portal-tests.html` (73), all under http://127.0.0.1:5500/assets/js/.

```bash
python3 -m unittest discover -s frontend/tests -v
```

Manual checks, with no new financial mutations:

1. Open `/` and each sign-in/signup URL directly, then refresh. Confirm landing branding, local assets and honest Available/Upcoming labels. Check registration/approval/checkout/chatbot are not portrayed as working.
2. Enter synthetic signup preview values; test missing fields, invalid email/mobile, mismatched passwords and missing acknowledgment. Check password toggles and inline error/focus behavior. A valid preview must explicitly say no account created/nothing sent. No network signup request should appear. Navigate away and Back; entries should have been cleared. Do not enter real credentials in this preview.
3. From a fresh tab, open both dashboard URLs. They should redirect to their matching sign-in. Sign in privately as a provisioned MERCHANT through Merchant login; confirm Merchant overview/navigation. Sign in privately as ADMIN through Admin login; confirm Admin overview/navigation. Do not copy passwords/JWTs into console or reports.
4. Test wrong-role credentials in each login: ADMIN-only at Merchant login and MERCHANT-only at Admin login must be denied with no accepted replacement session. A valid matching-role session on its login URL redirects to its dashboard. No public admin registration exists.
5. From an authenticated dashboard, use the PayMesh home link and return through the matching sign-in link or Back/Forward. The same-document session remains until logout/expiry. Browser reload/new tab loses it and requires login. Unknown direct `/unknown` is sanitized 404; unknown same-document navigation cannot expose private content.
6. Use Payments/Payment Monitoring to read an existing authorized UUID and verify preserved details, gateway history, refund history and current AI report controls. Use Merchant A/B isolation checks from previous reports without mutating records. No automatic create/process/refund/investigation should occur from navigation. Do not repeat earlier mutation runbooks.
7. Sign out from each portal. Verify token/private views/results clear and Back cannot restore dashboard access. Wait for natural expiry or use mocked tests for lifecycle/error/race cases. Pending sign-in navigation must ignore the old response and restore controls when it finishes.
8. At desktop and about 375px, inspect wrapping public navigation, hero/cards, signup/login controls, sidebar, long UUIDs and table scrolling. Use Tab/Shift-Tab/Enter/Space, skip link, labels, visible focus, status announcements and placeholder navigation. Confirm no fake totals, merchant records, approval buttons or saved reports appear.

No actual browser automation or new live protected business verification is claimed. The active frontend handler now serves all six explicit routes, including direct path refresh.

## 7. Service and Git preservation

Initial listener PIDs: frontend 85275/5500, Java 83515/18080, Python 80995/8000 and llama.cpp 79855/8082. No backend service was restarted. The frontend-only reload was explicitly approved through command approval and completed: old PID 85275 was replaced by PID 92049 on port 5500. Java 83515, Python 80995 and llama.cpp 79855 remained unchanged.

Initial Git index SHA-256: `a52651e89daedace6c23a228841271d50fcfcebc1d8a9ec1c7b8aced901abad4`. Initial staged binary diff SHA-256: `8320e120b02fb591a4cf472e059911b26a510360961f2658e911885278a60c4a`.

A later observation detected concurrent external staging: index `b9f2a7d2f236b45816aea4b420812c04637d559c25373e29b581f300b2efe065`, staged diff `a1ee2d4fc68187c8553e187df7659242ae39800a5ee0c5148779d1c0e57afb51`. The agent issued no git add/commit/push/reset/clean or index mutation and did not restore the prior index. Final index/staged-diff hashes remain the later values above; the concurrent staging was left untouched. The tracked non-frontend working diff matches the initial snapshot. Pre-existing staged/unstaged work is retained.

No Java/Python business changes, database connections/schema/migrations, original paymesh_db/port 8080 access, live financial/settlement/webhook/investigation actions, protected configuration, secret/backup/archive changes or Docker implementation occurred.

## 8. Blockers and honest boundaries

The frontend-only activation was approved through the command approval tool and completed. There is no remaining route-activation blocker. No essential backend change is needed for this frontend phase. Signup, email verification, approval, persistent sessions and recovery cannot be made operational using current APIs; they are future backend design work, not silently bypassed or simulated successes.

Root README/PROGRESS Phase 6.6 release caveats remain historical QA context; the new portal report/updated frontend README records current implementation scope and supersedes the old landing-only entry assumptions. The in-app browser is unavailable, so actual visual/mobile/native-form/Back verification remains manual even though mocked/server routing tests passed.

## 9. Next-phase requirements (not implemented)

Phase 6.7.2 and subsequent authorized work must define real merchant signup DTO/API, normalized identity/uniqueness rules, password policy/hashing, verification-token storage/lifetimes/single-use semantics, email delivery using an explicitly chosen free solution, rate limiting/abuse prevention, consent/privacy policy and safe account-enumeration behavior. Pending accounts must not gain verified merchant access. Review offline provisioning compatibility and isolated migration/tests before changing existing account state.

Admin approval requires actual authorized/audited backend APIs, state transitions, registry/membership checks, concurrency/version/revocation behavior and safe listing/filtering contracts. Do not expose settlement/HMAC secrets or invent approve/reject UI actions before those contracts exist.

Phase 6.7.3 persistent sessions require an explicit secure design (e.g. reviewed HttpOnly/Secure/SameSite cookies, refresh rotation/revocation, CSRF/origin checks and session expiry handling). Do not move access tokens into browser storage to retain login across refresh. Password recovery needs generic responses, expiring single-use tokens, replay/rate-limit protection, secure free email delivery and session invalidation. No such endpoint or security change is part of this phase.

Stop after Phase 6.7.1. No Phase 6.7.2 or Dockerization begins automatically.

## Final activation verification

Read-only HTTP checks returned 200 for all six required routes and the new portal test page, and 404 for `/unknown` and `/admin/signup`. The active login response retains no-store, CSP, nosniff and no-referrer headers. Java readiness and Python health were UP; llama.cpp health was OK. Python health reported model connectivity NOT_VERIFIED, not a fresh inference test. No protected business request was issued. The assembled mocked app also exercised navigation node reuse across Merchant/Admin workspace replacement; existing operation listeners remain attached. Final portal rerun passed 73 assertions.
