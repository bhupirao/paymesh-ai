# Phase 6.8.2 — Merchant Payment Links and gateway selection

Implementation and isolated verification; **not deployed**. Phase681 remains open:
analytics deployed per operator; native browser verification, disposable Merchant
password change and final audit remain pending. Phase673/674 evidence limitations
are unchanged. No checkout execution or Phase683 implementation is included.

## Architecture and authorization

`PaymentLinks` reuses `MerchantPortal.scope()` (package-scoped, unchanged checks).
Every read/mutation acquires the existing transaction-scoped account-administration
advisory lock, validates current JWT/session/account state and exact MERCHANT role,
requires exactly one active membership, and a verified/active registry with V11
ACTIVE business lifecycle. Ownership is always server-derived. ADMIN-only accounts
cannot use these APIs. Detail/cancel select by UUID **and** owned Merchant; other
Merchants receive the same 404 as a missing record. Existing bearer/session validation,
OTP gate, financial business services and gateway execution are unchanged.

The shared lock serializes low-volume link writes and account lifecycle changes
across application instances. PostgreSQL uniqueness additionally protects Merchant/key
and public tokens. Successful create/cancel and `PAYMENT_LINK_CREATED` /
`PAYMENT_LINK_CANCELLED` authenticated-actor audit commit or roll back together.
No tokens, references or description are put in audit metadata. GETs do not update
link/financial rows; detail reads take locks for consistent authorization.

## Additive V12 (NOT applied live)

`V12__merchant_payment_links.sql` adds only `payment_links`. UUID PK, Merchant FK,
unique 43-character base64url public token, NUMERIC(14,2) amount (0.01 through
999999999999.99), currency/method/gateway constraints, bounded reference/description,
status, creation/update/expiry instants, nullable unique payment FK, Merchant-scoped
unique idempotency key and SHA-256 canonical request fingerprint; ownership/time and
expiry indexes. V1–V11 are unmodified. Existing rows are not seeded or updated.

AuthStore supplies 32 SecureRandom bytes (256 bits) per public token. The token is
**retrievable plaintext in this protected database**, deliberately not hash-only:
Merchant create/replay/detail must redisplay a shareable path. Database/backups must
be protected; token leakage is a bearer-capability risk for future checkout. It is
omitted from list responses, errors and audit metadata. No public lookup endpoint is
implemented. A future public checkout must independently validate lifecycle/expiry,
never log tokens, use appropriate rate limits and avoid URL/referrer leakage.

Effective lifecycle:

| Stored/effective state | Phase682 action |
| --- | --- |
| ACTIVE and expiresAt > server time | Read, cancel |
| ACTIVE and expiresAt <= server time | Read as EXPIRED; cancel conflicts |
| CANCELLED | Read; repeated cancel returns 409 |
| EXPIRED | Read; cancel conflicts |
| PAID | Reserved for Phase683; read only; cancel conflicts |

No request can set status/paymentId. Database constraint binds PAID to a non-null
payment association. No hidden GET expiry updates, scheduler or payment creation.
Server time is PostgreSQL `clock_timestamp()` captured **after** authorization lock
acquisition. Expiry is exactly 1/24/168 hours from creation, independent of timezone.
All timestamps are ISO-8601 UTC instants. No processing state/execution is enabled.

## Exact API contracts

All paths below prefix `/api/v1/merchant/payment-links`, require current active
MERCHANT Bearer JWT, return no-store JSON, and reject unknown query/body fields and
duplicate query/JSON keys. No client merchant/user/actor/status/gateway/payment/URL
field is accepted. Backend/proxy cap mutation bodies at 4096 bytes.

- `POST /`: required `Idempotency-Key` (1–128 ASCII letters/digits/`.`/`_`/`:`/`-`).
  Body: `{ "amount": 100.00, "currency":"INR", "paymentMethod":"UPI",
  "customerReference":"order-123", "description":"Invoice", "expiryHours":24 }`.
  Amount is decoded as its exact decimal text; a decimal string is also accepted.
  Maximum12 integer/2 fractional digits, positive, no exponent/sign/leading-zero
  variants. Empty reference/description strings are allowed but fields are required;
  limits100/500 UTF-16 units, no control characters or malformed Unicode; no surrounding
  whitespace. Frontend trims text and normalizes amount to two decimals. Expiry must
  be integer1/24/168. Returns201 new,200 exact replay;409 conflicting same-key intent.
- `GET /?page=0&size=5&search=order-123&status=ACTIVE&currency=INR`: optional filters;
  page0–10000,size1–50(default5). Search case-insensitive literal reference substring
  or exact UUID. Search<=100; status ACTIVE/CANCELLED/EXPIRED/PAID; INR/USD. Stable
  order createdAt DESC,linkId DESC. Response `{items:[],page,size,total}`.
- `GET /{linkId}`: owned canonical lowercase UUID; full detail.
- `POST /{linkId}/cancel`: **no body, no idempotency header required**.200 cancelled
  record;409 repeated/ineligible/expired. Row lock and shared authorization lock
  prevent duplicate cancellation audits and lifecycle races.

Record fields: `linkId, merchantId, amount` (**exact decimal string**), `currency,
paymentMethod, gatewayName, customerReference, description, status, createdAt,
updatedAt, expiresAt, paymentId`. Create/replay/detail/cancel also return
`checkoutPath: "/checkout/<43-character-token>"`; list omits it. No arbitrary URL or
host-derived server URL is returned. Frontend validates that path and constructs
an address from the existing same-origin application origin. `/checkout/...` remains
an unknown/non-operational route until Phase683; copying does not execute anything.

Gateway selection: INR+UPI/CARD -> MOCK_RAZORPAY; USD+CARD -> MOCK_STRIPE; USD+UPI
and all other combinations ->400. This is link routing metadata, not proof a gateway
transaction occurred. Existing `GatewayRouter.route(currency)` is reused for selection (without processPayment);
no historic payment validation/routing behavior was changed.

Errors:400 invalid fields/query/key;401 absent/expired/revoked JWT;403 invalid current
Merchant context;404 unknown/unowned link;409 intent/lifecycle conflict;413 size;
415 wrong create media type;503 unconfirmed/unavailable operation. Existing proxy
502/504, network/timeouts and429 are safely surfaced. No raw exception/body is shown.

## Frontend

Routes `/merchant/payment-links` and `/merchant/payment-links/create` use the
single-document router and existing session. List filters/search/server pagination
(default5, Previous/Next arrows), detail, copy, status, expiry, create/review/confirm,
explicit cancellation review and refresh use safe createElement/textContent.
Currency restricts available methods and shows expected gateway. No active checkout
or financial mutation exists. Full Payments/Refunds list paging and full chart datasets
are unchanged; prior dashboard independent five-row exact tables remain in place.

Creation freezes canonical fields plus crypto.randomUUID key in memory. Pending
submissions are blocked. Uncertain responses preserve the original intent/key for
**deliberate exact retry**, never automatic retry.201/200 and returned field/expiry
matching are validated before confirmation. New intents obtain new keys.409 needs
operator review. An uncertain cancellation requires authoritative detail refresh
before another action. Shared portal guards block navigation/account switching while
pending/uncertain; existing unrelated financial/AI guards also block link mutations.
Logout/session replacement clears records, drafts, review/key and pagination; sequence
and session-version checks suppress late responses. No persistent browser storage.
Refresh/logout loses uncertain intent recovery: inspect authorized list before another
creation. Cancellation uncertainty is not treated as confirmed cancellation.

Tables scroll on narrow screens; labelled native forms/buttons, live status/aria-busy,
text status labels and bounded safe text preserve accessibility. Native browser and
375px keyboard/layout verification remain pending.

## Verification

Final executed counts and preservation observations are appended below. Financial
operations in tests use isolated PostgreSQL or mocked fetch only. No live DB/business
request, OTP activation, service restart, deployment, financial mutation or password
change was performed. Python AI code/dependencies and historical migrations unchanged.
No git stage/commit/reset/clean/restore was performed; concurrent staging is left intact.

## Files in this batch

Backend: new V12 migration, `security/accounts/PaymentLinks.java`,
`security/auth/PaymentLinkController.java`, `security/auth/PaymentLinkIntegrationTest.java`;
modified MerchantPortal scope visibility, BusinessEndpointCatalog and
BoundedRequestBodyFilter (exact routes/size only).
Frontend: new `payment-links/model.js`, `payment-links/view.js`, `payment-link-tests.html`,
`payment-link-tests.js`, `tests/test_payment_link_proxy.py`; modified merchant routes/view,
portal view/test, API client/decimal, index.html, merchant_proxy.py and explicit route-count
proxy test. Documentation: this report, Phase681 report, README, PROGRESS, frontend README,
API reference. Existing in-progress pagination files are preserved.

## Live handoff — operator approval required

Do **not** use the old V11-only Phase681 deployment scripts for this V12 artifact.
No live activation is authorized or performed here. Before activation prepare/review a
V12-aware guarded procedure using existing private demo helpers: validate actual listener
identities and exact paymesh_demo/paymesh_demo_user loopback5432 target; verify V1–V11,
OTP=false and baseline6/4/4/2/6/4; protected timestamped PostgreSQL16 custom backup,
archive-list/extraction/checksum; capture exact financial/account fingerprints; verify
packaged V12; restart only verified demo Java with preserved protected config and normal
Flyway enabled/schema validation; confirm V12 and unchanged existing rows/OTP gate; restart
only the frontend because Python allowlists are imported at server startup. Preserve
Python/LLM identities. Stop on any mismatch; no clean/repair/automatic restore/downgrade.
No activation command is supplied that could accidentally reuse a V11-only guard.

After an explicitly reviewed activation, operator browser checklist:

1. Hard refresh Merchant portal; navigate to Payment Links; check empty/list/filter/page states.
2. Review each allowed currency/method and USD+UPI prevention; amount boundary/invalid text.
3. Only with separate explicit mutation approval, create a simulated link; review UUID,
   exact amount/gateway/expiry; verify no payment/refund row was created.
4. Copy URL; verify clearly unavailable Phase683 checkout notice; do not enter credentials.
5. Inspect detail and explicitly cancel with review; expired/repeated cancellation conflicts.
6. Merchant B cannot list/get/cancel Merchant A links; ADMIN and pending/suspended denied.
7. Check375px tables/forms, keyboard labels/focus/loading/errors. No automatic mutations.
8. Logout/switch/session expiry clears link details/intents; refresh restores only existing
   session via secure cookie, never an in-memory uncertain intent. Original dashboards,
   charts/pagers/payment/refund/AI workspaces remain functional with explicit actions.

No new test link, payment, refund or account is authorized by this checklist alone.

## Final executed results — 2026-11-15

| Verification | Actual result |
| --- | --- |
| Full isolated PostgreSQL Java suite |336 tests,0 failures/errors/skips;14 new link tests |
| Complete mocked JS batch |983 assertions across14 suites |
| Full frontend proxy suite |39 tests passed (3 new) |
| Combined frontend total |1022 (983 mocked JS +39 proxy) |
| Existing operational mocked suite |111 tests passed |
| Maven package -DskipTests |BUILD SUCCESS; V12/PaymentLinks/PaymentLinkController verified in JAR |
| JS syntax |51 source files passed node --input-type=module --check |
| Modified Python syntax |merchant_proxy and new/updated proxy tests passed |
| git diff --check |passed |

JS breakdown: API10,auth34,payment94,refund125,investigation149,QA18,portal73,
registration39,session/recovery67,Admin113,Merchant97,analytics/switch46,
pagination51,payment-links67. Mocked DOM/Node runtime is **not native browser testing**.
The Merchant count grew through existing route-derived assertions for the new routes.

Commands actually run: `cd backend && bash scripts/test-isolated.sh` (fresh isolated
cluster, retained test files, stopped on completion); `mvn package -DskipTests`;
`python3 -m unittest discover -s frontend/tests -v`;
`python3 -m unittest discover -s backend/scripts -p 'test_*.py'`; syntax/diff checks.
The14 browser-compatible module suites were imported in the existing mocked DOM runtime;
new native-browser mocked suite URL:
http://127.0.0.1:5500/assets/js/payment-link-tests.html.
Initial test compile errors (MockMvc get helper name/setup checked exception), the
new static DOM test fixture integration, and obsolete20-route assertions were corrected;
final batches above passed. Final backend batch also covers invalid-ID cancellation
body limits and use of existing GatewayRouter.

No Python AI implementation change, so its suite was not rerun. No native browser or
live protected API verification was performed. Supplied live entity baseline
6/4/4/2/6/4 was not independently queried. Live schema remains operator-supplied V11;
this batch applied V12 only inside disposable isolated tests.

Git cached binary diff matches the initial captured diff; zero changed cached patch
blocks at observation (416 status entries, including pre-existing changes). Existing
staged/unrelated work is untouched. No staging/commit/restore/cleanup or protected
evidence/backup/configuration change was made. Final recheck follows documentation.

## Phase683 integration addendum (implementation only; NOT closeout/activation)

Customer checkout is now implemented in the Phase683 report; the earlier “checkout coming”
text above records the Phase682-only implementation baseline. V12 bytes remain unchanged.
Additive V13 retains V12's successful-only association and adds durable checkout attempts,
FK ownership, unique blocking/success slot and transactional outcome synchronization.
Merchant projection adds PROCESSING, checkoutAttemptStatus and failedAttemptCount; cancellation
refuses unresolved accepted attempts, including failed-history timestamp-order anomalies.
Successful details explicitly open existing authorized payment lookup; no auto refund/AI.
Combined guarded activation is prepared at backend/scripts/activate-phase682-683-demo.sh,
from verified live V11 to V12/V13; it replaces no previous evidence or backup. It was not run.
Phase682 live verification and Phase681 pending checks remain OPEN, with historical evidence
limitations preserved. No public customer payment was executed by the agent.
