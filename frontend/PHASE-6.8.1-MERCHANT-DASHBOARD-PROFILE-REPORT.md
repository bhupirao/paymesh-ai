# Phase 6.8.1 — Merchant dashboard, profile and transaction monitoring

## Scope and design

Implementation reuses the V1–V11 schema, account administration advisory lock,
current JWT/session validation, exact SQL NUMERIC read models, AccountPasswords/BCrypt,
AccountAudit and V10 revocation triggers. No migration is required or created. Existing
Admin endpoints and financial mutation services are preserved; AdminQueries' existing
paginated financial query is shared with a server-scoped Merchant caller. New aggregate
queries are read-only; no payment/refund/AI mutation is performed by opening the portal.

MerchantPortal locks and rechecks the authenticated SecurityContext identity, enabled
account, exact MERCHANT-only role and ACTIVE status. It requires exactly one membership,
active membership, verified/active registry and ACTIVE V11 lifecycle. Ambiguous/missing/
inactive context fails closed. Merchant ID is always derived on the server; client
merchantId/userId/role selectors are rejected. All data queries bind the authorized
merchant_id, including refund joins through their payment. Admin role is not accepted
as Merchant authority. Existing BusinessAccess still authorizes existing payment details,
gateway/refund history and explicit AI investigation.

All new routes, including business profile and password change, require this ACTIVE
verified context. PENDING_APPROVAL/REJECTED/SUSPENDED accounts retain existing limited
onboarding access but gain no new profile/password or financial privileges. This is an
explicit conservative phase boundary; offline recovery remains a separate guarded tool.
No profile editing, self approval/ownership change, Payment Links, customer checkout or
conversational AI is implemented.

## Exact API contracts

All paths below use `/api/v1/merchant`, Bearer access JWT, no-store responses. Browser
calls go through the existing fixed Java same-origin proxy. No request identity is
trusted from a client. GET/HEAD are in the Spring catalog; proxy allows GET only.

| Method/path | Input | Response |
| --- | --- | --- |
| GET /dashboard | optional currency=INR/ USD, from/to UTC instants | totalPayments; profile; paymentCounts/refundCounts arrays {status,count}; paymentAmounts/refundAmounts arrays {currency,status,amount}; recentPayments/recentRefunds (up to5 each) |
| GET /payments | bounded filters below | {items,page,size,total}, payment projection below |
| GET /refunds | bounded filters below | {items,page,size,total}, refund projection below |
| GET /profile | no query | actual profile fields below |
| POST /profile/password | JSON {currentPassword,newPassword,confirmPassword} | 200 {message:"Password changed. Sign in again; prior sessions are revoked."}; no new token |

List filters: page0..10000 (default0), size1..100 (default25), exact search (payment UUID
or customer ID, max100), status, currency, sort=newest/oldest, optional from/to ISO8601
instants. Date bounds are inclusive; if both provided, ordered and at most366 days.
Ordering is created_at plus UUID in the same direction. All conditions are parameterized;
only allowlisted order expressions are interpolated. Duplicate/unknown query parameters
are rejected. Dashboard accepts only currency/from/to so payment/refund statuses cannot
be confused across datasets. Refund statuses currently only SUCCESS; payment statuses:
CREATED, PROCESSING, SUCCESS, FAILED, CANCELLED, REFUNDED.

Payment projection: paymentId,merchantId,amount,currency,customerId,paymentMethod,status,
createdAt. Refund projection: refundId,paymentId,merchantId,amount,currency,status,createdAt.
Amounts are exact decimal strings from PostgreSQL NUMERIC/BigDecimal.toPlainString;
counts are integers. INR/USD and distinct statuses remain separate; no combined money
sum, available balance, revenue, profit or bank settlement claim. Empty datasets use
zero totalPayments and empty aggregate/record arrays.

Profile: merchantId,merchantVerified,merchantActive,merchantCreatedAt,businessStatus,
approvedAt,membershipActive,businessName,email,firstName,lastName,mobile,businessType,
country,registeredAt,accountStatus,login,registrationAvailable. Legacy profiles lacking
registration return null business/contact/registeredAt fields and registrationAvailable=false.
No approval actor UUID, ownership reference, audit metadata, hash, token or other
Merchant's data is returned.

Password request is strict JSON (unknown/duplicate/trailing fields rejected),4096-byte
body limit, current password validated with existing BCrypt. New/confirmation must match,
minimum12 Unicode code points, maximum72 UTF8 bytes, no NUL/malformed Unicode. Under the
same account administration lock/transaction, only hash/version/timestamp update;
MERCHANT_PASSWORD_CHANGED SUCCESS audit uses actual Merchant self actor and empty
metadata. V10 trigger atomically revokes all prior sessions and consumes challenges/
grants. Audit failure rolls back user and trigger effects. No automatic sign-in/token,
refresh or mutation retry; fresh login required. Business/account/status/ownership and
financial rows are untouched. No OTP recovery is enabled.

Errors:400 invalid filters/JSON/password policy;401 absent/expired/revoked authentication;
403 wrong role, non-active/ineligible membership or current password;404 existing
payment details use existing inaccessible contract;413 body limit;415 unsupported
content type;503 unconfirmed operation/service failure. Proxy/network502/504/timeout
feedback is fixed/safe, no raw exception/body. Client timeout does not imply server rollback.

## Frontend and proxy

Single-document routes: /merchant/dashboard, /merchant/payments, /merchant/refunds,
/merchant/profile, /merchant/security. Direct navigation/refresh/Back use the existing
router and session restoration. Sidebar includes these pages and existing known-payment,
create, refund/history/AI entry points; Payment Links/chat remain honestly planned.
Opening a record performs existing authorized payment lookup only, never processing,
refund or investigation automatically. Detail eligibility/idempotency/uncertain-outcome
rules stay in the existing shared workflow. Shared financial/AI locks prevent navigation
or password changes from interfering with unresolved operations.

New model uses session version and operation sequence checks, clears on logout/expiry/
replacement, rejects malformed responses and prevents duplicate password submissions.
No secrets enter persistent browser storage; existing HttpOnly cookie/origin/CSRF,
Remember Me/Web Locks/single-flight/cross-tab behavior remain. Lists/profile are read-only.
Password UI requires native explicit confirmation, clears fields, disables duplicates,
marks uncertain outcomes without blind retry, and clears session/signs out on success.

All returned data uses createElement/textContent. Responsive scrollable tables, wrapping
UUIDs, separate currency/status amounts, accessible labels/status announcements/aria-busy,
focusable tables and navigation/focus styles reuse the existing navy/white Bootstrap
assets. Empty/loading/error/missing-profile states are explicit. Native browser/mobile/
keyboard checks remain operator work; mocked DOM execution is not browser verification.

The proxy adds only exact Merchant GET routes and one POST password path, bounded
allowlisted queries (no identity selector) and four static SPA routes. Existing Host/
Origin/CSP/no-store/request/response/timeouts/fixed upstream policies remain. Cookies
are not forwarded to Merchant business routes; existing exact auth cookie routes are
unchanged. No Python/LLM/actuator/signing/settlement path is exposed.

## Controlled activation — prepared, NOT executed

After explicit approval in a private Mac Terminal:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/deploy-phase681-demo.sh"
```

Hidden database password prompt; exact confirmation **DEPLOY_PHASE681_V11_OTP_DISABLED**.
Build reviewed sources with `cd backend; mvn package -DskipTests` first if the artifact
has changed since this report. The agent packages after isolated tests, but never starts it.

The script verifies actual listeners/cwd/bindings, private config/JWT settings, exact
paymesh_demo/paymesh_demo_user/127.0.0.1:5432 identity, PostgreSQL16 tools, V1–V11 only,
counts6/4/4/2/6/4, disabled OTP and zero eligibility. It validates the Merchant controller
and unchanged V11 artifact/source, creates a protected custom archive, verifies mode600/
list/extraction/SHA256 (not a test restore), fingerprints eight financial tables plus
ownership/registration/roles and safe account metadata, then rechecks before stopping.
Only verified Java/frontend are restarted; no new migration is expected or authorized.
Readiness/health/all Admin and new Merchant routes, counts/content fingerprints and
unchanged Python/LLM identities must pass. No login/password/financial/AI action runs.

Stop on failure. Do not repair/clean/baseline Flyway, force-kill, restore over live DB,
downgrade against incompatible data, or retry blindly. Preserve private backup/logs/
evidence and inspect safely. Any rollback or isolated restore needs separate operator
approval and compatibility review; no automatic database restoration is implemented.
Original database/application are never targeted. Historical OTP tools remain V10-only;
OTP stays disabled. Phase673/674 evidence limitations remain unchanged.

## Live browser checklist after separately approved deployment

1. Merchant A: sign in, refresh session, Dashboard actual scope/currency/status totals,
   recent rows and legacy nullable profile; desktop and375px layout/table/UUID wrapping.
2. Merchant A: Payments/Refunds lists, exact search by own payment/customer, status/
   currency/date filters, sort, paging and empty states. No automatic mutations/AI.
3. Open own payment; existing gateway/refund history, creation/processing eligibility
   and explicit investigation entry work. Use existing read-only records; no new
   financial mutation is required for this checklist.
4. Merchant B: sign in separately, verify only own lists/profile; A cannot list/search/
   open B records (empty list or existing generic inaccessible details). Do not infer
   owned Merchant from username/UUID. ADMIN cannot use Merchant APIs/portal role.
5. Pending/rejected/suspended and inactive/unverified contexts: verify limited UI and
   denied new financial/profile/password APIs with approved disposable data only.
   Do not change lifecycle merely to generate test data without separate approval.
6. On the expressly disposable ACTIVE otp-merchant-demo@example.test account only,
   check current-password/mismatch/policy validation and cancel-confirmation without
   request. If separately authorized, change password explicitly, verify fresh login,
   new credentials, old password rejection, prior JWT/session invalidation and actual
   MERCHANT_PASSWORD_CHANGED self audit/version+1. No operational password change.
7. Verify logout/expiry/replacement/cross-tab private clearing; Back/direct routes,
   focus, keyboard labels, visible focus, aria-busy and polite status messages.
8. Use mocks for errors/timeouts/duplicate/stale responses; do not stop services.
   An uncertain password mutation requires manual sign-in/review, never auto retry.
9. Admin routes/workflows and public signup/login/recovery capability remain; OTP=false.
   Counts remain6/4/4/2/6/4 and eight financial tables unchanged. A separately approved
   password test legitimately changes the disposable account version/hash/audit only.
10. Record actual browser results separately. No native browser or live deployment
    is claimed by automated mocked suites. Do not start Payment Links/checkout/chat.

## Files, tests and preservation

Final actual counts/file inventory/build/index observations follow after the complete
implementation and verification batch. Live activation/browser verification remain pending.

### Existing records for manual isolation checks

Use operator-owned credentials privately: Merchant A's existing USD payment
`842b460e-2451-4294-abc7-62c5525bc180` and fully refunded INR payment
`96829409-bb1a-4f82-b113-4bc9694bd2c0`; Merchant B's existing reconciliation payment
`c6f797c0-c810-4730-bac2-19cb8504a87d`. A's list/search for B's UUID must return no rows;
B must see its own record; existing lookup must keep the generic inaccessible response
for non-owners. These IDs are manual reference data, never hardcoded ownership rules
in application code. Do not process/refund them or automatically investigate them.

The Phase674 final verifier binds its historical authorized state; do not relax it to
accept future Phase681 password changes. A separately approved disposable Merchant
password test needs its own phase-specific evidence. Old successful rejection remains
unverified; prior Phase673 historical session/version/fingerprint limitations are not
resolved by this implementation.

### Created files

- backend/src/main/java/com/paymesh/backend/security/accounts/MerchantPortal.java
- backend/src/main/java/com/paymesh/backend/security/auth/MerchantPortalController.java
- backend/src/test/java/com/paymesh/backend/security/auth/MerchantPortalIntegrationTest.java
- backend/scripts/deploy-phase681-demo.sh
- backend/scripts/phase681_deployment.py
- backend/scripts/test_phase681_deployment.py
- frontend/merchant_proxy.py
- frontend/assets/js/merchant/routes.js
- frontend/assets/js/merchant/model.js
- frontend/assets/js/merchant/view.js
- frontend/assets/js/merchant-tests.html
- frontend/assets/js/merchant-tests.js
- frontend/tests/test_merchant_proxy.py
- frontend/PHASE-6.8.1-MERCHANT-DASHBOARD-PROFILE-REPORT.md

### Modified files

- backend/src/main/java/com/paymesh/backend/security/accounts/AdminQueries.java —
  shared scoped financial read primitive and Merchant aggregates; public Admin checks retained.
- backend/src/main/java/com/paymesh/backend/security/auth/BusinessEndpointCatalog.java —
  exact new Merchant routes.
- backend/src/main/java/com/paymesh/backend/security/auth/JwtSecurityConfiguration.java —
  MERCHANT role gate for that catalog; existing Admin/payment rules preserved.
- backend/src/main/java/com/paymesh/backend/security/BoundedRequestBodyFilter.java —
 4096-byte Merchant password body and no-store.
- frontend/dev_server.py — exact Merchant proxy/SPA routes and query/body limits.
- frontend/assets/js/api/config.js and api/client.js — route validation and role presentation gate.
- frontend/assets/js/portals/router.js and portals/view.js — dedicated navigation/shared workflows.
- frontend/index.html and assets/css/app.css — Merchant root/responsive cards/tables.
- frontend/assets/js/portal-tests.js and tests/test_portal_routes.py —20 explicit SPA routes.
- README.md, PROGRESS.md and frontend/README.md — implementation/activation handoff.

### Known limitations and preservation

Only single-role ACTIVE Merchant accounts with one active verified membership can use
new APIs. Complex ownership and limited-account self-service security need separate
review. Business profile editing is not offered. Read models use bounded offset paging,
not an unbounded export or accounting/settlement ledger. Snapshots need explicit refresh;
financial activity occurring concurrently with several read queries can advance between
queries. No per-endpoint production rate limiting or public recovery feature is added.

No migration, dependency, backend financial mutation or Python AI implementation changed.
All historical migrations and protected evidence/configuration remain untouched. No live
database access, password/account/financial operation, OTP activation, service restart or
deployment was performed by the implementation agent. Current live counts are the supplied
Phase674 baseline, not newly measured by this batch. No original database/port8080 access
occurred. No Git add/commit/push/reset/clean/restore was issued. Concurrent external staging
is inspected and left untouched; final observations are recorded below. Phase6.8.2/6.8.3/
6.9 are not implemented.

## Final executed verification

| Suite/check | Actual final result |
| --- | --- |
| `cd backend; bash scripts/test-isolated.sh` |315 tests passed, zero failures/errors/skips (300 existing +15 new);6m28s |
| All11 JavaScript mocked suites |813 assertions passed (722 existing +91 Merchant) |
| `python3 -m unittest discover -s frontend/tests -v` |34 tests passed (30 existing +4 Merchant proxy) |
| Frontend total |847 checks =813 JS +34 proxy |
| `python3 -m unittest discover -s backend/scripts -p 'test_phase*.py' -v` |109 mocked operational tests passed (105 existing +4 deployment) |
| `mvn package -DskipTests` |BUILD SUCCESS after isolated tests; packaging does not rerun tests |
| Bash syntax/Python compilation |Deployment shell/helper/tests and modified proxy/test modules passed |
| JavaScript syntax |43 ES modules passed `node --input-type=module --check` via stdin |

The first Java attempt stopped during test compilation because the existing protected
Identity constructor cannot be used from this subclass package. Tests now use real
Bearer headers without changing that shared test infrastructure. A second complete run
found one invalid fixture that tried active/unverified registry data, correctly rejected
by existing DB constraints. The fixture was corrected to a valid unverified state; no
constraint or security rule was weakened. The complete final run then passed315/315.
The isolated cluster was verified on its non-live port/data directory and stopped by
the documented runner. Its selected installed PostgreSQL version was14.20; this is not
an independently run live PostgreSQL16 test. Deployment targets PostgreSQL16 tools;
live target verification remains operator work. No bare Maven test was run.

All new and existing JS suites ran in the existing Node-backed DOM-double runtime,
sequential module imports, mocked fetch only. This is not native browser automation.
Suite counts: API10, authentication34, payment94, refund125, investigation149, QA18,
portal73, registration39, session/recovery67, Admin113, Merchant91. Merchant tests include
rendered currency/amount cards, missing profile, form labels/private clearing and no
view-triggered mutation/AI request, as well as state/route/password/uncertainty checks.
No new Node package, build system or paid dependency was installed. Native browser,
375px visual/keyboard/screen-reader and live API verification remain pending.

No Python AI implementation changed; its independent full suite was not rerun. Existing
Java AI/integration and frontend investigation regressions passed in the full runs.
No live AI investigation was requested.

Browser-compatible mocked test pages (safe financial mocks, no live passwords):

- http://127.0.0.1:5500/assets/js/tests.html
- http://127.0.0.1:5500/assets/js/auth-tests.html
- http://127.0.0.1:5500/assets/js/payment-tests.html
- http://127.0.0.1:5500/assets/js/refund-tests.html
- http://127.0.0.1:5500/assets/js/investigation-tests.html
- http://127.0.0.1:5500/assets/js/qa-tests.html
- http://127.0.0.1:5500/assets/js/portal-tests.html
- http://127.0.0.1:5500/assets/js/registration-tests.html
- http://127.0.0.1:5500/assets/js/session-recovery-tests.html
- http://127.0.0.1:5500/assets/js/admin-tests.html
- http://127.0.0.1:5500/assets/js/merchant-tests.html

Runnable JAR verified to contain both Merchant classes and exactly V1–V11 migrations;
no V12/new migration exists. SHA256: `e2674a2163f44110843d26ec6e63b78b9ac56cac8f31d70317f093f3ed875031`.
No JAR was started by the implementation agent.

**IMPLEMENTATION AND AUTOMATED VERIFICATION COMPLETE. LIVE ACTIVATION AND ACTUAL
BROWSER VERIFICATION PENDING OPERATOR APPROVAL.** Phase6.8.2/6.8.3/6.9 remain outside
scope. This is not production security certification. Final diff/index observations
are recorded below.

Final Git preservation: initial/final cached binary patch is identical. No concurrent staging change was detected. Git status has388 entries (optional index refresh disabled), categories {'AM': 177, 'A ': 195, '??': 16}.

`git diff --check` passed. No stage/commit/push/reset/clean/restore was issued.

## Operator Step17 activate-phase681 evidence

Outcome: verified. Stage: frontend-restart. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-activate-phase681-20261115T070224Z-62yoz_bv/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Analytics and account-switching enhancement — implementation preparation

The operator reports original Phase681 deployed and browser verification in progress.
Original successful deployment evidence/backups are not modified. This enhancement is
prepared only; no live DB access, deployment, logout, password or financial action is
performed by the agent. No migration: V1–V11 remain unchanged.

New GET `/api/v1/merchant/analytics` and ADMIN-only GET `/api/v1/admin/analytics` use
existing JWT/session/account authorization. Merchant scope comes only from the verified
ACTIVE single membership. Admin accepts optional exact merchantId; Merchant cannot
select identity. Parameters:currency=INR|USD optional; from/to must both be supplied or
both omitted, UTC midnight ISO instants, start inclusive/end exclusive,1–93 days,
no end beyond tomorrow UTC. Default:last30 UTC calendar days including today. Date
bucketing is explicitly UTC independent of database session timezone; days with no
records are bounded server-generated zero buckets, not invented activity.

Response:range{from,to,timezone:"UTC",endExclusive:true}; paymentCounts[{currency,status,
count}],refundCounts[{currency,status,count}],paymentMethods[{currency,paymentMethod,count}],
amountComparison[{currency,paymentAmount,refundAmount}],dailyPayments[{date,currency,count,
amount}]; Admin additionally merchantCounts[{status,count}] for all registry records.
Amount fields are exact NUMERIC/BigDecimal decimal strings. Counts/method/status groups
scan the complete authorized bounded dataset, not pages/recent5 records. Refunds use
refund.created_at and their own SUCCESS status, payments use payment.created_at and
all actual payment states. Lifecycle distribution is current global state, not a
historical lifecycle timeline. No currency sums are combined. Daily "volume" means
payment counts, not settlement/revenue/profit/available funds.

Existing dashboard record filters/KPIs/recent lists remain intact. New chart filters
are an explicitly labeled independent UTC analytics scope, with Today/Last7/Last30/
custom inclusive start/end day controls and one chart currency at a time. Exact
fallback tables remain visible alongside approximate Number-only plot projections;
no Number conversion performs authoritative financial arithmetic. Four Merchant
charts:status/method donuts, daily count line, recorded payment/refund bar. Admin:
global lifecycle donut,status donut,count trend and payment/refund bar. Responsive
cards, static Canvas descriptions, table equivalents, keyboard forms, loading/empty/
errors and stale/session guards are included. Chart instances are destroyed on
filter/route/session change. No model options or HTML are accepted from API values.

Chart.js4.4.8 UMD is vendored unchanged under assets/vendor/chartjs, MIT LICENSE.md,
official npm/source URLs and SHA256 in README.md; bundled @kurkle/color0.3.2 MIT
license is also retained. No CDN/fonts/dependency/build service is used at runtime.
CSP stays unchanged (self scripts/styles/connect; no unsafe-inline/eval expansion).
The official integration reference supports local script-tag UMD use:
https://www.chartjs.org/docs/latest/getting-started/integration.html.

Account menu displays the current login/role with own profile/security, Switch Account
and Sign Out. Login/refresh token responses add backward-compatible own `login` metadata
from the current database snapshot; JWT claims/lifetime/refresh-cookie design are
unchanged. Optional metadata is validated and kept in memory so restored limited
accounts can identify themselves without granting profile/financial permissions.
Older responses remain supported; an active restored account may load its permitted
own profile as fallback. No username is inferred from UUID or persisted in browser
storage. Shared cookie restoration across normal tabs remains intentional. Separate
Chrome profiles, an Incognito session or another browser provide independent accounts.

Switch Account requires explicit confirmation of browser-profile-wide logout and
respects unresolved payment/refund/AI and administrative operation guards. It calls
existing signOut:stop refresh/epoch advancement, local private clear, BroadcastChannel
logout and Web-Locked secure server logout/cookie removal. Only confirmed logout leads
to the chosen public login route. On failure, local data is cleared but server/cookie
revocation is unconfirmed; login submission is blocked until explicit Finish Sign Out
succeeds. Do not refresh/share the browser while logout is uncertain: a surviving
HttpOnly cookie may still restore an account after a full page reload. New sessions
invalidate stale switch/refresh completions. Merely opening a login tab never logs out.
No multiple-cookie or per-tab token/storage feature is introduced.

Guarded enhancement redeployment (operator approval required; NOT executed):

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/redeploy-phase681-analytics.sh"
```

Confirmation:`REDEPLOY_PHASE681_ANALYTICS_OTP_DISABLED`. PostgreSQL16 identity/tools,
expected6/4/4/2/6/4,V11-only artifact/history, protected backup/readability/extraction/
checksum, pre/post eight-financial/ownership/account fingerprints, exact process
identity and loopback/configuration/health checks follow the reviewed deployment
conventions. A fresh `redeploy-phase681-analytics` evidence directory is used; original
Phase681 evidence/backups are not overwritten. Only approved Java/frontend restarts;
Python/LLM preserved. No schema change, automatic auth/financial/AI request or password
change. Stop on failure; no automatic restore/repair/downgrade/retry. Existing Phase681
report limitations and Phase673/674 historical limitations remain.

Manual browser enhancement checklist after approved redeployment:

1. Merchant A/B:charts reflect only owned complete data. Today/7/30/custom UTC boundaries,
   INR/USD separation, status/method groups, zero ranges and exact fallback amounts.
2. Admin:global lifecycle and authorized filtered financial graphs; preserve original
   record tables/filters; understand the independent chart scope. No automatic mutation.
3. Desktop/375px:Canvas sizing, no overflow, focus/labels, descriptions and accessible
   data tables, loading/errors, filter refresh and route changes without stale charts.
4. Normal second tab restores the same cookie session without logout. Menu shows actual
   login/role. Explain profiles/Incognito for independent accounts.
5. Switch cancellation makes no logout request; pending/unresolved financial/AI actions
   block switching. Explicit confirmed switch clears old private data across tabs and
   allows fresh Merchant/Admin login with existing role gates.
6. Simulate logout failure using mocks/browser interception only (never stop services).
   No success claim/old-state restoration; Finish Sign Out is explicit; login blocked
   while uncertain. Verify stale refresh/account replacement does not restore old data.
7. OTP stays disabled; counts and financial contents unchanged. No real password,
   payment/refund/AI mutation is required. Native browser results are pending, not
   inferred from mocked tests. Phase681 is not closed; no Phase682 work begins.

Actual final automated results, inventory and preservation checks follow below.

The Admin lifecycle chart reuses the already-authorized dashboard merchantCounts when
available. Financial chart cohorts require new complete bounded aggregates: existing
record APIs use independently filtered inclusive instants, while analytics use exact
exclusive UTC-day ends. Reusing their recent5 rows or silently equating the different
ranges would be incorrect. Existing record KPIs/tables remain intact and explicitly
labeled with independent filters. Payment status is the current stored status for
payments created in-range, not reconstructed historical status or settlement history.

### Final enhancement verification and file inventory

Actual completed results:

| Check | Result |
| --- | --- |
| `cd backend; bash scripts/test-isolated.sh` |322 tests, zero failures/errors/skips;315 existing +7 analytics/identity tests;4m37s |
| All12 frontend JS suites in existing Node DOM-double runtime |859 assertions;813 existing +46 enhancement |
| `python3 -m unittest discover -s frontend/tests -v` |36 tests;34 existing +2 analytics proxy |
| Frontend total |895 checks (859 JS +36 proxy), all mocked runtime/proxy tests |
| `python3 -m unittest discover -s backend/scripts -p 'test_phase*.py' -v` |111 tests;109 existing +2 redeployment |
| `mvn package -DskipTests` |BUILD SUCCESS after isolated verification; no test rerun during packaging |
| Bash syntax/Python compilation |New redeploy wrapper/helper/tests and changed proxy/test modules passed |
| Node syntax checks |47 JavaScript files, including vendored UMD, passed |
| Vendored UMD runtime metadata |require(...).version confirmed4.4.8; no native Canvas render claimed |

The final Java run used the existing isolated harness, fresh non-live cluster/data
directory and paymesh_test identity, then stopped that cluster. Its selected installed
server was PostgreSQL14.20; live demo/PostgreSQL16 verification was not executed.
No bare Maven tests against demo/original DB were run. Python AI implementation is
unchanged; its separate suite was not rerun. Java AI/integration and existing149
frontend investigation assertions passed. No live investigations were issued.

New mocked page:http://127.0.0.1:5500/assets/js/analytics-switch-tests.html —46 assertions.
All prior test pages remain. Test fetch and BroadcastChannel are mocked so the page
does not mutate live auth/financial records or sign out actual browser tabs. New cases
cover server-provided identity, preset/custom UTC dates, exact fallback values, status/
method grouping, Canvas descriptions, safe labels, plot-only Number conversion, chart
destruction, zero/error states, duplicate/stale/filter/session guards, cancelled/blocked/
confirmed/failed/retried switching, replacement while pending, shared-cookie restoration,
broadcast clearing and late refresh. These are not actual browser observations.

Runnable JAR contains DashboardAnalytics and only V1–V11. Artifact SHA256:
`4c08d6326d01ffb1ac12dbb1784aed65c7e0dd05353e51e88bf44e2505ca5acc`.
No JAR/deployment helper was started by the agent.

Created:

- backend/src/main/java/com/paymesh/backend/security/accounts/DashboardAnalytics.java
- backend/src/test/java/com/paymesh/backend/security/auth/DashboardAnalyticsIntegrationTest.java
- backend/scripts/redeploy-phase681-analytics.sh
- backend/scripts/phase681_analytics_deployment.py
- backend/scripts/test_phase681_analytics_deployment.py
- frontend/assets/js/analytics/charts.js
- frontend/assets/js/auth/account-switch.js
- frontend/assets/js/analytics-switch-tests.html
- frontend/assets/js/analytics-switch-tests.js
- frontend/tests/test_analytics_proxy.py
- frontend/assets/vendor/chartjs/chart.umd.js
- frontend/assets/vendor/chartjs/LICENSE.md
- frontend/assets/vendor/chartjs/LICENSE-kurkle-color.md
- frontend/assets/vendor/chartjs/README.md

Modified:

- backend/src/main/java/com/paymesh/backend/security/accounts/AdminQueries.java
- backend/src/main/java/com/paymesh/backend/security/accounts/MerchantPortal.java
- backend/src/main/java/com/paymesh/backend/security/accounts/AccountTokenStateService.java
- backend/src/main/java/com/paymesh/backend/security/auth/JwtTokenService.java
- backend/src/main/java/com/paymesh/backend/security/auth/AdminManagementController.java
- backend/src/main/java/com/paymesh/backend/security/auth/MerchantPortalController.java
- backend/src/main/java/com/paymesh/backend/security/auth/BusinessEndpointCatalog.java
- frontend/admin_proxy.py and merchant_proxy.py
- frontend/assets/js/admin/routes.js and admin/view.js
- frontend/assets/js/merchant/routes.js and merchant/view.js
- frontend/assets/js/auth/session.js
- frontend/assets/js/portals/view.js
- frontend/assets/js/app.js
- frontend/index.html and assets/css/app.css
- backend/API-REFERENCE.md, README.md,PROGRESS.md,frontend/README.md and this report

No persistence.js, security cookie/Origin/CSRF configuration, historical migration,
financial mutation service, original deploy helper, protected evidence or backup was
modified. No live DB access/write, password/account change, service restart, OTP
activation or deployment occurred during preparation. All current live counts remain
the supplied expected baseline, not a newly measured agent observation. No original
application/database access. No Git staging/commit/reset/clean/restore was issued.

**Enhancement implemented and automated-tested; controlled redeployment/native browser
verification pending operator approval. Phase681 remains OPEN; Phase682 not started.**
Exact redeployment command and confirmation are recorded above. No production security
certification, live JWT replay test or backup test restore is claimed. Prior Phase673/
674 historical evidence limitations remain; original successful Phase681 deployment
records/backups are preserved. Final whitespace/index observations follow.

Final enhancement preservation: 20 concurrently changed staged patch blocks observed and left untouched. No index/staging modification was performed by the agent. Read-only Git status (optional refresh disabled) has404 entries, categories {'AM': 186, 'A ': 206, '??': 12}. `git diff --check` passed; final syntax results passed. No live action was performed.

Final handoff:322 isolated Java,895 frontend (859 mocked JS+36 proxy),111 operational tests passed; packaging/syntax/diff checks passed. Final index observation:20 externally changed cached patch blocks versus initial snapshot, left untouched. No live operation or deployment executed. Phase681 remains open.

## Operator Step17 redeploy-phase681-analytics evidence

Outcome: verified. Stage: frontend-restart. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-redeploy-phase681-analytics-20261115T103656Z-kuu2z8f7/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Five-row dashboard exact-value table follow-up

Reusable `components/paginated-table.js` now bounds visible rows to5 per independent
table, Previous/Next arrows, disabled edges, page/range live announcements, hidden
controls for<=5 and existing empty states. Analytics date/currency scope changes
reset pages; same-scope refresh clamps; session reset disposes rows/pages. Merchant/
Admin chart fallback tables and complete dashboard aggregates use it. Charts keep
all authorized rows/zero UTC days/exact totals. Recent previews and full list server
pagination are unchanged. No UI dependency or server change was added for pagination.
New pagination suite:51 mocked assertions, also run with the Phase682 full regressions.
Files: components/paginated-table.js, analytics/charts.js, merchant/view.js, admin/view.js,
app.css, pagination-tests.html/js (plus this report). Static JS/CSS is read from disk
on every request with no-store: pagination alone requires Cmd+Shift+R, no restart.
The later Phase682 proxy route additions separately require approved proxy activation.
Manual: Last30 daily table1/6, navigate all30 rows, independent tables, edge focus/disabled
controls, Last7/USD resets, refresh clamps, logout clears,375px overflow/keyboard and
full unchanged charts. No native browser verification of this follow-up is claimed.
Phase681 remains OPEN; prior evidence/backups/limitations preserved.
