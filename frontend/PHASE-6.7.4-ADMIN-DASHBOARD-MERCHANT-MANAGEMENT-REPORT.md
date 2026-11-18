# Phase 6.7.4 — Admin dashboard and Merchant management

**OFFICIAL FINAL STATUS: PHASE 6.7.4 — COMPLETE WITH DOCUMENTED EVIDENCE LIMITATIONS.**
GO for continued private local portfolio development; NOT production security certification.
The definitive closeout is at the end of this report. Earlier pending/failure/preparation
sections are chronological evidence, superseded by that final status where stated.
Next:Phase6.8.1 — Merchant Dashboard, Profile and Transaction Monitoring (not started).

## Scope and implementation design

Implementation targets the existing Java21/Spring/PostgreSQL16 and static ES-module/Bootstrap platform. Source inspection covered existing account credentials/authorization/administration lock/audit/password/registration, V1–V10, JWT/session validation and financial BusinessAccess, existing payment/refund/detail/AI interfaces, frontend router/session/client/views/proxy, the Phase6.7.3 limited closeout and prior tests. No live DB connection or application/financial request is used for implementation. OTP stays disabled; Phase6.7.3 historical evidence limitations are not changed.

The existing AccountAdministration/AccountAuthorization and advisory-lock namespace are reused. New MerchantAdministration coordinates only administrative account/registry/membership changes and atomic audit. AdminQueries is an explicit parameterized read model, using AuthStore's server-validated schema prefix, named response projections, PostgreSQL NUMERIC and Java BigDecimal→decimal text. Existing payment/refund/processing/webhook/reconciliation/AI business services are unchanged. There is no new financial mutation logic.

V11 expands the existing account_status check to PENDING_APPROVAL/ACTIVE/REJECTED/SUSPENDED and adds merchant_administration with lifecycle, original approval actor/time, last actor/time, reason and review reference. Existing verified active merchants backfill ACTIVE using existing attestation; verified inactive merchants backfill SUSPENDED; unverified records stay PENDING_APPROVAL. No existing pending registration is approved, no financial row is changed, no historical migration edited. Insert/verification triggers keep supported existing registration/offline provisioning compatible. Active legacy verified merchants remain supported without requiring invented registration profiles.

### Transition matrix

| Action | Required state | Result | Required input/evidence |
| --- | --- | --- | --- |
| approve | PENDING_APPROVAL account and registry, unverified/inactive, existing registration and inactive membership | ACTIVE account/registry/membership, verified actor/time | ownershipAttested=true; reviewReference3–100 supported ASCII characters, explicit external ownership review |
| reject | PENDING_APPROVAL, unverified/inactive | REJECTED account/lifecycle; registry/membership inactive | reason1–500 non-control characters |
| suspend | ACTIVE account, verified/active registry, active membership | SUSPENDED account/lifecycle; registry/membership inactive | required bounded reason |
| reactivate | SUSPENDED account/lifecycle, previously approved/verified with original approval evidence, inactive membership | ACTIVE account/registry/membership | required bounded reason |

REJECTED is terminal in this phase. Repeated/invalid actions return409; they do not add duplicate memberships or success audits. A disabled account, mixed-role identity, shared registry ownership or multi-merchant identity fails closed with409 rather than guessing which other privileges should change. This is an intentional current single-owner administrative scope; original financial ownership records are not reinterpreted. Unclaimed historical registry rows without the required account/membership/registration evidence cannot be approved through this flow.

Every transition runs under AccountAdministrationLock and checks the actual SecurityContext-derived authenticated Admin against current enabled/ACTIVE/version/role state. Target account status/version, registry, membership, lifecycle and MERCHANT_APPROVE/REJECT/SUSPEND/REACTIVATE success audit share one transaction. Failure rolls back all writes, including V10 session/challenge/grant revocation. Status changes increment authorization_version and existing V10 triggers invalidate previous sessions; JWT validation checks live version/status/roles/sid. A new sign-in for any non-ACTIVE Merchant can reach only limited account UI, never financial/Admin APIs. Reactivation does not revive old tokens or re-enable a separately disabled account.

## Exact API contracts

All new endpoints are under `/api/v1/admin`, require an enabled ACTIVE ADMIN's valid Bearer JWT and return no-store JSON. Cookies alone grant no Admin authority. Actor identity/role/status cannot be submitted as data. Existing `POST /api/v1/admin/accounts` is reused unchanged for additional ACTIVE ADMIN-only creation; new GET on that path is the requested list capability. No public Admin signup, Admin status-change endpoint or bootstrap bypass is introduced; last-active-Admin status management is not added.

| Method/path | Request | Response |
| --- | --- | --- |
| GET /dashboard | optional financial filters below | totalMerchants, pendingRegistrations; merchantCounts; paymentCounts/refundCounts; paymentAmounts/refundAmounts by currency AND status; recentRegistrations/recentPayments (max5) |
| GET /merchants | paginated search/status/merchant/date filters | `{items,page,size,total}` with registry/lifecycle and nullable registration/business projection |
| GET /merchant | exact `merchantId` query | merchantId,status,verified,active,approvedAt/By,lastActionAt,reason,reviewReference,createdAt,registrationUserId,businessName,email,firstName,lastName,mobile,businessType,country |
| POST /merchant/approve | `{merchantId,reviewReference,ownershipAttested:true}` | `{merchantId,status,message}` |
| POST /merchant/reject | `{merchantId,reason}` | same committed-state envelope |
| POST /merchant/suspend | `{merchantId,reason}` | same |
| POST /merchant/reactivate | `{merchantId,reason}` | same |
| GET /payments | bounded pagination, search, merchant/status/currency/date filters | page; paymentId,merchantId,amount,currency,customerId,paymentMethod,status,createdAt |
| GET /payments/{canonical UUID} | none | exact payment read projection |
| GET /refunds | pagination, search, merchant/status/currency/date filters | page; refundId,paymentId,merchantId,amount,currency,status,createdAt |
| GET /refunds/{canonical UUID} | none | exact refund read projection |
| GET /audit | pagination; exact event-type search; merchant/date filters | page; eventId,actorUserId,eventType,merchantId,resourceType,resourceId,outcome,occurredAt; no raw metadata |
| GET /accounts | pagination; exact normalized login search | page of Admin userId,login,enabled,accountStatus,createdAt |
| GET /profile | none | actual Admin userId,login,enabled,accountStatus,roles |
| POST /profile/password | `{currentPassword,newPassword,confirmPassword}` | safe confirmation; current/all sessions revoked; sign-in required |

Pagination: page0–10000, size1–100/default25. Sort only newest/oldest with created/time + unique-ID tie-breakers. Search/merchantId max100, query max2048 bytes at proxy; duplicate keys rejected. From/to are ISO-8601 instants, inclusive; if both specified, ordered and max366day range. Merchant search is literal escaped ILIKE on ID/business/email; payment/refund search is exact payment UUID/customer ID; audit event search and Admin login search are exact. All values are bound SQL parameters; sorting/table/column SQL comes from fixed server code. Dashboard applies financial merchant/currency/status/date/search filters to financial aggregates/recent payments, while registry totals and recent registrations explicitly cover all merchants/registrations. It does not fabricate zeros, balance/revenue/settlement claims or cross-currency sums. Empty groups are empty arrays. Supported refund status is SUCCESS per actual existing schema; unsupported refund statuses are not invented.

Request bodies are max4096 bytes, strict unknown-field/duplicate-key/trailing-JSON rejection. Merchant IDs are explicit body/query values, never inferred from login/user UUID. Reasons are bounded/no control characters; attestation is mandatory for approval. Password change reuses AccountPasswords/BCrypt (12 Unicode code points minimum,72 UTF-8 bytes maximum, no NUL/malformed Unicode), matching confirmation and current-password verification under the same transaction/lock. ADMIN_PASSWORD_CHANGED records the real Admin actor atomically, increments version and revokes prior credentials through V10; no replacement JWT/automatic reauthentication. Accessible password buffers are cleared; JVM/HTTP transient copies cannot be perfectly erased.

Errors:400 invalid fields/query/confirmation;401 missing/expired/revoked JWT;403 wrong role/current authorization/current password;404 unavailable record;409 ineligible/ambiguous/repeated lifecycle transition;413 body too large;415 non-JSON mutation;429 existing login limiter where applicable;503 safe unconfirmed internal/update/audit failure. No raw exception, password/hash, refresh/OTP/reset digest, key or arbitrary audit metadata is returned. No automatic mutation retry. After uncertain action, explicitly refresh authoritative Merchant detail before another action.

## Frontend integration

One HTML entry and memory-only access tokens remain. Explicit private routes:
`/admin/dashboard`, `/admin/merchants`, `/admin/merchant`, `/admin/pending`, `/admin/payments`, `/admin/refunds`, `/admin/audit`, `/admin/accounts`, `/admin/profile`.
Existing Merchant/login/signup/forgot routes remain; SUSPENDED and REJECTED Merchants see limited status UI. Forgot Password remains unavailable with the live disabled capability; no OTP setting is changed.

Admin ES modules provide state sequencing/session-version checks, bounded encoded query construction, current-role presentation guards and safe DOM rendering via createElement/textContent. Lists have search/status/currency/date/order filters as relevant, pagination, refresh, empty/loading/error feedback and keyboard-scrollable responsive tables. Merchant detail includes registration/attestation/last-action fields, reason input and explicit review/confirmation dialogs. Duplicate pending actions and concurrent route changes are blocked. Shared unresolved payment/refund/investigation locks block administrative mutations. Financial detail/AI navigation reuses the existing authorized known-payment/refund-history/investigation workspace; it does not automatically process/refund/investigate.

Admin Accounts lists actual records and reuses existing creation API with explicit privilege confirmation. Admin Profile shows actual metadata and current/new/confirm password controls, show/hide and required reauthentication. No browser credential persistence is added. Token renewal preserves existing same-session state; logout/expiry/replacement clears private Admin state and invalidates old responses. 401 clearing/403 retention behavior and existing cross-tab/persistent-session mechanisms remain.

The proxy adds only exact Admin GET/POST paths, eight additional static SPA paths and bounded allowlisted Admin query strings. Legacy routes retain their original path restrictions. Host/Origin/CSP/no-store/framing/body/response limits, fixed Java18080 target, redirects denied and cookie forwarding limited to existing authentication routes remain unchanged. No Python/LLM/settlement/webhook-signing/actuator route is exposed.

## Controlled activation — preparation only

After separately reviewing/approving V11 and backup/deployment, in a private Mac Terminal:

```bash
cd "$HOME/Developer/paymesh-ai/backend"
mvn package -DskipTests
cd ..
/bin/bash backend/scripts/activate-phase674-demo.sh
```

The activation wrapper reads the DB password silently through /dev/tty and requires the exact non-secret confirmation `ACTIVATE_PHASE674_V11_OTP_DISABLED`. Never put credentials in arguments/chat/history. The implementation agent does not execute this script. It discovers current process identities, cwd/start/bindings; validates private config, literal demo JDBC/user, actual PostgreSQL identity, PostgreSQL16 tools, successful V1–V10/no V11, counts6/4/4/2/6/4, disabled recovery and zero eligibility. Packaged V1–V11/Admin controller and source V11 identity are checked before any stop.

It fingerprints all eight financial tables, registry/membership/registration/role rows and safe account metadata, verifies disk reserve and a new protected custom-format backup (mode600/nonempty/list/extraction/SHA256, no test restore), then rechecks state. Only the verified demo Java is restarted with all established config/session/JWT/gateway/AI/scheduling settings and OTP=false; normal Flyway startup applies V11. Readiness, V11 success and unchanged counts/financial/account fingerprints must pass. Only then is the verified frontend restarted to load the exact new proxy routes. All Admin/old public routes, proxy health, disabled recovery and preserved Python/LLM identities are checked. No login, approval/rejection/suspension/reactivation, account creation, password change, payment/refund mutation or AI investigation is run automatically. New merchant_administration rows are expected (4); existing counts remain6/4/4/2/6/4. No pending account is auto-approved.

Failure handling/rollback: stop on any unexpected target/process/history/schema/startup/count/content condition. Logs/evidence remain private. Do not Flyway clean/repair/baseline, force-kill, restore over the live DB, downgrade against V11/new statuses or repeatedly restart blindly. A failed startup may leave V11 applied. Preserve the backup and evidence; inspect the exact failure privately. Any application rollback requires explicit V11 compatibility/status/security review. Any DB recovery requires separate operator approval, an isolated restore/test and a controlled switch plan, not automatic destructive rollback. The V10-only OTP operational scripts deliberately reject V11 artifacts/history; they are historical tools, not permission to relax OTP gates. OTP must remain disabled.

## Manual browser checklist after approved activation

No live verification is claimed before operator execution. Use private credentials in the actual browser; avoid screenshots containing passwords/tokens/business PII. Use disposable accounts for lifecycle/password actions; do not mutate existing payments/refunds.

1. Confirm landing, Merchant/Admin login, Remember Me, refresh restoration, cross-tab logout and disabled Forgot Password still work. At375px and desktop check labels/focus/navigation/table scrolling/UUID wrapping.
2. Sign in as actual ADMIN, visit every new Admin route directly, refresh and use Back. Confirm real dashboard counts/currency-separated status amounts/recent records; no balance/settlement claims.
3. Check pending/active/rejected/suspended filters, literal search, paging, dates and ordering; empty/invalid/inaccessible behavior. Merchant detail must show actual explicit Merchant ID and optional legacy profile absence honestly.
4. On an explicitly approved disposable pending registration, review external ownership, enter reference and check attestation; review must not submit. Explicitly confirm approval, then refresh. Verify ACTIVE registry/account/membership and real actor audit. Old pending session must be rejected; new sign-in gains only owned Merchant access.
5. On separately disposable data, confirm rejection requires a reason and is terminal; repeated/invalid actions fail without duplicate memberships/audits. Do not reject operational accounts merely for testing.
6. Suspend an approved disposable Merchant with reason; refresh; old session/token rejected, new limited sign-in cannot use financial/Admin APIs. Reactivate only previously approved state; verify no approval bypass and no revival of old tokens.
7. Payment/refund monitoring: filters, exact amounts/INR–USD separation, read-only cross-merchant details, gateway/refund history and explicit AI entry. Do not create/process/refund/investigate to test navigation. Merchant cannot enter Admin or read another Merchant's existing record.
8. Audit History/Admin Accounts/Profile: safe real metadata only, no secrets/raw internal metadata. Additional Admin creation only if separately authorized; do not create records just to test a page.
9. On an expressly disposable Admin, verify current-password/mismatch validation and successful password change, prior sessions rejected and fresh sign-in required; no password recovery action. Do not change operational demo-admin password for this checklist.
10. Use mocked tests for503/timeouts/network/duplicate-pending/late responses; do not stop services to induce failures. Confirm uncertain mutations are not automatically retried and require authoritative refresh.
11. Verify original six payment/four refund records and all eight financial contents remain unchanged, OTP remains false, and AI/LLM services unchanged. Keep actual manual evidence separate from automated mocks.

## Known boundaries and roadmap

Current administrative transitions deliberately require a single-role single-owner/single-membership account context; complex shared ownership needs a separately reviewed model, not guessed broad changes. Rejection reversal and Admin disable/status management are not exposed. Dashboard read models are operational monitoring, not bank settlement/revenue/accounting statements. Search/paging is bounded offset paging for the local portfolio; distributed scale/production identity recovery/ingress/secrets remain separate work. Existing Phase6.7.3 historical session/fingerprint/version limitations remain documented. Public on-screen OTP must never be enabled. No Phase6.8/Docker implementation begins here.

## Executed tests, files and preservation

Final actual results and exact changed-file inventory are appended after the complete implementation/test batch. Compilation or source review is not counted as a test; no live activation or browser verification is claimed.

### Final executed results — November 15, 2026

| Verification | Actual result |
| --- | --- |
| `cd backend; bash scripts/test-isolated.sh` | 299 tests, zero failures/errors/skips (283 existing +16 new); isolated PostgreSQL only |
| Browser-compatible JavaScript modules, existing Node DOM doubles | 722 assertions: API10, authentication34, payment94, refund125, investigation149, QA18, portal73, registration39, session/recovery67, new Admin113 |
| Frontend Python proxy discovery | 30 tests passed (25 existing +5 new) |
| `python3 -m unittest discover -s backend/scripts -p 'test_phase67*.py' -v` | 53 mocked tests passed (50 existing +3 activation) |
| `mvn package -DskipTests` | BUILD SUCCESS; tests already separately verified |
| Bash syntax and Python compilation | New activation shell/helper/tests and modified proxy files passed |

Frontend total is **752** (722 mocked JS +30 proxy), not an actual-browser claim.
Actual browser/mobile/screen-reader checks are pending. No separate Python AI test
rerun was necessary: no AI implementation changed, and Java integration regressions
remain in the complete isolated suite. Initial Java approval tests exposed a JDBC
Instant binding defect; converting the nullable approval time to SQL Timestamp fixed
it and the complete suite then passed. Proxy test transport mocking and expected
explicit-route count were corrected, followed by a complete passing proxy run.
No failing result is represented as a pass without a rerun.

Packaged JAR contains V1–V11 migrations and AdminManagementController; SHA-256:
`3eef241fb5cac30a689c9018a25fd47e52da7aba807542a19a354b30a2e0b3e4`.
No JAR was started by the implementation agent.

### Exact file inventory

Created:

- backend/src/main/resources/db/migration/V11__merchant_administration.sql
- backend/src/main/java/com/paymesh/backend/security/accounts/MerchantAdministration.java
- backend/src/main/java/com/paymesh/backend/security/accounts/AdminQueries.java
- backend/src/main/java/com/paymesh/backend/security/auth/AdminManagementController.java
- backend/src/test/java/com/paymesh/backend/security/auth/AdminMerchantManagementIntegrationTest.java
- backend/scripts/activate-phase674-demo.sh
- backend/scripts/phase674_activation.py
- backend/scripts/test_phase674_activation.py
- frontend/admin_proxy.py
- frontend/assets/js/admin/routes.js
- frontend/assets/js/admin/model.js
- frontend/assets/js/admin/view.js
- frontend/assets/js/admin-tests.html
- frontend/assets/js/admin-tests.js
- frontend/tests/test_admin_proxy.py
- frontend/PHASE-6.7.4-ADMIN-DASHBOARD-MERCHANT-MANAGEMENT-REPORT.md

Modified:

- backend/src/main/java/com/paymesh/backend/security/accounts/AppUser.java — status/version transition helper.
- backend/src/main/java/com/paymesh/backend/security/accounts/Merchant.java — controlled registry activation helper.
- backend/src/main/java/com/paymesh/backend/security/auth/BusinessEndpointCatalog.java — explicit Admin endpoint catalog.
- backend/src/main/java/com/paymesh/backend/security/BoundedRequestBodyFilter.java — bounded Admin bodies/no-store.
- backend/src/test/java/com/paymesh/backend/security/auth/AdminAccountApiIntegrationTest.java — existing GET account-list contract now supported.
- frontend/dev_server.py — exact Admin routes/query handling and SPA paths.
- frontend/assets/js/api/config.js and api/client.js — bounded Admin API paths and presentation gating.
- frontend/assets/js/auth/session.js — supported non-active Merchant states.
- frontend/assets/js/portals/router.js and portals/view.js — Admin routes/views/shared-operation navigation guard.
- frontend/index.html and assets/css/app.css — Admin mount/responsive presentation.
- frontend/assets/js/portal-tests.js and tests/test_portal_routes.py — explicit sixteen-route expectations.
- README.md, PROGRESS.md and frontend/README.md — implemented/pending-activation status and handoff.

### Preservation and release decision

No live DB connection, live business request, account creation/password change,
financial mutation, V11 activation, OTP activation or service restart was performed.
Existing runtime counts6/4/4/2/6/4 are the supplied operator baseline, not a new
measurement. Original database/application were not accessed. Historical migrations,
protected credentials/configuration, Python AI and financial business implementations
remain untouched. No staging/commit/reset/clean/restore command was issued.

Concurrent external staging was observed: cached binary patch changed in16 paths
(new Phase674 source/scripts/tests/report) between snapshots. Initial index SHA-256
was `3a92cedfcccac2555164b32a971cc9d6492d795549e0a4419368e90f84f14c2a`;
intermediate final inspection was `61fdaf382db888f208806b517c9280681a34febbf8d6182dd94ee6732b5652ab`
with361 staged paths. Existing/concurrent staged content was left untouched; index
byte identity cannot be claimed. Git status showed365 total entries at that inspection.
Final whitespace/status observations are recorded below.

**IMPLEMENTATION AND ISOLATED VERIFICATION COMPLETE. OPERATOR REVIEW REQUIRED
BEFORE CONTROLLED ACTIVATION.** Live migration, deployment and browser verification
remain pending. No Phase6.8 begins. Existing Phase673 evidence limitations remain
unchanged; this is not production security certification.

Final documentation check: `git diff --check` passed. Git status: 365 entries; porcelain categories {'AM': 172, 'A ': 189, '??': 4}. Cached patch unchanged since the preservation inspection above. No index writes were performed by the implementation agent.

## Operator Step17 activate-phase674 evidence

Outcome: verified. Stage: frontend-restart. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-activate-phase674-20261115T045625Z-yd6r_0kn/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Final database audit preparation — November 15, 2026

### Confirmed evidence and operator reports

The protected V11 activation evidence was read at
`$HOME/.config/paymesh-demo/otp-step17-activate-phase674-20261115T045625Z-yd6r_0kn/evidence.json`.
It records success, V11/Admin frontend activation, OTP disabled, counts6/4/4/2/6/4,
equal before/after integrity fingerprints, verified backup list/extraction and no test
restore. These are recorded activation observations, not new live queries. No protected
record was altered. The new verifier uses that authentic pre-V11 archive, not the
older pre-OTP archive or an invented successful Phase673 pre-audit baseline.

The operator reported all36 Phase674 browser checklist items passed across Dashboard,
Merchant lifecycle, monitoring and Admin security. The later diagnostic does not
corroborate successful rejection: no rejection-test account/event was present. See the
authorization-resolution section below; rejection remains unverified, not database PASS.
The operator also confirms successful offline recovery of the exact pending disposable
Merchant, with terminal message `Disposable pending MERCHANT password reset successfully;
prior access tokens are invalidated.` The subsequent lifecycle outcome is to be checked
against actual DB state. These are **operator-confirmed results**, not independent
browser automation or a completed final database audit.

Current application verification remains300 isolated Java tests (zero failures/errors/
skips),752 frontend checks and successful Maven packaging. No application implementation
changed for this preparation, so those suites were not rerun. Existing Phase673 missing
historical session rows/fingerprints and unexplained historical Merchant increment
remain documented; a new baseline comparison does not reconstruct those older facts.

### Read-only verifier and exact operator command

New files:

- `backend/scripts/verify-phase674-closeout.sh` — protected-config/TTY wrapper.
- `backend/scripts/phase674_closeout.py` — V11-aware read-only audit.
- `backend/scripts/test_phase674_closeout.py` — mocked regression tests.

Modified: this report only. No application, migration, dependency, secret or historical
evidence file changed. Existing Phase673 verifier/activation/deactivation tools are
unchanged; the V10-only OTP launch path is never called.

Run in a private interactive Mac Terminal:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase674-closeout.sh"
```

There are no arguments and no mutation confirmation phrase. The only interactive
prompt is `Existing paymesh_demo_user database password (hidden): `. Never provide it
in chat, arguments or redirected input. The command must not be run under tracing,
pipes or output redirection. It writes sanitized evidence under the protected external
demo directory and appends its actual outcome to this report. **It was not executed
against the live database during preparation.** No deactivation, recovery or restart
command is part of this procedure.

### Actual checks and safe interpretation

The wrapper verifies owner/mode700 for the private directory and owner/mode600 for
protected environment files before loading them. The helper discovers current Java,
frontend, Python and LLM listener/cwd/start identities. It uses the V11-aware launch
validator, requires exact loopback demo/session/Origin settings and OTP launch flag
false, verifies Java/frontend PIDs against successful activation and Python/LLM full
identities against authentic activation evidence, and rechecks identities at the end.
An unexpected legitimate restart requires evidence review rather than bypassing the
check. The JAR on disk is checked for V1–V11/source migration identity; its current
file checksum does not independently attest the already-running JVM's loaded bytes.

PostgreSQL16 `psql`/`pg_restore` are selected explicitly from
`/Library/PostgreSQL/16/bin`. The database password is read without terminal echo;
only the child psql environment receives it, never command arguments/logs/evidence.
Every SQL operation is wrapped in a repeatable-read **READ ONLY** transaction with UTC
and a20-second statement timeout, plus libpq default_transaction_read_only=on. The
literal target and actual identity must be paymesh_demo/paymesh_demo_user/
127.0.0.1/5432. No original database/port8080 target exists in the verifier. It requires
successful V1–V11 and an enabled V10 account revocation trigger whose function body
matches the reviewed migration. OTP capability and all eligibility must remain disabled;
no currently usable unconsumed challenge or reset authorization may remain.

A combined database snapshot checks account identities/roles, one-owner membership
integrity, unchanged registration profiles and consistent account/registry/member/V11
states. It requires the disposable Merchant ACTIVE/enabled/MERCHANT-only, verified/
active registry and active membership. It checks one offline recovery success followed
by approval, suspension and reactivation, actual authenticated actor/source metadata,
original approval actor/time and retained ownership attestation reference. Unexpected
repetitions/order/state stop rather than inventing success. Prior successful audits,
including OTP reset evidence, must still exactly exist in the archive/live comparison.
If the named rejection account exists, it must be the single additional MERCHANT
registration, REJECTED/enabled with inactive/unverified ownership, retained reason and
authenticated rejection audit. Otherwise it must not be invented. Existing non-disposable
pending/operational roles, status, ownership and profile/password rows are compared to
the authentic archive. The later correction checks only the explicitly authorized operational demo-admin
self password-change event, against protected single-event authorization. otp-admin-demo
must remain unchanged; no password change there is claimed. Unexpected password changes fail;
extra version increments without sufficient audit are explicitly reported as unexplained,
not attributed to logout-all or another guessed action.

Counts are measured: the only supported outcomes are6/4/4/2/6/4 without the rejection
registration or7/5/5/3/6/4 with it. Unexpected account/financial counts stop. All eight
financial tables are compared by exact canonical row contents and multiplicities using
the established whitelisted COPY parser, NUMERIC preservation and column/type checks.
The custom archive path/mode/SHA256/list are verified. `pg_restore --data-only --file=-`
extracts data in memory only; no archive SQL is executed and **no restore is performed**.
Password hashes needed for equality comparisons exist only in memory, never sanitized
output or evidence. Count equality alone is not a financial integrity claim.

Each relevant offline/lifecycle/Admin password-change audit gets a separate session
assessment. Its historical cohort uses family creation time versus the actual event,
plus the event's version derived from the authentic baseline and successful changes.
An unexplained increment makes the exact event version unknown; the minimum supported
post-event version is used conservatively, with ambiguous versions reported. Lower
current versions alone never identify a pre-event family. Valid post-event families
need not be revoked. Retained pre-event unrevoked/late-revoked families fail strict
verification; absent rows are HISTORICAL_EVIDENCE_UNAVAILABLE, never historical PASS.
Equality/version ordering ambiguity is reported separately. V10 CURRENT_TIMESTAMP is
transaction start, whereas audit Instant is recorded after the write; neither is a
commit timestamp. Actual JWT acceptance/replay is not tested, legacy no-sid tokens
are not inventoried in auth_sessions, and deleted families cannot be reconstructed.
The existing live validator's current version/status/roles/revocation/expiry rules are
used for retained-family checks. This is not unrestricted historical token certification.

Java readiness, direct/proxied payment health, public SPA/Admin route availability,
current persistent-session launch configuration and disabled capabilities are checked
using GETs only. No login, refresh/logout, account mutation, financial mutation or AI
investigation is requested. Session functionality already confirmed in the browser
is distinct from configuration/GET checks here.

Expected sanitized successful output (actual counts and history vary):

```text
Counts users|merchants|memberships|registrations|payments|refunds: 7|5|5|3|6|4
V11/account/lifecycle/actor/audit/eligibility/grant checks: VERIFIED
Actual successful audit counts: {actual measured counts by event type}
Financial row contents: MATCH (8 pre-V11 archive tables; no restore)
DISPOSABLE_MERCHANT_PASSWORD_RECOVERED: HISTORICAL_EVIDENCE_UNAVAILABLE
MERCHANT_APPROVE: <actual retained-row result>
MERCHANT_SUSPEND: <actual retained-row result>
MERCHANT_REACTIVATE: <actual retained-row result>
OTP=false; persistent-session configuration/readiness/payment health/frontend: PASS
Evidence limitation: <actual documented limitation>
VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS
Verified read-only audit. Evidence: <protected evidence.json path>
```

Without a rejection account the first counts line is6|4|4|2|6|4. Event history output
above is illustrative, **not an expected fabricated result**: retained rows can yield
VERIFIED_FROM_RETAINED_ROWS, HISTORICAL_EVIDENCE_UNAVAILABLE or AMBIGUOUS_BOUNDARY.
CURRENT_SECURITY_FAILURE or REVOCATION_INCONSISTENT stops verification. A real Admin
password-change/rejection event adds its own measured line; do not require an event
that was not performed. Failure prints a fixed safe reason and private evidence path;
never remove checks, change rows or repeat resets merely to obtain a pass.

### Executed preparation tests and pending closeout

`python3 -m unittest discover -s backend/scripts -p 'test_phase67*.py'`:
**78 mocked operational tests passed** (53 existing +25 new), zero failures/errors.
New cases cover both count outcomes, unexpected counts/roles/state/actors, missing
audits/attestation, disabled recovery and live-capability rejection, usable grants,
unchanged pending/operational accounts, Admin self password change, financial numeric
comparison/mismatch, archive extraction/no restore and event-relative retained/missing/
post-event/boundary/currently usable session evidence. No live service or DB was called.
Bash syntax and Python compilation passed. No full Java/frontend/AI suite rerun was
needed because application code is unchanged. Final whitespace/index observations follow.

**Final database verification remains PENDING OPERATOR EXECUTION.** The verifier does
not turn operator browser confirmations into independently observed DB evidence.
No Phase6.8 work begins; OTP remains disabled and public on-screen OTP remains prohibited.

Final preparation checks: Bash/Python syntax passed; `git diff --check` passed.
Initial/final cached binary patch is identical. No staging/index operation was issued; concurrent external work remains untouched.
Git status has372 entries; categories {'AM': 173, 'A ': 192, '??': 7}. No live verification, restart, password reset, account creation or database write was performed.

## Operator Phase674 final read-only verification

Outcome: STOPPED; inspect private evidence, no automatic retry. Evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-verify-phase674-final-20261115T055205Z-0hvhy2md/evidence.json`. No mutation/restore/token test performed.

## Final-audit password failure diagnosis preparation — November 15, 2026

The actual failed protected evidence was inspected:
`$HOME/.config/paymesh-demo/otp-step17-verify-phase674-final-20261115T055205Z-0hvhy2md/evidence.json`.
It records success=false at read-only-snapshot, counts6/4/4/2/6/4, the reviewed enabled
V10 trigger, one successful ADMIN_PASSWORD_CHANGED, one offline disposable Merchant
recovery, one each approval/suspension/reactivation, no rejection and the two earlier
OTP resets. It does **not** retain the password-change target/actor or account snapshots.
Neither that historical failure nor the original activation evidence was modified.

The exact raising condition is inside `phase674_closeout.evaluate`: for each account,
collect successful `ADMIN_PASSWORD_CHANGED` rows whose resource_type is ACCOUNT,
resource_id equals that user's UUID and occurred_at is at/after the recorded V11
activation startedAt. If any exist, require that user's normalized login to equal the
literal `ADMIN` constant, `otp-admin-demo`. Otherwise raise exactly:
`Unexpected operational account password change; documented review required.`

This is an **audit-target allowlist failure, before the hash comparison**, not direct
proof of a current hash mismatch. A password changed back or rehashed can also produce
a different relationship to the baseline; lifecycle authorization-version increments
alone cannot trigger this particular condition. The exact disposable Merchant has its
separate documented offline recovery path. Both guarded offline recovery and Admin
Profile password-change source implementations were inspected: they use the actual
existing password/audit/version transaction paths, not a guessed endpoint or event.

The retained evidence establishes an unexpected post-activation password-change audit
target under this check, but does not identify which account. It would be speculation
to name operational demo-admin or call this a verifier bug before reading actual target
and hash equality evidence. No account change was automatically accepted. The existing
strict closeout verifier and original archive/baseline remain unchanged.

### Exact next operator command — diagnostic only

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/diagnose-phase674-password-mismatch.sh"
```

Run in a private interactive Mac Terminal without arguments, tracing, pipes or output
redirection. It prompts `Existing paymesh_demo_user database password (hidden): `.
No mutation confirmation is needed because no write/reset/restart operation exists.
**The diagnostic has not been executed against the live database during preparation.**

New files:

- backend/scripts/diagnose-phase674-password-mismatch.sh
- backend/scripts/phase674_password_diagnosis.py
- backend/scripts/test_phase674_password_diagnosis.py

Modified: this report only. No application, migration, closeout-verifier, activation
script, protected evidence or backup was changed.

### Diagnostic safeguards and output interpretation

The helper reuses the V11-aware launch inspection and existing strict listener/cwd/
identity checks, successful activation reference, literal demo target, PostgreSQL16
psql/pg_restore tools, READ ONLY repeatable-read transactions/UTC/statement limit and
protected hidden-password conventions. OTP configuration/capability and eligibility
must remain disabled. It does not invoke login/refresh/logout/OTP, any financial API,
recovery, service control or restore. It validates the original protected archive path,
mode and SHA256, checks its list and extracts only app_users/user_roles COPY data into
memory for this diagnostic, never executing archive SQL. No original database/port8080
is accessed. Existing service identities are rechecked at the end.

Disposable classification requires the protected dedicated-account manifest UUIDs and
exact matching original archive/current normalized names, not merely MERCHANT/ADMIN
role. Other identities are not silently designated disposable. For each current account,
sanitary evidence/terminal output contains login, classification/source, enabled/status/
roles, hash-changed YES/NO only (or explicitly no baseline for a new account), previous/
current authorization version and update timestamps. Successful recovery/password-change
audits include type/time, before/after-activation classification and the actual recorded
actor login or honest offline/local-demo source classification. Related lifecycle audit
types/times are shown separately; no password change is inferred from version movement.
No password/hash/digest/token/OTP/key/reset authorization or raw archive row is printed
or persisted. Hash inequality alone does not prove plaintext inequality: BCrypt rehashing
can also change bytes. An audit actor record is not a new independent authentication test.

The output names **all current accounts matching the exact failed verifier condition**.
A documented disposable Merchant recovery or disposable Admin self password-change
is explained only by matching protected identity and appropriate successful audit/source.
Any operational hash change, or operational Admin password-change audit even without net
hash difference, requires explicit operator review. No allowance is added to the verifier.
Exit0 means diagnosis completed without a current flagged mismatch, not closeout passed;
exit2 means diagnosis completed and found account(s) requiring operator explanation;
exit1 means a guard or diagnostic operation failed. `success=true` in diagnostic evidence
means diagnostic collection completed, not that account changes were authorized or that
Phase674 passed its audit.

Next: the operator runs the diagnostic and reviews only sanitized rows/event actor/time
information. If an operational password change is identified, stop for the operator's
specific explanation/authorization; do not whitelist it, reset it, alter audits or
replace the baseline. If new authentic evidence proves a narrow verifier defect, a
separately justified correction and regression can follow. Historical session and
Phase673 evidence limitations remain; Phase674 is **not closed** and Phase6.8 is not started.

### Executed tests

`python3 -m unittest discover -s backend/scripts -p 'test_phase67*.py'`:
**89 mocked tests passed** (78 existing +11 new), zero failures/errors in the final run.
New regressions demonstrate acceptance of both exact disposable cases, rejection of
operational password-change audit/hash cases (including the exact message), no hash
inference from lifecycle versions, real/self actor and manifest constraints, no secret
content in summaries, new-account baseline limits and read-only/source guard behavior.
Bash syntax, Python compilation and git diff --check passed. Initial new-test fixture
import/port-substring assertion errors were fixed, then the complete operational suite
was rerun successfully. No application or frontend suite rerun was needed; no application
code changed and no live diagnostic was run.

Git preservation: initial/final cached binary patches are identical. No staging/index/restore operation was issued. Final git diff --check passed.

## Operator password-mismatch diagnosis

Read-only diagnosis completed; NOT closeout certification. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-diagnose-phase674-password-mismatch-20261115T055856Z-1mmdwii9/evidence.json`.

## Exact demo-admin authorization and final verifier resolution — November 15, 2026

### Established cause and corrected browser attribution

The successful protected diagnostic at
`$HOME/.config/paymesh-demo/otp-step17-diagnose-phase674-password-mismatch-20261115T055856Z-1mmdwii9/evidence.json`
was inspected. The original verifier's strict scope correctly stopped at the previously
undocumented operational account change. It was **demo-admin**, not otp-admin-demo,
that received one successful authenticated self `ADMIN_PASSWORD_CHANGED` audit at
`2026-11-15T05:38:11.323483Z`, password hash different from the original archive and
version3→4. The operator now explicitly authorizes this exact change:

> Yes, I intentionally changed the demo-admin password during the Admin Profile browser test. I authorize this exact change.

This is a newly documented, one-event authorization, not evidence that the original
verifier indiscriminately misclassified disposable accounts. No general operational
Admin exception is introduced. The Admin Profile browser password-change test was
performed on **demo-admin**. **otp-admin-demo did not change**: diagnostic hash equality,
version1→1 and the old OTP audit remain. Earlier disposable-test guidance described
planned scope, not the actual tested account; this section corrects the attribution.

The diagnostic also corroborates the exact disposable Merchant recovery at
`2026-11-15T05:25:24.128213Z`, approval at05:28:33.595202Z, suspension at05:33:42.559122Z
and reactivation at05:35:22.474259Z, version2→6 and current ACTIVE/MERCHANT-only status.
Existing operational Merchants and the original pending registration showed unchanged
password hashes/versions; the original pending account remained PENDING_APPROVAL.
These are recorded diagnostic observations, not a newly executed final verification.

The diagnostic listed six accounts and no reject-demo registration; the failed audit
recorded counts6/4/4/2/6/4 and zero MERCHANT_REJECT successes. Consequently a successful
rejection workflow is **not corroborated and remains unverified/not demonstrated by
retained database evidence**. Do not infer a seventh account from the36-item browser
checklist report. Validation-only rejection UI checks may have occurred, but are not
proof of a committed rejection. No account should be created merely to reconcile this
report. If a rejection account actually appears later, the existing conditional strict
rejection checks still apply and the cause must be reviewed. Operator browser reports
remain distinct from database evidence.

### Separate protected authorization record

Created with exclusive creation/mode600 under the existing owner-only mode700 directory:

`$HOME/.config/paymesh-demo/phase674-demo-admin-password-change-authorization.json`

This is a new operator-authorization record, not a replacement of activation, diagnostic,
failed audit or backup evidence. No original evidence was modified. The record contains
the exact account UUID read from the original protected pre-V11 archive, normalized
login, authenticated self actor UUID/login, exact event timestamp/type/SUCCESS outcome,
expected version3→4, the quoted authorization and recording timestamp. It binds SHA256
of the original activation evidence, original diagnostic evidence and original archive.
The account's enabled/ACTIVE/ADMIN-only baseline and version3 were independently checked
by offline pg_restore extraction into memory; no live database connection or restore
was made. Hashes/raw rows were not printed or retained in this authorization record.

The original diagnostic did **not retain the new password-change event UUID**. The
record explicitly stores null eventId with NOT_RETAINED_IN_DIAGNOSTIC; no identifier
was fabricated. On final read-only execution, exactly one current event must match the
complete authorized account/type/actor/target/timestamp/outcome tuple, and its valid
observed UUID is recorded in new final evidence. An invented event-ID authorization is
rejected. Without an independent retained historical event UUID, arbitrary substitution
of a different valid UUID with otherwise identical immutable fields cannot be certified
historically. Likewise there is no retained post-change hash fingerprint: the verifier
checks inequality to the original hash plus exact diagnostic update timestamp, version
and audit tuple, not a fabricated fingerprint or plaintext comparison.

### Narrow verifier behavior

`phase674_closeout.py` now requires the protected record and its authentic evidence
bindings before database work. Original/archive/current identity must match the exact
recorded UUID and demo-admin login; both original/current records must be enabled ACTIVE
ADMIN-only. Original version must be3 and current version exactly4. The hash must differ
from the original archive, and the current account update timestamp must equal that
in the authentic diagnostic. Exactly one post-activation ADMIN_PASSWORD_CHANGED event
for this account is permitted, with ACCOUNT target, authenticated self actor, SUCCESS
and exact authorized timestamp. Missing, repeated, wrong-actor/target/time/outcome/version
or unexpected hash combinations fail. No additional unexplained increment is accepted
for this account. Any other operational password change still fails. otp-admin-demo
requires full original account-row equality unless a separate future authorization is
explicitly designed and reviewed; none is included here. Other existing non-target
account rows are checked strictly against the original archive as well.

The authorized event enters the same event-relative session verification as Merchant
recovery/approval/suspension/reactivation. Pre-change families must be revoked as required;
post-change families are not incorrectly treated as pre-change merely because of version
differences. Missing rows remain HISTORICAL_EVIDENCE_UNAVAILABLE and timestamp/version
boundaries remain ambiguous rather than historical PASS. A retained unrevoked pre-change
family still stops final verification. No live token acceptance/replay is performed.
Existing Phase673 historical/fingerprint/version limitations remain untouched.

All original V11 identity/migration, Merchant attestation/actor/lifecycle/membership,
conditional rejection, prior audit retention, eight-table exact financial comparison,
six payment/four refund contents, OTP-disabled/eligibility/grant, runtime health and
preserved Python/LLM checks remain. No original baseline/archive was replaced.

### Exact next operator command

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase674-closeout.sh"
```

No arguments or new confirmation phrase. Enter the database password only through the
hidden /dev/tty prompt. The command loads the new protected exact-event authorization;
no login, password update, financial mutation, OTP activation or service restart occurs.
The protected record must stay owner-only mode600. If its permissions/source checks
fail, stop rather than broadly relaxing the verifier. New output/evidence reports the
actual event/session/history/financial results; do not claim final PASS before execution.
Current retained count evidence supports6/4/4/2/6/4, not an invented seventh account.

### Actual preparation tests and changed files

Complete relevant mocked operational run:
`python3 -m unittest discover -s backend/scripts -p 'test_phase67*.py'` —
**105 tests passed**, zero failures/errors (89 prior tests,16 new exact-authorization
regressions). Existing tests were updated where the new requirement expressly tightens
unapproved disposable-Admin mutations; they do not grant other account exceptions.
Cases include exact accepted authorization, missing/invalid/protected/source-binding
records, different UUID/login/scope, wrong actor/target/timestamp/outcome, fabricated or
malformed event ID, missing/additional events, wrong versions, unchanged hash, unchanged
disposable Admin, other operational changes, retained pre-change revocation failure and
preserved lifecycle/OTP/financial checks. Bash/Python syntax and final git diff --check
results follow. No application/frontend/Java suite rerun was needed: application code
and migrations are unchanged.

Repository files changed:

- backend/scripts/phase674_closeout.py
- backend/scripts/test_phase674_closeout.py
- backend/scripts/test_phase674_password_diagnosis.py
- backend/scripts/test_phase674_authorization.py (new)
- frontend/PHASE-6.7.4-ADMIN-DASHBOARD-MERCHANT-MANAGEMENT-REPORT.md

External protected record created: the single authorization JSON listed above. Existing
activation/archive/failed-audit/diagnostic evidence remains unchanged. No database write,
password change, account creation, financial mutation, service restart or live final
verification was performed during preparation. **Phase674 remains open pending operator
execution and review of final results; Phase6.8 is not started.**

Final preparation: all105 operational mocks passed; Bash/Python syntax and
`git diff --check` passed. Protected authorization mode/source checks passed.
Initial/final cached binary patches are identical. No Git index/staging operation was issued.

## Operator Phase674 final read-only verification

Outcome: VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS. Evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-verify-phase674-final-20261115T060830Z-_lddxg69/evidence.json`. No mutation/restore/token test performed.

## Official Phase 6.7.4 closeout — November 15, 2026

**PHASE 6.7.4 — COMPLETE WITH DOCUMENTED EVIDENCE LIMITATIONS.**

**Release decision: GO for continued private local portfolio development.**
**Not production security certification.**

V11 controlled activation, Admin dashboard and Merchant management implementation
are complete. This definitive section supersedes earlier pending/failure/preparation
status statements; the earlier records remain chronological evidence. The strict final
verifier and exact one-event authorized Admin exception are unchanged by closeout.

### Final evidence reviewed, not rerun

The actual final protected evidence was inspected:

`$HOME/.config/paymesh-demo/otp-step17-verify-phase674-final-20261115T060830Z-_lddxg69/evidence.json`

It records success=true, stage read-only-final-verified and
`VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS`. The operator's terminal output agrees.
No new audit, live database access, application call, test run, restore, recovery or
service restart was performed for this documentation task. Original activation,
failed-audit, diagnostic, exact operator-authorization and backup evidence remain intact.

Previously executed automated results, not new documentation-closeout executions:

| Verification | Passed result |
| --- | --- |
| Isolated Java | 300 tests; zero failures/errors/skips |
| Frontend automated checks | 752 (722 JavaScript assertions and30 proxy tests) |
| Mocked operational checks | 105 |
| Maven packaging and Bash/Python syntax | Passed in the preceding implementation/preparation batches |

These are separate evidence categories; no new combined browser-pass count is inferred.

### Verified final database, lifecycle and runtime state

Counts users|merchants|memberships|registrations|payments|refunds:
**6|4|4|2|6|4**.

V11/account/lifecycle/actor/audit/eligibility/grant checks are VERIFIED. The eight exact
financial row comparisons against the protected pre-V11 archive matched, including
all six original payments and four refunds. Compared tables: payments, refunds,
payment_gateway_transactions, idempotency_keys, simulated_gateway_outcomes,
webhook_events, reconciliation_jobs and reconciliation_attempts. This is exact row
content/multiplicity evidence, not merely matching table counts. The archive was
verified/extracted/compared; **no test restore was performed**.

The enabled ACTIVE MERCHANT-only disposable Merchant has verified/active registry and
active membership, with original approval actor/time and ownership attestation retained.
Successful offline password recovery while pending, approval, suspension and reactivation
explain all four Phase674 authorization increments **2→6**. The original non-disposable
pending registration remains pending; operational Merchants retain their original state.
This four-increment explanation does not explain away the earlier Phase673 version gap.

The actual Admin Profile password-change test was **demo-admin**, not otp-admin-demo.
The operator explicitly authorized this exact authenticated self event, timestamp
2026-11-15T05:38:11.323483Z, with exact archive/current identity and version **3→4**.
The protected single-event authorization was enforced; no general Admin exemption exists.
**otp-admin-demo remains unchanged**, including version1→1 and original password hash.
No plaintext/hash is included in this report. The final evidence retains the observed
matched Admin event UUID; the authorization did not fabricate a previously unretained ID.

Actual successful audit counts:

| Event | Count |
| --- | ---: |
| ADMIN_PASSWORD_CHANGED | 1 |
| ADMIN_PASSWORD_RECOVERED | 1 |
| DISPOSABLE_MERCHANT_PASSWORD_RECOVERED | 1 |
| LOCAL_DEMO_PASSWORD_RESET | 2 |
| MERCHANT_APPROVE | 1 |
| MERCHANT_REACTIVATE | 1 |
| MERCHANT_REJECT | 0 |
| MERCHANT_SUSPEND | 1 |

All five Phase674 event-relative session checks returned
**VERIFIED_FROM_RETAINED_ROWS**:

- DISPOSABLE_MERCHANT_PASSWORD_RECOVERED
- MERCHANT_APPROVE
- MERCHANT_SUSPEND
- MERCHANT_REACTIVATE
- ADMIN_PASSWORD_CHANGED

No retained pre-event family passed the verifier's current-family authentication checks.
This certifies the reported retained-row conditions, not missing/deleted historical
sessions or actual replay acceptance of every issued JWT. Post-event families were
correctly excluded from pre-event revocation assertions.

OTP remains false, recovery eligibility disabled and no usable outstanding recovery
grant/challenge was found. Java readiness, direct/proxied payment health, frontend/Admin
route availability and persistent-session configuration passed the operator-run verifier.
Python AI and LLM identities matched the authentic activation evidence and remained
preserved. This closeout did not independently repeat any runtime check. The protected
recovery key remains stored but unused as recorded at Phase673 closeout; no new deletion
or key inspection is claimed. On-screen OTP must never be enabled publicly.

### Browser evidence correction and remaining limitations

The operator initially reported all36 browser checklist items passed. The retained
records establish no additional rejection registration and **zero successful
MERCHANT_REJECT** events. Consequently successful live rejection remains unverified;
it must not be described as passed. The implemented rejection tests are automated
coverage, not a live rejection success. No seventh account is inferred or created.
No revised exact browser-pass total is invented. Browser confirmations remain distinct
from final read-only database/session evidence and are correctly attributed to the
actual tested Admin account.

Remaining limitations:

- No direct live JWT acceptance/replay test was performed.
- Legacy no-sid access tokens are not inventoried in auth_sessions.
- Phase673 historical session/fingerprint limitations and its earlier unexplained
  Merchant increment remain unchanged. New Phase674 retained-row results do not
  reconstruct that older evidence.
- The original diagnostic did not retain the authorized Admin event UUID or a new
  post-change hash fingerprint; exact actor/time/version/identity authorization and
  current observed event UUID are preserved without fabricating historical evidence.
- The backup was verified and exactly compared, but no test restore occurred.
- Successful live rejection remains unverified as described above.
- This is a private simulated portfolio environment, not production security
  certification or proof of bank settlement/refund arrival. Public production-grade
  recovery and deployment hardening remain separate work.

### Documentation handoff

Updated only:

- frontend/PHASE-6.7.4-ADMIN-DASHBOARD-MERCHANT-MANAGEMENT-REPORT.md
- README.md
- PROGRESS.md
- frontend/README.md

No application/verifier change, database access/write, password reset/account creation,
financial mutation, OTP activation, service restart or automated test rerun occurred.
No original protected evidence was changed and no Git staging/commit/reset/clean/restore
operation was issued. Final whitespace/index-preservation observations follow.

**Next: Phase 6.8.1 — Merchant Dashboard, Profile and Transaction Monitoring.**
Ready to begin on instruction; no Phase6.8 implementation starts in this closeout.

Final documentation checks: `git diff --check` passed. Initial/final Git index SHA256 and cached binary diff are identical; staged content is unchanged. No tests or live operations were rerun.
