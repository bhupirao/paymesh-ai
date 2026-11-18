# PayMesh AI frontend foundation

Current: Phase6.8.3 customer checkout implemented; combined V12/V13 activation and native
browser verification PENDING. Live remains operator-supplied V1–V11. Phase681/682 are not
closed. Separate `/checkout/{43-character-token}` HTML entry never restores portal sessions
or sends cookies/JWTs. All payment execution is simulated and explicitly confirmed. OTP
remains disabled; private outcome controls are gated and disabled by default.
See [Phase683 report](PHASE-6.8.3-CUSTOMER-CHECKOUT-REPORT.md).

From the repository root:

```bash
python3 frontend/dev_server.py
```

Open **http://127.0.0.1:5500/** (use this literal address, not localhost). Existing Java demo must already run on 127.0.0.1:18080 for API use. Starting this server does not start, stop or reconfigure any backend. Ctrl-C stops only this foreground frontend server. Port 5500 is fixed; a collision fails without taking over another process.

Safe checks in another terminal:

```bash
curl --fail http://127.0.0.1:5500/ -o /dev/null
curl --fail http://127.0.0.1:5500/api/v1/payments/health
python3 -m unittest discover -s frontend/tests -v
```

Tests bind an ephemeral loopback listener and mock the upstream; they never create payments or contact Java. Browser API client tests: open http://127.0.0.1:5500/assets/js/tests.html and check the displayed result. Those tests mock fetch and make no business requests.

Open the existing server and reload to receive static asset changes; do not start a second server when port 5500 is already listening. The login screen makes no requests until submission. Use your provisioned credentials; no passwords are bundled. Refresh discards the session and requires sign-in. Logout clears the local session, not the server JWT. Java authorizes every lookup; decoded roles only affect presentation. Payment creation, processing and refunds use explicit separate reviews. AI investigation is a separate read-only action in authorized payment details. See [the Phase 6.1 report](PHASE-6.1-FRONTEND-FOUNDATION-REPORT.md) for contracts and implementation plan. See [Phase 6.2 report](PHASE-6.2-LOGIN-AUTHENTICATION-REPORT.md) for the current behavior, test results and exact manual checks.

Bootstrap source: official https://github.com/twbs/bootstrap/tree/v5.3.3 ; files downloaded from https://raw.githubusercontent.com/twbs/bootstrap/v5.3.3/dist/css/bootstrap.min.css and https://raw.githubusercontent.com/twbs/bootstrap/v5.3.3/LICENSE . MIT license retained in assets/vendor/bootstrap/LICENSE. CSS only; no Bootstrap JavaScript required by this shell. System fonts avoid external downloads.

This loopback development server is not a production web server. Deployment should use an HTTPS reverse proxy serving assets and forwarding the same narrow Java business route/method allowlist. Never forward AI, settlement, webhook or sensitive actuator paths to the browser.

Authentication/lookup mocked tests: open http://127.0.0.1:5500/assets/js/auth-tests.html in a separate tab. Expected: PASS: 34 assertions. API regression page remains PASS: 10 assertions. Test pages use synthetic fixtures and make no real login or payment calls.

Phase 6.3 adds Create payment and explicit CREATED-only processing reviews within the same HTML entry. Merchant ID must be entered explicitly. Creation intent/key remain in memory for deliberate exact retries; refresh/sign-out/expiry loses them and may prevent recovery of an uncertain creation. No mutation retries automatically. Phase 6.4 adds gateway history/refunds and Phase 6.5 adds explicit investigation. See [Phase 6.3 report](PHASE-6.3-PAYMENT-CREATION-PROCESSING-REPORT.md).

New mocked workflow tests: http://127.0.0.1:5500/assets/js/payment-tests.html — expected PASS: 94 assertions. These never create/process live payments. Existing test pages remain 10 and 34 assertions.

Phase 6.4 details open automatically from authorized lookup; created/processed results also have Open payment details. Refunds require fresh complete history and a separate review/confirmation. Unknown or stale history blocks new refunds. Uncertain refund intents retain the exact amount, payment UUID and key in memory; only deliberately retry that exact intent. Browser refresh/sign-out/expiry loses recovery state. Confirmed refund records remain distinct from any failed totals/status refresh. No bank refund arrival is verified.

New mocked tests: http://127.0.0.1:5500/assets/js/refund-tests.html — expected **PASS: 125 assertions**. Existing pages remain 10 API, 34 authentication and 94 payment assertions; Python proxy suite remains 12 tests. No test page performs live financial operations.

See [Phase 6.4 report](PHASE-6.4-GATEWAY-HISTORY-REFUNDS-REPORT.md) for contracts, recovery limits, preservation checks and the planned user-operated INR 200.00 + 300.00 refund steps. The USD payment remains reserved for later AI investigation; no live mutations were executed by the agent.

AI Investigation (Phase 6.5): open an authorized payment's details and explicitly select Investigate with AI. Nothing investigates automatically. The browser calls only Java through the existing proxy, with a 65-second client timeout. Results show actual scenario, customer/technical views, separate certainty labels, provenance, unavailable evidence, RAG/LLM status, knowledge relevance and limitations. Results are snapshots and clear on observed changes/refresh. Timeout does not stop backend work; retries are explicit. Financial intents block investigation, and loading investigation blocks new financial confirmations.

New mocked tests: http://127.0.0.1:5500/assets/js/investigation-tests.html — expected **PASS: 149 assertions**. All five pages use mocked fetch; none performs live financial operations or investigations. Existing page counts remain 10 API, 34 authentication, 94 payment, 125 gateway/refund assertions; Python proxy suite remains 12 tests.

See [Phase 6.5 report](PHASE-6.5-AI-INVESTIGATION-DASHBOARD-REPORT.md) for actual schema/timeout/security contracts, four planned user-operated live investigation scenarios, remaining verification and proposed final QA. Reuse the existing server and reload; no services need restarting. No live protected request was performed by the agent.

Phase 6.6 final QA: all existing 424 checks reran successfully (12 proxy tests + 412 JavaScript assertions), with **18 new QA assertions** at http://127.0.0.1:5500/assets/js/qa-tests.html. Those tests use mocked fetch only. JSON-null errors now preserve HTTP status, details live feedback is outside busy content, and generatedAt is explicitly labeled as analysis preparation **before retrieval/LLM generation**, not completion or inference duration. Backend behavior is unchanged.

See [the final QA/release-readiness report](PHASE-6.6-FINAL-QA-REPORT.md) for pending actual-browser refresh/logout confirmation, 375px/desktop accessibility checks, safe timing observation and the planning-only five-service Docker prerequisites. Earlier financial mutation runbooks are historical; do not repeat payment/refund confirmations during final QA. Phase 7 must separately resolve a free runtime compatible with macOS 12 and explicitly reviewed container trust/bootstrap settings. No Docker implementation or final commit was performed.

Phase 6.7.1 adds a public landing page at `/`, Merchant registration **preview** at `/merchant/signup`, separate `/merchant/login` and `/admin/login`, and role-guarded `/merchant/dashboard` and `/admin/dashboard`. All six use the same document and memory-only session; normal navigation preserves the session, refresh still requires sign-in. Only the matching actual role enters a portal. Signup never submits or creates an account; approval, persistent sessions, recovery, payment links and chatbot remain planned.

The frontend-only handler reload was approved and completed; all six required paths now return HTTP 200 on port 5500 (frontend PID 92049 at verification). Java, Python AI and llama.cpp were not restarted. Reuse this server and reload the browser; do not launch a duplicate listener. Future Python handler changes still require approval before restarting a running service. See [the Phase 6.7.1 report](PHASE-6.7.1-PORTALS-REPORT.md) for activation status, exact route/manual checks and security decisions.

All existing 442 checks passed. New tests: 6 Python route tests (18 Python tests total) and http://127.0.0.1:5500/assets/js/portal-tests.html — **PASS: 73 assertions**. Existing JavaScript pages retain counts 10/34/94/125/149/18; no test performs live registration or financial operations. Run `python3 -m unittest discover -s frontend/tests -v` from the repository root.

## Phase 6.7.2 — merchant registration (activation pending)

Signup now connects to `POST /api/v1/auth/register` through the narrow Java proxy. New accounts sign in using the same email/password to a PENDING_APPROVAL onboarding dashboard; Java denies financial APIs until future authorized approval. No email verification, OTP, SMTP or Mailpit is used. Existing ACTIVE Merchant/Admin access is preserved. This supersedes the Phase 6.7.1 preview-only signup description.

Historical Phase6.7.2 implementation-time note, superseded by the final Phase6.7.3 status below: the Java artifact, Flyway V9 and frontend proxy reload had **not** yet been activated on the running demo. Explicit approval is required for migration and the two relevant process restarts; Python/LLM need no restart. See [Phase 6.7.2 report](PHASE-6.7.2-MERCHANT-SIGNUP-REPORT.md) for exact controlled activation and manual checks. Do not perform live signup until activation is approved.

New mocked page: http://127.0.0.1:5500/assets/js/registration-tests.html — 39 assertions. Existing 521 checks pass; with 2 new proxy tests and 39 new registration assertions, the frontend total is 562. JavaScript counts are mocked runtime execution, not actual browser verification. All passwords/tokens remain transient; refresh requires sign-in. Admin approval is Phase 6.7.4; persistent sessions/password recovery are Phase 6.7.3.

Phase 6.7.2 final isolated Java verification: **231 tests passed** (226 existing + 5 new registration integration tests), no failures/errors/skips. Live migration and activation remain pending approval.

## Phase 6.7.3 — implementation complete; local-demo verification complete with limitations

The source now implements Remember Me, HttpOnly refresh-cookie restoration/rotation, current/all-device logout and the explicitly insecure on-screen OTP demonstration. Access tokens and all recovery state remain memory-only. V10/server/proxy activation is complete; this supersedes earlier refresh-requires-sign-in descriptions. A browser reload still loses memory-only financial intent keys; no financial mutation is automatically replayed.

Cookie configuration is explicit: `paymesh.sessions.origin` must be HTTPS by default. The local HTTP exception additionally requires demo/development profile, loopback bind, port18080 and exact frontend origin. The approved private local demo uses this explicit local configuration; production HTTPS requirements are unchanged. Cookie refresh uses single flight and Web Locks; browsers without Web Locks use sign-in rather than automatic refresh/restoration. Do not expose the local Python development server publicly.

Recovery routes: `/merchant/forgot-password` and `/admin/forgot-password`. Default behavior is unavailable, with no OTP controls. The insecure display-code flow requires the separately reviewed local demo flag, real database/connector checks, private keyed-digest secret, explicit no-public-proxy operator confirmation and per-account disposable eligibility. No email/SMS/SMTP/Mailpit. No production/public recovery or merchant approval implementation was added.

New mocked tests: http://127.0.0.1:5500/assets/js/session-recovery-tests.html — **67 assertions**. All nine JavaScript test pages total **609 assertions**; proxy discovery totals **25 tests**. They make no live auth/recovery/financial requests. Exact contracts, security decisions and definitive limited closeout: [Phase 6.7.3 report](PHASE-6.7.3-SESSIONS-PASSWORD-RECOVERY-REPORT.md).


Phase 6.7.3 final status (November15,2026): **IMPLEMENTATION COMPLETE; LOCAL-DEMO
VERIFICATION COMPLETE WITH DOCUMENTED EVIDENCE LIMITATIONS; GO FOR CONTINUED
LOCAL-DEMO DEVELOPMENT; NOT PRODUCTION SECURITY CERTIFICATION.** Baselines:
283 isolated Java tests (zero failures/errors/skips), 634 mocked frontend checks,
50 mocked operational tests, 30 operator-confirmed browser checks. No tests were
rerun for documentation closeout. Final operator read-only audit verified disabled
recovery, account/eligibility/reset-audit/grant state, counts6/4/4/2/6/4, readiness/
health/frontend and exact archive row comparisons. Persistent-session functionality
remains available. The protected recovery key remains stored but unused; it was not
erased. Do not reactivate OTP or repeat deactivation.

Historical pre-reset-family proof is unavailable for both accounts; the Merchant's
additional version increment remains unexplained. Activation/deactivation fingerprints
were not recorded, and no successful pre-audit fingerprint exists. These limits do not
become historical PASS claims because current checks passed. Browser-confirmed behavior
is separate evidence. On-screen OTP is deliberately insecure and must never be enabled
publicly; production-grade password recovery remains unimplemented. At the Phase673 closeout, Phase674 was ready to begin. Its later official closeout
is recorded below; the Phase673 historical limitations remain unchanged.


## Phase 6.7.4 — official Admin workspace closeout

**COMPLETE WITH DOCUMENTED EVIDENCE LIMITATIONS.** V11 controlled activation and
Admin dashboard/Merchant management are complete. GO for continued private local
portfolio development; not production security certification.

Existing suites previously passed:300 isolated Java tests (zero failures/errors/skips),
752 frontend checks (722 mocked JavaScript assertions +30 proxy tests),105 mocked
operational tests. Packaging/syntax checks passed. No tests were rerun for documentation
closeout. Admin mocked test page remains:
http://127.0.0.1:5500/assets/js/admin-tests.html (113 assertions).

Final operator-run read-only evidence confirms counts6/4/4/2/6/4, exact contents of all
eight financial tables matching the pre-V11 archive, and retained-row revocation evidence
for all five Phase674 security events. Disposable Merchant offline recovery and approval/
suspension/reactivation explain version2→6. The actual Admin Profile password test used
the specifically authorized demo-admin account,version3→4; otp-admin-demo is unchanged.
OTP is disabled; runtime health and persistent-session configuration passed. Do not
repeat activation, recovery or deactivation for this closeout.

The initial36-item browser confirmation remains operator-reported; no revised exact
pass total is claimed. Successful live rejection remains unverified: no rejection-test
registration or successful MERCHANT_REJECT event exists. No direct live JWT acceptance/
replay test, inventory of legacy no-sid tokens or backup test restore occurred. Phase673
historical limitations remain. Public on-screen OTP is prohibited; public production-grade
password recovery is unimplemented. Strict verification and the one-event protected
Admin authorization remain intact.

See the [definitive Phase 6.7.4 report](PHASE-6.7.4-ADMIN-DASHBOARD-MERCHANT-MANAGEMENT-REPORT.md)
for exact evidence and limitations. The subsequent Phase6.8.1 implementation is recorded below; activation remains pending.


## Phase 6.8.1 — Merchant dashboard and profile (activation pending)

New single-document Merchant routes:/merchant/dashboard,/merchant/payments,
/merchant/refunds,/merchant/profile,/merchant/security. Real owned/currency-separated
counts/amounts, paginated filters and recent records; honest legacy profile nulls;
password change with current-password verification, explicit confirmation and fresh login.
The new APIs require ACTIVE MERCHANT-only identity with one active verified membership;
other account statuses retain the existing limited onboarding. Existing detail/refund/
gateway/explicit AI and create/process flows remain shared; no automatic mutation/AI.
Payment Links and chatbot remain placeholders. No new migration; OTP stays disabled.

Final automated results:315 isolated Java tests,847 frontend checks (813 mocked JS
assertions +34 proxy tests),109 mocked operational tests. New mocked browser-compatible
page:http://127.0.0.1:5500/assets/js/merchant-tests.html —91 assertions. These runtime
checks are not actual browser verification. Full existing suites passed; native mobile/
keyboard/layout and live Merchant isolation/password checks remain operator tasks.

Only after deployment approval:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/deploy-phase681-demo.sh"
```

Hidden DB password; confirmation `DEPLOY_PHASE681_V11_OTP_DISABLED`. The script verifies
existing V11/counts/identity/config, protected backup and financial/account fingerprints,
then restarts only verified Java/frontend and checks health/routes/OTP=false while
preserving Python/LLM. It performs no login/password/financial/AI mutation. Do not run
old activation/recovery scripts or relax historical audit checks for new phase activity.
See the [Phase6.8.1 implementation report](PHASE-6.8.1-MERCHANT-DASHBOARD-PROFILE-REPORT.md)
for contracts, limits, complete manual checklist and test results. No live deployment
or browser verification was performed by the agent. Later phases are not started.


### Phase681 analytics and account switching (redeployment pending)

Both dashboards now include local Chart.js4.4.8 MIT charts and exact equivalent tables.
Charts have their own UTC Today/7/30/custom-day filters and INR/USD selector, independently
labeled from existing record summaries. Complete scoped aggregates are read through
new GET /api/v1/merchant/analytics and /api/v1/admin/analytics. No migration or financial
mutation; all amount math stays in NUMERIC/BigDecimal and authoritative decimal strings.
Plot-only Number conversion is approximate. Vendor source/license/hash are in
assets/vendor/chartjs/README.md (including bundled @kurkle/color MIT license). No CDN.

The account menu shows actual own login/role and profile/security links. Switch Account
requires confirmation and existing operation guards, then secure logout/cookie clearing
and cross-tab state clearing. Failure is unconfirmed, blocks sign-in and exposes explicit
Finish Sign Out. Do not refresh/share while logout is uncertain. Normal tabs intentionally
restore the same cookie session; use separate Chrome profiles, an Incognito session or
another browser for simultaneous independent accounts. No per-tab cookies/storage.

Full automated totals:322 isolated Java,895 frontend checks (859 mocked JS+36 proxy),
111 mocked operational tests. New safe mocked page:
http://127.0.0.1:5500/assets/js/analytics-switch-tests.html —46 assertions.
No native browser verification is implied. After operator approval only:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/redeploy-phase681-analytics.sh"
```

Confirmation:`REDEPLOY_PHASE681_ANALYTICS_OTP_DISABLED`. New private backup/evidence
prefix preserves the original Phase681 deployment. V1–V11 only, OTP=false, counts
6/4/4/2/6/4, content and service checks remain. Phase681 stays open and Phase682 is
not implemented. See the Phase681 report enhancement checklist and exact API semantics.

## Payment Links (Phase682; activation pending)

Merchant routes: `/merchant/payment-links`, `/merchant/payment-links/create`.
Create/review/confirm, owned search/filter/paging (5 rows), detail/copy and explicit
cancel are implemented. Checkout URLs remain non-operational until Phase683.
No payment is created or processed on link creation/navigation. Memory-only uncertain
intent/key must be retried deliberately; refresh/logout loses its recovery state.
New mocked pages (no actual business operations):

- http://127.0.0.1:5500/assets/js/payment-link-tests.html
- http://127.0.0.1:5500/assets/js/pagination-tests.html

Do not run V11-only deployment scripts against the V12 artifact. A separate approved
V12-aware activation is required; no live action was performed in implementation.

Phase682 final automated results:336 isolated Java tests;1022 frontend checks
(983 mocked JavaScript assertions +39 proxy tests);111 operational mocked tests.
Packaging, syntax and diff checks passed. Native browser/live V12 activation pending.
See the Phase682 report for complete contracts, limitations and operator checklist.

## Customer checkout — Phase683 (NOT activated)

Public `/checkout/{token}` displays the one linked order; Pay requires review/confirmation.
No real card/CVV/bank/UPI PIN/OTP is collected. GET/status never executes or reconciles.
PROCESSING/UNCERTAIN blocks replacement payment; only definitive failure may be retried
with a new explicit intent. Paid receipts remain historical after a refund, with actual
current status and no bank-arrival claims. Merchant link details open authorized payments.

Additional mocked suite: http://127.0.0.1:5500/assets/js/checkout-tests.html

After separate approval only:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/activate-phase682-683-demo.sh"
```

Confirmation:`ACTIVATE_PHASE682_683_V12_V13_OTP_DISABLED`. Blank outcome-controls prompt
keeps controls disabled. Explicit private controls additionally require
`ENABLE_PRIVATE_CHECKOUT_CONTROLS` and `NO_PUBLIC_PROXY_OR_TUNNEL`.
No V11-only old deployment script should be used. Full safeguards, live checklist and
remaining production/crash-recovery limitations are in the Phase683 report.

Phase683 final automated verification: **361 isolated Java tests** (zero failures/errors/
skips), **1086 frontend checks** (1043 mocked JS +43 proxy), **119 operational mocked tests**.
Maven packaging, syntax and git diff --check passed. Native browser verification and
combined V12/V13 activation are pending separate approval; live remains operator-supplied
V11. Phase681/682 are not closed. No live DB access/mutation/restart/OTP activation performed.


## Phase 6.9.2 — Java chat API preparation

The same-origin proxy accepts only POST `/api/v1/merchant/ai/chat`,
`/api/v1/admin/ai/chat` and `/api/v1/payments/{UUID}/ai/chat` (no query, 32 KiB body,
40-second upstream timeout). Bearer authorization goes to Java; cookies and internal
chat credentials do not. No Python/LLM endpoint or frontend chat UI is exposed. Phase693
must add central API-client/UI support with session guards and explicit send/no retries.
See [Phase692 report](PHASE-6.9.2-SECURE-AI-CHAT-API-REPORT.md). Live activation pending;
previous Phase681/682/683 checks remain pending and prior evidence limitations remain.

Phase692 automated verification: **388 isolated Java tests**, **237 Python tests**,
**1,089 frontend checks** (1,043 mocked JS assertions +46 proxy tests), and
**119 operational mocked tests** passed. No native browser/live LLM verification is claimed.
Detailed execution, packaging and preservation evidence is in the Phase692 report.


## Phase 6.9.3 — Merchant AI Assistant

Merchant navigation now includes `/merchant/ai`: explicit questions, memory-only bounded
history, authorized five-record payment selection, structured evidence/money, honest fallback
labels, explicit retry and New Chat invalidation. No automatic AI request on page open.
The browser calls only POST `/api/v1/merchant/ai/chat` with existing bearer authorization,
no cookies,45-second timeout and no automatic retries. No Admin chat/detail Ask AI UI.

Mocked test page: http://127.0.0.1:5500/assets/js/merchant-ai-tests.html . All APIs on it
are synthetic; no live financial/account/chat request is sent. Native browser verification
and separately approved chat activation remain pending. Updated JS/CSS require a hard refresh;
new explicit direct route handling needs the later approved frontend handler reload. No
service restart or activation was executed. See [Phase693 report](PHASE-6.9.3-MERCHANT-AI-CHAT-REPORT.md).

Phase693 actual automated result: **1,202 frontend checks passed** (1,154 mocked JS
assertions across16 suites +48 proxy/static-security tests). Module/Python syntax and
`git diff --check` passed. Browser unavailable; no native browser/live AI verification.
Java388/Python237/operational119 are unchanged baseline evidence, not rerun in this phase.


## Phase 6.9.4 — Admin AI Assistant

`/admin/ai` adds role-isolated platform/Merchant/payment chat with explicit sends, bounded
Merchant/payment searches, UTC/currency aggregate context and safe structured evidence/money.
It calls only POST `/api/v1/admin/ai/chat` through Java, with bearer auth, no cookies,
45-second timeout and no automatic retry. No mutation tools, persistent history or payment-detail
Ask AI. Shared presentation keeps the existing Merchant AI behavior and operation/session locks.

Mocked-only test page: http://127.0.0.1:5500/assets/js/admin-ai-tests.html . No live chat or
financial/account request is sent by it. Native browser/live activation is pending. The new
explicit direct route requires a later approved frontend handler reload; static JS/CSS require
hard refresh. No service restart/activation was performed. See
[Phase694 report](PHASE-6.9.4-ADMIN-AI-CHAT-REPORT.md) for the complete checklist and results.

Phase694 actual automated verification: **1,350 frontend checks passed** (1,300 mocked JS
assertions across17 suites +50 proxy/security tests), including all108 Merchant AI and143
new Admin AI assertions. Module/Python syntax and `git diff --check` passed. Native browser
and live chat activation remain pending. Java388/Python237/operational119 are prior baselines,
not rerun in this frontend-only phase. Full evidence: Phase694 Admin AI Chat report.


## Phase 6.9.5 — Payment-specific Ask AI

Open an existing authorized Merchant/Admin payment detail, then explicitly choose Ask AI
from its header or investigation area. The inline panel fixes that UUID, never automatically
sends, and uses POST `/api/v1/payments/{id}/ai/chat` with question/history only, bearer auth,
no cookies/idempotency header and the45-second chat budget. Investigation remains distinct.
Close/New Chat invalidate private chat without clearing financial recovery intent.

Mocked-only page: http://127.0.0.1:5500/assets/js/payment-ai-tests.html . No live chat or
financial/account request is performed by it. This phase adds no server route configuration;
HTML/JS are served from disk and need a later approved asset release/hard refresh. Prior
Phase693/694 handler reload and protected chat activation requirements remain pending.
See [Phase695 report](PHASE-6.9.5-PAYMENT-ASK-AI-REPORT.md) for verification and limitations.

Phase695 actual automated verification: **1,458 frontend checks passed** (1,406 mocked JS
assertions across18 suites +52 proxy/security tests), including106 payment Ask AI,108
Merchant AI and143 Admin AI assertions. Syntax and `git diff --check` passed. Java388,
Python237 and operational119 remain prior baselines, not rerun. Native browser/live chat
activation and earlier verification gaps remain pending; see the Phase695 report.

## Phase696 saved conversations

Merchant AI, Admin AI and fixed-payment Ask AI now share an in-memory history drawer
backed by authorized Java/PostgreSQL conversation APIs. First explicit question creates
a saved conversation; opening pages/restoring history never invokes inference. Restored
answers are historical snapshots. Lists/messages are bounded and rename/delete/retry
require explicit actions; session/context changes invalidate private state.

See [Phase696 report](PHASE-6.9.6-CONVERSATION-MANAGEMENT-REPORT.md) for exact APIs,
limits, actual tests, guarded V11→V14 activation plan and native browser checklist.
The running frontend handler needs a later approved reload to recognize the new exact
proxy routes; source JS/CSS are served as files, without a bundler. No reload was performed.
No browser/chat activation is claimed. Live remains V11, V12–V14 pending, OTP disabled;
previous verification gaps remain open. Phase697 is not implemented.

Phase696 final verification: **412 isolated Java tests** (zero failures/errors/skips),
**1,558 frontend checks** (1,503 mocked JS assertions +55 proxy/security tests), Maven
packaging, relevant syntax and `git diff --check` passed. Python237 and operational119
remain prior baselines, not rerun; their source/operational scripts are unchanged.
No native browser/live verification is claimed. See the Phase696 report for limits and
the future separately approved V11→V14 migration plan.
