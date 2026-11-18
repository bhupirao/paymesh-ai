# PayMesh AI API reference

This is the authoritative human-readable API contract, verified against the current Spring MVC controllers, DTOs, security catalogs, and exception handlers. The provider and refund behavior is simulated. There is no live Razorpay/Stripe integration and no real money movement. This project is not production certified.

Base URL examples use `http://127.0.0.1:18080` for the controlled local demo. Use HTTPS in any deployment where traffic crosses an untrusted network. Do not place actual bearer credentials in command-line arguments or terminal output.

## Authentication matrix

| Route group | Authentication | Authorization |
|---|---|---|
| `GET /api/v1/payments/health`, `GET /actuator/health`, `GET /actuator/health/liveness`, `GET /actuator/health/readiness` | Public | Payment health is static; liveness excludes PostgreSQL; readiness includes PostgreSQL; health components/details are hidden |
| `POST /api/v1/auth/login` | Public, rate limited | Credentials verified by existing account service; no other `/api/v1/auth/**` route is allowed |
| Payment, refund, and gateway history routes below | `Authorization: Bearer <JWT>` | ADMIN or MERCHANT; MERCHANT requires active verified membership for the payment's merchant. ADMIN cross-merchant business access is permitted and audited per the business-security design |
| `GET /actuator`, `GET /actuator/info` | ADMIN JWT | ADMIN only |
| Mock webhook routes | HMAC-SHA256 headers | Provider-specific configured webhook secret; JWT does not replace HMAC |
| Settlement routes | Separate `Authorization: Bearer <PAYMESH_SETTLEMENT_ADMIN_TOKEN>` | Settlement token only; neither JWT nor ADMIN role substitutes |
| Uncatalogued route/method | Denied | No public wildcard; default deny |

The method catalogs allow HEAD for GET routes and OPTIONS only on enumerated paths; these methods inherit the matching route's authentication policy. No additional endpoint is created by that method matching.

JWT access tokens use RS256 and expire after 900 seconds (15 minutes). There is no refresh endpoint. Renew by authenticating again at login. Current account enabled status, authorization version, and roles are checked server-side. A merchant-supplied `merchantId` is accepted only after verified membership authorization. Out-of-scope resource access uses 404 to avoid existence disclosure; role or creation-scope denial uses 403.

## Common response and error behavior

Security error bodies are not the application validation schema: 401 is `{"status":401,"message":"Authentication failed"}`, 403 is `{"status":403,"message":"Access denied"}`, login 429 is `{"status":429,"message":"Too many login attempts"}` with `Retry-After`, oversized body 413 is `{"status":413,"message":"Request too large"}`, and authentication configuration/state unavailable 503 is `{"status":503,"message":"Authentication unavailable"}`. 401 responses include `WWW-Authenticate: Bearer`; auth responses disable caching.

Application API errors use `timestamp`, `status`, `error`, `message`, `fieldErrors`, and `path` as present in the `ApiErrorResponse`. Validation/invalid arguments return 400; absent resources return 404; idempotency conflicts and ineligible state/amount operations return 409; gateway failure exceptions may return 503. A request-body limit violation returns 413. Do not rely on fields omitted from a particular error response.

## Public health

These paths are explicitly enumerated in the legacy security endpoint catalog:

| Method and path | Authentication | Behavior |
|---|---|---|
| `GET /api/v1/payments/health` | None | Static payment-service status; does not probe PostgreSQL |
| `GET /actuator/health` | None | Aggregate health; sensitive component details are not returned |
| `GET /actuator/health/liveness` | None | Liveness-state group only; a PostgreSQL outage alone does not make this group DOWN |
| `GET /actuator/health/readiness` | None | Includes application readiness and PostgreSQL health |

`GET /actuator` and `GET /actuator/info` require an ADMIN JWT. Only `health` and
`info` are exposed over Actuator HTTP. Other paths, including `env`,
`configprops`, `beans`, and `heapdump`, are not exposed and remain denied by the
security fallback. The health paths return minimal status only; no credentials,
connection settings, or component details are exposed.

### `GET /api/v1/payments/health`

Static payment-service liveness-style response; it does not test PostgreSQL or gateway health.

- Auth: public.
- Request: no body or required headers.
- Success: 200 `{"service":"PayMesh AI Payment Service","status":"RUNNING"}`.

### `GET /actuator/health`

Spring Boot aggregate health endpoint; public. Health components and details
are suppressed. It is distinct from the static payment health route.

### `GET /actuator/health/liveness` and `GET /actuator/health/readiness`

Both paths are public and return minimal Actuator health status. Liveness
contains only `livenessState` and does not depend on PostgreSQL. Readiness
contains `readinessState` and the `db` contributor, so it reflects PostgreSQL
availability. Both routes are explicitly matched in the legacy security
catalog; they do not grant access to other Actuator endpoints.

### `GET /actuator` and `GET /actuator/info`

ADMIN JWT required. These are the other Actuator endpoints exposed by the current application properties. No custom response shape is promised here beyond Spring Boot Actuator's response.

## Login

### `POST /api/v1/auth/login`

- Auth: public; rate-limited per remote address.
- Headers: `Content-Type: application/json`.
- Body: `{"login":"merchant-login","password":"secret entered securely"}`.
- Validation: login required, at most 255 characters; password required, at most 72 characters. Invalid credentials, disabled account, stale authorization state, or roleless account receive a generic failure.
- Success: 200 `{"accessToken":"<token>","tokenType":"Bearer","expiresIn":900,"expiresAt":"<ISO-8601 instant>"}`.
- Errors: 400 invalid request; 401 generic authentication failure; 429 rate limit; 413 login body larger than 4096 bytes; 503 JWT/authentication configuration unavailable.
- Idempotency: not applicable. Login returns a new access token; there is no refresh token or refresh route.

Do not put passwords in shell history. Capture tokens without printing them and renew by logging in again after expiry.

## Payments

### `POST /api/v1/payments`

Create a payment. Auth: ADMIN or MERCHANT JWT. The requested merchant must exist and be verified/active; a MERCHANT must have active verified membership. ADMIN creation is also scoped to an existing verified, active merchant.

- Required headers: `Authorization: Bearer <JWT>`, `Content-Type: application/json`, `Idempotency-Key` (1–255 nonblank characters).
- Body:

```json
{"merchantId":"DEMO_MERCHANT_A","amount":200.00,"currency":"INR","customerId":"demo-customer-unique","paymentMethod":"UPI"}
```

- Validation: merchantId, currency, customerId, paymentMethod are nonblank; amount is at least 0.01 and has at most 12 integer and 2 fractional digits. INR routes to MOCK_RAZORPAY; USD routes to MOCK_STRIPE. Unsupported currencies do not trigger provider fallback and produce a failed result on processing.
- Success: 201 for a newly created payment; 200 for an idempotent replay with the same key and request.
- Errors: 400 invalid input/missing required key; 401 missing/invalid JWT; 403 authenticated caller lacks creation authorization; 404 unknown/out-of-scope resource semantics; 409 conflicting idempotency reuse; 413 body too large; 503 gateway/infrastructure failure.
- Response fields: `paymentId`, `merchantId`, `amount`, `currency`, `customerId`, `paymentMethod`, `status`, `createdAt`.
- Idempotency: the key is scoped by the service to the payment creation request; reuse for a different request conflicts. For a deliberate replay, send the exact same request and key.

### `GET /api/v1/payments/{paymentId}`

Retrieve one payment. Auth: ADMIN or owning MERCHANT JWT. Path value is a UUID; no body.

- Success: 200 `PaymentResponse` with the fields listed above.
- Errors: 401 missing/invalid JWT; 404 absent or out-of-scope payment; malformed UUID follows framework path conversion error behavior (400).
- Idempotency: not applicable.

### `POST /api/v1/payments/{paymentId}/process`

Process an existing payment. Auth: ADMIN or owning MERCHANT JWT. No request body; path value is a UUID.

- Success: 200 `PaymentResponse`.
- Errors: 401 missing/invalid JWT; 404 absent/out-of-scope payment; 409 if a state conflict is reported; 503 when a gateway call fails uncertainly. Repeated processing is protected by the persisted lifecycle/claim and does not issue a second charge for a payment already claimed or terminal.
- Idempotency: payment ID and state/atomic processing claim prevent duplicate gateway charging; this route does not take an `Idempotency-Key`.

### `GET /api/v1/payments/{paymentId}/gateway-transactions`

List gateway attempts for a payment. Auth: ADMIN or owning MERCHANT JWT. No body.

- Success: 200 JSON array; can be empty if no attempt exists.
- Each item: `id`, `paymentId`, **`gatewayName`**, `gatewayTransactionId`, `status`, `errorCode`, `errorMessage`, `createdAt`, `updatedAt`.
- Errors: 401 missing/invalid JWT; 404 absent/out-of-scope payment.
- Idempotency: read-only.

## Refunds

Refund records are simulated; they are not provider reversals. Multiple partial refunds are supported. The sum of successful refunds cannot exceed the original amount through the locked application refund flow. A partial refund leaves payment status SUCCESS; refunding the remaining balance changes it to REFUNDED. A full refund uses the remaining refundable amount.

### `POST /api/v1/payments/{paymentId}/refund`

- Auth: ADMIN or owning MERCHANT JWT.
- Required headers: `Authorization: Bearer <JWT>`, `Content-Type: application/json`, `Idempotency-Key` (1–255 nonblank characters).
- Body: `{"amount":200.00}`. Amount must be ≥0.01, at most 17 integer digits and 2 fractional digits.
- Success: 201 new refund, 200 exact idempotent replay (same payment, key, amount).
- Errors: 400 invalid amount/missing header; 401 missing/invalid JWT; 404 absent/out-of-scope payment; 409 key reused with a different amount, payment not SUCCESS, or amount greater than remaining refundable balance.
- Response: `refundId`, `paymentId`, `amount`, `status`, `createdAt`.
- Idempotency: one refund per `(paymentId, Idempotency-Key)`; exact replay returns the stored refund. A different key means a distinct refund request.

### `GET /api/v1/payments/{paymentId}/refund`

Return the latest refund. Auth: ADMIN or owning MERCHANT JWT. 200 with one `RefundResponse`; 401 unauthenticated; 404 if payment is absent/out of scope or no refund exists.

### `GET /api/v1/payments/{paymentId}/refunds`

Return refund history in creation order. Auth: ADMIN or owning MERCHANT JWT. 200 JSON array, including `[]` for an existing payment with no refunds; 401 unauthenticated; 404 absent/out-of-scope payment.

## Mock webhooks

Both routes are POST, HMAC-authenticated, and do not use JWT. Require `Content-Type: application/json`, `X-Paymesh-Timestamp` (decimal Unix epoch seconds), and `X-Paymesh-Signature` (hex HMAC-SHA256). Sign `timestamp + "." + exact raw UTF-8 body`; accepted timestamp skew is ±300 seconds. Secret configuration must be present and at least 32 characters. Body maximum is 65,536 bytes.

Body schema:

```json
{"eventId":"event-unique-1","paymentId":"UUID","gatewayTransactionId":"UUID","status":"SUCCESS","occurredAt":"2026-11-13T12:00:00Z"}
```

`eventId` is 1–255 nonblank characters; payment and gateway transaction IDs are UUIDs; status is SUCCESS, FAILED, TIMEOUT, or UNKNOWN; occurredAt is an ISO-8601 instant. The gateway identity and transaction ID must match the current attempt for an outcome to apply. Only PROCESSING payments can transition; terminal states are not reversed.

### `POST /api/v1/webhooks/mock-razorpay`

HMAC secret: `PAYMESH_RAZORPAY_WEBHOOK_SECRET`. Receipt fields: `id`, `eventId`, `status`, `attempts`, `detail`.

### `POST /api/v1/webhooks/mock-stripe`

HMAC secret: `PAYMESH_STRIPE_WEBHOOK_SECRET`. Same body/receipt contract as Razorpay.

For either route: receipt status RECEIVED or DEFERRED yields HTTP 202; terminal receipt states yield HTTP 200. Missing required headers/invalid payload returns 400; bad or expired signature returns 401; unconfigured secret returns 503; oversized body returns 413; same provider/event ID with changed raw body returns 409. Exact duplicate raw payload reuses the existing receipt and is not applied twice. Invalid signatures are rejected before inbox persistence.

## Settlement administration

Every route below requires the separate opaque `PAYMESH_SETTLEMENT_ADMIN_TOKEN` as `Authorization: Bearer <token>`. Do not use an application JWT. Missing/wrong token is 401; missing or shorter-than-32-character server configuration is 503. There is no request body for these operations. IDs in paths are UUIDs.

### `POST /api/v1/settlement/payments/{paymentId}/reconcile`

Run one bounded reconciliation operation using the local simulated gateway ledger only.

- Success: 200 report `{paymentId,status,attempts,nextAttemptAt}`. A known simulated outcome can resolve an eligible PROCESSING payment as RESOLVED; a CREATED payment is NOT_ELIGIBLE; terminal payment is SKIPPED; uncertain outcomes can return RETRY or EXHAUSTED.
- Errors: 401 invalid/missing settlement token; 404 payment absent; 503 settlement token configuration unavailable or infrastructure failure.
- Idempotency: repeated calls are bounded attempts under persisted payment/job state; they do not issue another payment.

### `GET /api/v1/settlement/payments/{paymentId}/reconciliation`

Return up to 100 audit rows for the payment ordered by attempt. Auth: settlement token. 200 array of database row maps (column set follows V7 `reconciliation_attempts`); 401 bad/missing token; 503 missing/short configured token. This is an audit read, not a merchant endpoint.

### `GET /api/v1/settlement/payments/{paymentId}/webhooks`

Return up to 100 webhook inbox event row maps for the payment, newest received first. Auth: settlement token. 200 array of database row maps (column set follows V7 `webhook_events`); 401 bad/missing token; 503 missing/short configured token.

### `POST /api/v1/settlement/webhooks/{id}/retry`

Manually retry a stored webhook event by inbox UUID; no body. Auth: settlement token. Returns a `WebhookInbox.Receipt`; 404 unknown event; 401 bad/missing token; 503 missing/short configured token. Retries obey persisted due time and bounded-attempt rules; they do not reset exhausted events.

## Safe request examples

Create a payment only in a deliberately chosen demo database, with an existing verified merchant and token stored in a shell variable:

```bash
curl --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_TOKEN") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: demo-payment-unique-001' \
  --data-binary '{"merchantId":"DEMO_MERCHANT_A","amount":200.00,"currency":"INR","customerId":"customer-unique-001","paymentMethod":"UPI"}'
```

Refund an existing successful payment:

```bash
curl --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_TOKEN") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments/PAYMENT_UUID/refund' \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: demo-refund-unique-001' \
  --data-binary '{"amount":200.00}'
```

These examples show request shape only; they were not executed during documentation finalization. Never repeat a state-changing example with a new key after an uncertain response until its result has been checked. For intentional idempotency testing, reuse the exact same key and request body.

## Related references

- [README-DEMO.md](README-DEMO.md): controlled demo setup and recovery runbook.
- [README-JWT.md](README-JWT.md): JWT configuration, validation, and rate limiting.
- [README-BUSINESS-SECURITY.md](README-BUSINESS-SECURITY.md): role and merchant ownership policies.
- [README-WEBHOOKS.md](README-WEBHOOKS.md): signature, deduplication, and reconciliation behavior.
- [README-REFUNDS.md](README-REFUNDS.md): refund concurrency and lifecycle details.
- [README-DEPLOY.md](README-DEPLOY.md): deployment constraints and isolated testing.

## Payment investigation (Phase 5.4)

`POST /api/v1/payments/{paymentId}/investigate` takes no body. Requires the existing
JWT with ADMIN or MERCHANT role. Merchants need an active membership in the
payment's active, verified merchant; admins may investigate across merchants.
Missing and inaccessible payments both return 404, before evidence reads or Python calls.

200 returns `{ "evidenceProvenance": { "source": "JAVA_AUTHORIZED_DATABASE_SNAPSHOT",
"collectedAt": "<UTC instant>", "unavailableEvidence": {}, "scope": "<trust-boundary explanation>" },
"investigation": <validated Python InvestigationResponse> }`.
The nested response is preserved, including actual `analysisMode`, `generationStatus`
and all limitations. The provenance envelope attests only to Java's authorized
collection, not external bank debit, settlement or refund arrival. Python's statement
that supplied input is unauthenticated remains true at its direct-input boundary;
it does not override the Java envelope. Arbitrary direct Python input has no Java provenance.

Money is sent internally as exact decimal strings. Collections contain at most 100
records each. Known empty histories are `[]`; an entire collection with unsupported
stored values is `null`, explained by `unavailableEvidence`. No partial collection
or partial financial total is sent. Evidence exceeding the collection, amount,
consistency or 131072-byte request limits returns 422. A malformed stored webhook
payload causes a sanitized evidence-unavailable error, not a synthetic investigation.

Errors use `ApiErrorResponse`: 401 invalid/missing authentication; 403 role denied;
404 missing/inaccessible payment; 422 unsupported or excessive evidence; 502 upstream
failure, timeout, invalid/oversized/mismatched response or non-2xx; 503 disabled,
busy or unavailable database evidence. No upstream body or exception details are returned.
The feature defaults disabled. One concurrent investigation is admitted per Java
process with no queue or automatic retries. The database snapshot is released before
HTTP. Internal Python must remain bound to `127.0.0.1:8000`.

Configuration: `PAYMESH_AI_ENABLED=false`, `PAYMESH_AI_BASE_URL=http://127.0.0.1:8000`,
`PAYMESH_AI_CONNECT_TIMEOUT_MS=2000`, `PAYMESH_AI_RESPONSE_TIMEOUT_MS=45000`,
`PAYMESH_AI_MAX_RESPONSE_BYTES=262144`. The origin must be literal IPv4 loopback
with no credentials, path, query or fragment. Proxy use and redirects are disabled.
See [Phase 5.4 report](PHASE-5.4-JAVA-PYTHON-INTEGRATION-REPORT.md) for guarded restart
and authenticated verification commands against the existing port-5432 demo.

## Phase 6.7.2 — public merchant registration (requires V9 activation)

`POST /api/v1/auth/register`, JSON, public, bounded 16 KiB, no Idempotency-Key. Shares the bounded login rate budget (429/Retry-After). Fields: firstName (nonblank/max80), lastName (80), businessName (160), email (ASCII normalized lowercase, max254, unique), mobile (optional + then 7–15 digits), businessType (SOLE_PROPRIETOR/COMPANY/PARTNERSHIP/NONPROFIT/OTHER), country (IN/US/GB/CA/AU/OTHER), password, confirmPassword, terms=true. Password policy matches existing accounts: >=12 Unicode code points and <=72 UTF-8 bytes, no NUL or malformed Unicode. No email verification/OTP.

201: `{"accountStatus":"PENDING_APPROVAL","message":"Your account has been created successfully. You can now sign in using your email and password."}`. No password/hash/token in registration response. 400 validation, 409 duplicate/conflict, 413 oversized, 415 unsupported media, 429 request budget. User, generated merchant, inactive membership, MERCHANT role and profile/terms persistence are transactional. Client input cannot choose merchant ID, role or approval state. Historical accounts default ACTIVE; existing business records are unchanged.

Login remains `POST /api/v1/auth/login` using `{login,password}`. Registered email is the login. JWT now carries `account_status`; pending accounts authenticate but receive no financial Spring authorities and BusinessAccess independently blocks them. Status must match current persisted state. Existing tokens missing the claim are accepted only for ACTIVE users. No approval/listing/profile/refresh-token API was added. Activation/manual checks and limitations: `frontend/PHASE-6.7.2-MERCHANT-SIGNUP-REPORT.md`.

## Phase 6.7.3 — server sessions and gated local-demo recovery (V10, not live-activated)

Login retains its existing envelope and optional `rememberMe=false`. Browser requests require the configured exact Origin and `X-PayMesh-CSRF: 1`; browser login creates a session and sets HttpOnly `pm_refresh`, SameSite Strict, Path `/api/v1/auth`, Secure by default. Non-browser Origin-less login stays JWT-only for compatibility. Access lifetime remains 900 seconds; new session-bound JWTs add `sid` and validate current revocation/expiry/account version/status/roles. Old sid-less JWTs keep existing version/role/status validation.

- `POST /api/v1/auth/refresh`: cookie only, no body/idempotency key; rotates credential; 200 existing access-token envelope, 401 missing/expired/replayed/revoked credential, 403 Origin/CSRF denial, 429 bounded auth budget. Replay revokes family.
- `POST /api/v1/auth/logout`: idempotent current-family revocation and cookie deletion; 200/403/429.
- `POST /api/v1/auth/logout-all`: valid current refresh cookie required; revokes all families and increments account authorization_version; 200/401/403/429.
- `GET /api/v1/auth/password/capabilities`: `{localDemoEnabled:false}` by default, no-store.
- `POST /api/v1/auth/password/forgot`: `{identity,portal}` → `{challengeId,otp,expiresAt,resendAfterSeconds:60}` only for explicitly eligible, single-role disposable accounts in verified local demo. Unknown/ineligible: same envelope with otp=null. No email/SMS is sent.
- `POST /api/v1/auth/password/verify-otp`: `{challengeId,portal,otp}` → `{resetAuthorization,expiresIn:300}` on one-time success. 400 invalid/expired/exhausted, 404 feature unavailable, 429 budget/cooldown.
- `POST /api/v1/auth/password/reset`: `{challengeId,portal,resetAuthorization,password,confirmPassword}` → fixed success message. Single-use grant; existing policy/BCrypt; atomic password/version/session/grant revocation and honest unauthenticated-source audit. 400 invalid/expired/policy, 403 request-boundary denial, 404 disabled, 429 budget.

All new sensitive responses are no-store. Recovery is deliberately insecure ownership UX: displaying a code to its requester proves nothing. It is disabled by default, disallowed outside the verified loopback-only demo and requires a private key and empty-by-default operator eligibility table. No recovery eligibility seeds, public admin approval, migration activation or live reset was performed. Details: `frontend/PHASE-6.7.3-SESSIONS-PASSWORD-RECOVERY-REPORT.md`.

## Additional administrator provisioning (Phase 6.7.3 blocker resolution)

`POST /api/v1/admin/accounts` is a narrow **Bearer JWT** administrative endpoint, not public signup. It is intentionally absent from the frontend proxy allowlist and public UI. Existing verified JWT/account/session checks require a currently enabled ACTIVE ADMIN; the account administration transaction rechecks current authorization version and role under its existing lock.

Request: JSON object containing exactly `login`, `password`, `confirmPassword`. Password/confirmation must match and meet AccountPasswords policy (12 Unicode code points minimum, 72 UTF-8 bytes maximum, no NUL/malformed Unicode). Login uses existing strip/lowercase ASCII normalization. Unknown fields, including roles/authority/status, duplicate keys and trailing JSON are rejected. Maximum request body: 4096 bytes, including chunked requests.

Success: HTTP201, no-store; `{userId,login,enabled:true,accountStatus:"ACTIVE",roles:["ADMIN"]}`. No password/hash is returned. A successful ACCOUNT_CREATED audit records the actual authenticated administrator and is atomic with account/role creation. No merchant, membership or recovery eligibility is created.

Errors: 400 malformed/mismatched/password-policy input; 401 missing/invalid/expired/revoked JWT; 403 valid non-Admin/pending authority or changed transactional authorization; 409 invalid normalized login or duplicate account (existing service intentionally conflates those cases); 413 oversized body; 415 unsupported media type; 503 safe unconfirmed failure, including required audit failure. Do not automatically retry an uncertain creation; inspect the authorized account state first. GET/other unmatched methods remain denied. Cookie-only authentication is insufficient. There is no new migration or public Admin registration page.

## Phase681 analytics and account identity metadata (redeployment pending)

GET `/api/v1/merchant/analytics`: ACTIVE verified MERCHANT-only single membership,
server-derived ownership. GET `/api/v1/admin/analytics`: current ACTIVE ADMIN;
optional exact merchantId. Both accept optional currency=INR|USD and paired UTC-midnight
from/to instants (start inclusive,end exclusive,1–93 days,no future end beyond tomorrow
UTC). Default:last30 calendar UTC days including today. Unknown/duplicate params fail.
No migration; no financial writes. Responses contain range,paymentCounts,refundCounts,
paymentMethods,amountComparison and zero-filled dailyPayments, all currency-separated;
Admin also returns global current merchantCounts. Monetary fields are exact decimal
strings; daily volume is creation counts, not settlement. Full field shapes and safe
browser semantics are in frontend/PHASE-6.8.1-MERCHANT-DASHBOARD-PROFILE-REPORT.md.
Existing dashboard record filters are independent of analytics' UTC-day filters.

Login/refresh responses additionally include own normalized `login` display metadata.
Existing accessToken/tokenType/expiresIn/expiresAt and JWT/HttpOnly-cookie/security
contracts remain; no refresh secret is exposed. Old responses without login remain
accepted by the frontend. Switch Account calls existing secure current-session logout;
shared cookies across normal tabs are intentional, not per-tab authentication.

## Phase682 Merchant Payment Links (V12; not activated live)

Current enabled ACTIVE exact-MERCHANT JWT/session, single active membership and
verified/active registry/V11 business lifecycle required. Owner derived server-side.
All responses no-store. Amounts returned as exact decimal strings.

| Method | Path | Contract |
| --- | --- | --- |
| POST | /api/v1/merchant/payment-links | Required Idempotency-Key; amount, currency, paymentMethod, customerReference, description, expiryHours(1/24/168);201 new/200 exact replay/409 conflict |
| GET | /api/v1/merchant/payment-links | page0–10000,size1–50(default5),search,status,currency; items/page/size/total; token omitted |
| GET | /api/v1/merchant/payment-links/{linkId} | Owned canonical UUID; detail including relative checkoutPath;404 missing/unowned |
| POST | /api/v1/merchant/payment-links/{linkId}/cancel | No body;200 cancelled;409 repeated/expired/ineligible |

Only INR+UPI/CARD→MOCK_RAZORPAY and USD+CARD→MOCK_STRIPE.
No client ownership/gateway/status/payment association/URL fields accepted.
No public checkout API or payment execution exists in this phase. Full schemas,
status/errors and recovery limits: `frontend/PHASE-6.8.2-PAYMENT-LINKS-REPORT.md`.

## Phase683 public customer checkout (V12/V13 pending live activation)

Exact capability-scoped routes, never a Merchant/Admin session substitute:

| Method | Endpoint | Contract |
| --- | --- | --- |
| GET | /api/v1/checkout/{token} | Customer-safe read-only order/status snapshot |
| GET | /api/v1/checkout/{token}/status | Safe current status/receipt; no gateway/reconciliation |
| POST | /api/v1/checkout/{token}/pay | Idempotency-Key + confirmed:true; strict Origin/header/body;200 resolved/202 unresolved |

Token exactly43 base64url characters. No query/body on GET. POST JSON fields only
`confirmed:true` and optional `simulationOutcome:SUCCESS|FAILED|TIMEOUT` when the independently
verified private demo gate is enabled. Default chooser absent; normal profiles reject choices.
Amount/currency/Merchant/method/gateway/customer identity derive only from stored link/server.
Same intent replay reads existing state, never re-executes gateway; new key only after definitive
FAILED and still eligible, maximum5 attempts/link. Unresolved attempts block cancel/replacement.
No public arbitrary payment/refund/AI/history/Admin API. No cookies/JWT used for authority.

Response: merchantName/orderReference/description/amount(decimal string)/currency/paymentMethod/
expiresAt/checkoutStatus/canPay/simulationChoices/simulationNotice/attemptReference/attemptStatus/
paymentStatus/receiptReference/paidAt. No private Merchant/user/payment UUID/contact/audit/errors.
Receipt reference is opaque attempt UUID; it grants no independent lookup authority.
Statuses ACTIVE/FAILED/PROCESSING/UNCERTAIN/PAID/CANCELLED/EXPIRED/UNAVAILABLE. Errors are safe
400/403/404/409/413/415/429/503. Public POST requires exact configured Origin and
X-PayMesh-Checkout:1; body<=4096. Full schemas/limits and transaction/recovery design:
`frontend/PHASE-6.8.3-CUSTOMER-CHECKOUT-REPORT.md`.

Merchant link projection now supports PROCESSING and checkoutAttemptStatus/failedAttemptCount.
Successful paymentId is available only through the existing owned Merchant link response;
private payment/refund/AI authorization remains mandatory. No link-as-payment double counting.


## Phase 6.9.2 — authorized read-only AI chat

`POST /api/v1/merchant/ai/chat`, `POST /api/v1/admin/ai/chat`,
`POST /api/v1/payments/{paymentId}/ai/chat`: bearer JWT, JSON, no query or
idempotency header. Input `{ "question": "What is the current payment status?",
"history": [] }`; optional explicit `context` supports `paymentId` OR `paymentLinkId`,
Admin-only `merchantId`, and `statistics: {from,to,currency}`. Payment path supplies the
payment selector. Unknown/duplicate fields rejected; question1000/history8+6000 characters,
body32KiB. No caller evidence/identity/role. No financial action or automatic retry.
Response contains server correlationId, approved answer/intent, dated evidenceProvenance,
authorized evidenceReferences, known knowledgeReferences, limitations/suggestedFollowUps,
exact string moneyFacts, analysisMode/generationStatus.
400 input,401 current auth,403 role/lifecycle,404 inaccessible context,413 size,415 media,
422 evidence limits/inconsistency,502 unverifiable/upstream response,503 unavailable/busy,
504 timeout. All responses no-store. Current authorization rechecked after private inference.
See `../frontend/PHASE-6.9.2-SECURE-AI-CHAT-API-REPORT.md` for full schema/examples,
protected disabled-by-default service authentication and Phase693 integration instructions.
