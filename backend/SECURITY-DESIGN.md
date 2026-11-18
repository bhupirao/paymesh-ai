# Proposed Security Architecture

**Status: proposed; awaiting architecture approval. Documentation only.**

This document records the proposed authentication, authorization, and merchant
isolation policy for PayMesh AI. It does not authorize implementation or database
changes. Java code, dependencies, application configuration, and migrations must
remain unchanged until implementation is explicitly approved.

## 1. Scope and existing controls

The audited application uses Spring Boot 3.5.7, Java 21, PostgreSQL, and Flyway
migrations V1–V7. The proposed security work must preserve payment lifecycle
validation, gateway routing, simulated provider behavior, idempotency, partial
refund limits, row locking, webhook auditing, and bounded reconciliation retries.

Current authentication is limited to:

- Provider-specific timestamped HMAC-SHA256 verification for mock webhooks.
- An environment-configured static bearer token for settlement administration,
  checked using constant-time comparison.

Payment, processing, refund, and gateway-history endpoints currently lack user
authentication and merchant ownership checks. No user accounts, password encoder,
JWT validation, roles, memberships, or Spring Security filter chains exist.

The POM has no Spring Security dependencies. Boot 3.5.7 manages Spring Security
6.5.6, compatible with the project's Java 21 runtime. Proposed dependencies are
`spring-boot-starter-security`, `spring-boot-starter-oauth2-resource-server`, and
test-scoped `spring-security-test`, with versions managed by the Boot BOM.
Do not independently introduce Spring Security 7 into this Boot 3.5 design.

## 2. Complete existing endpoint and role matrix

Definitions:

- **Owner:** an active MERCHANT membership matches the payment's stored
  `merchantId`, and the account and merchant are eligible for access.
- **ADMIN:** an authenticated application administrator with explicit,
  audited cross-merchant permission.
- **Settlement authority:** a dedicated authority derived only from successful
  validation of the existing settlement credential. It is not a general ADMIN
  account and does not authorize other application APIs.
- **Valid JWT:** signature, permitted algorithm, issuer, audience, time claims,
  account status, authorization version, and required claim structure pass
  validation. Roles and memberships are server-controlled.

| HTTP method | Existing URL | Required authentication | Required role/authority | Merchant ownership validation | Expected 401, 403, and 404 behavior |
|---|---|---|---|---|---|
| GET | `/api/v1/payments/health` | None | None | None | No authentication-related 401/403; no resource lookup |
| POST | `/api/v1/payments` | Valid JWT | MERCHANT or ADMIN | MERCHANT body merchantId must match active membership; ADMIN target must be an explicitly selected verified, active merchant | 401 missing/invalid JWT; 403 wrong role, inactive membership, or merchant mismatch; 404 unknown target merchant for ADMIN |
| GET | `/api/v1/payments/{paymentId}` | Valid JWT | MERCHANT or ADMIN | Owner required for MERCHANT; explicit ADMIN authorization | 401 missing/invalid JWT; 403 insufficient role; 404 absent payment or payment outside merchant scope |
| POST | `/api/v1/payments/{paymentId}/process` | Valid JWT | MERCHANT or ADMIN | Ownership checked before atomic processing claim or gateway call | 401 missing/invalid JWT; 403 insufficient role; 404 absent payment or payment outside merchant scope |
| GET | `/api/v1/payments/{paymentId}/gateway-transactions` | Valid JWT | MERCHANT or ADMIN | Authorize through parent payment before querying attempts | 401 missing/invalid JWT; 403 insufficient role; 404 absent/out-of-scope parent; authorized payment with no attempts returns 200 and [] |
| POST | `/api/v1/payments/{paymentId}/refund` | Valid JWT | MERCHANT or ADMIN | Authorize under payment row lock before idempotency replay, balance checks, or insertion | 401 missing/invalid JWT; 403 insufficient role; 404 absent payment or payment outside merchant scope |
| GET | `/api/v1/payments/{paymentId}/refund` | Valid JWT | MERCHANT or ADMIN | Authorize parent before retrieving latest refund | 401 missing/invalid JWT; 403 insufficient role; 404 absent/out-of-scope payment or no refund |
| GET | `/api/v1/payments/{paymentId}/refunds` | Valid JWT | MERCHANT or ADMIN | Authorize through parent payment | 401 missing/invalid JWT; 403 insufficient role; 404 absent/out-of-scope payment; authorized payment with no refunds returns 200 and [] |
| POST | `/api/v1/webhooks/mock-razorpay` | Existing Mock Razorpay HMAC and timestamp | No user role | Preserve provider, payment, and transaction correlation; no merchant JWT | 401 invalid HMAC/timestamp; 403 not used for user roles; unknown payments preserve existing deferred processing rather than resource-existence 404 |
| POST | `/api/v1/webhooks/mock-stripe` | Existing Mock Stripe HMAC and timestamp | No user role | Same correlation policy, using Stripe-specific secret | 401 invalid HMAC/timestamp; 403 not used for user roles; unknown payments preserve existing deferred processing rather than resource-existence 404 |
| POST | `/api/v1/settlement/payments/{paymentId}/reconcile` | Existing settlement admin bearer token | Dedicated settlement authority | Existing credential authorizes cross-merchant operations | 401 missing/incorrect credential; 403 not used for valid-token holders; 404 nonexistent payment |
| GET | `/api/v1/settlement/payments/{paymentId}/reconciliation` | Existing settlement admin bearer token | Dedicated settlement authority | Existing credential authorizes cross-merchant audit access | 401 missing/incorrect credential; 403 not used for valid-token holders; preserve 200 and [] when no audit rows exist, including unknown payment IDs |
| GET | `/api/v1/settlement/payments/{paymentId}/webhooks` | Existing settlement admin bearer token | Dedicated settlement authority | Existing credential authorizes cross-merchant access to sensitive event payloads | 401 missing/incorrect credential; 403 not used for valid-token holders; preserve 200 and [] when no event rows exist, including unknown payment IDs |
| POST | `/api/v1/settlement/webhooks/{id}/retry` | Existing settlement admin bearer token | Dedicated settlement authority | Existing credential authorizes inbox-event operational access | 401 missing/incorrect credential; 403 not used for valid-token holders; 404 nonexistent inbox event |
| GET | `/actuator/health` | None for minimal health | None | None | No authentication-related 401/403; detailed health must not be public |
| GET | `/actuator/info` | Valid JWT | ADMIN | None | 401 missing/invalid JWT; 403 non-ADMIN |
| GET | `/actuator` | Valid JWT | ADMIN | None | 401 missing/invalid JWT; 403 non-ADMIN |

Actuator URLs are framework-provided. Configuration currently exposes health and
info; other Actuator endpoints are not exposed and must not be enabled implicitly.
Unknown or unapproved routes are denied by default, with no business operation.
Do not disclose resource existence through differing authorization responses.

General response policy:

- Authenticate before resource lookup. Missing/invalid credentials return 401.
- A valid JWT with an insufficient role returns 403.
- A valid MERCHANT account querying another merchant's resource receives the same
  404 as an unknown resource, without revealing status, balance, or replay data.
- An inactive membership fails authorization; resource-scoped denials use 404 to
  conceal existence, while creation membership/mismatch failures use 403.
- Invalid UUIDs and malformed request bodies remain 400 after applicable security
  checks. Authorized lifecycle conflicts and excessive refunds remain 409.
- Missing or inadequate webhook/settlement secret configuration continues to
  fail closed with 503.
- Returning 401 for a missing settlement Authorization header is an intentional
  proposed consistency change: current required-header binding returns 400.

## 3. ADMIN and MERCHANT authorization rules

MERCHANT access requires an enabled account and an active verified membership.
The client cannot establish ownership through a request body or unsigned claim.
For the initial design, merchant context is resolved from the authenticated
identity and verified membership for the target merchant; the system must not
implicitly select an arbitrary merchant when multiple memberships exist.

ADMIN may use the explicitly listed business endpoints across merchants. This
permission is checked deliberately rather than arising from a skipped ownership
condition. Creation requires an existing verified, active target merchant.
An existing but unverified/inactive creation target returns 403, not an implicit
registry insertion. Administrative access to historical records does not claim
them on behalf of any merchant user.

ADMIN authorization does not waive payment-state validation, refund amount limits,
idempotency, gateway routing, concurrency controls, or fully-refunded protection.
Cross-merchant administrative actions record actor, target merchant/resource,
operation, outcome, and timestamp without recording credentials or raw tokens.

The settlement credential grants only settlement operations. ADMIN JWTs are not
accepted as substitutes for that credential. MERCHANT JWTs cannot access account
administration or settlement operations.

## 4. Merchant ownership enforcement

Existing merchant identifiers are text values in payments and idempotency records.
They participate in payment request hashing and advisory-lock scope. Refunds,
gateway attempts, and reconciliation records inherit ownership through payments.
UUID unpredictability and idempotency keys are not access controls.

Enforce ownership at the service/database boundary, not only in controllers:

1. Resolve the authenticated account and current roles/memberships from trusted
   server-side data.
2. Retain PaymentRequest.merchantId for compatibility, but reject mismatches for
   MERCHANT callers. Do not silently substitute a different merchant or alter
   existing canonical payment hashes.
3. Scope payment reads by payment ID and authorized merchant. Include merchant
   scope in processing claims so authorization precedes any state mutation.
4. Lock the payment for refunds, authorize ownership, then perform idempotency
   lookup and remaining-balance validation. Retain READ COMMITTED behavior and
   the existing lock protocol.
5. Authorize the parent payment before returning refund or gateway history.
6. Check ownership before returning existing idempotent payment/refund results.
7. Keep merchant-facing operations separate from internal webhook, reconciliation,
   and scheduled-worker operations. Do not fabricate a merchant principal or add
   a publicly selectable bypass flag for background work.

Denied requests must produce no claims, gateway calls, refunds, or business audit
mutations. Dedicated security-denial auditing may record the denied attempt.
Do not allow merchant callers to reach unrestricted internal service entry points.

## 5. Account provisioning and JWT lifecycle

### Provisioning

No public registration is proposed for the initial release.

| Account or identity | Proposed provisioning |
|---|---|
| Initial ADMIN | Controlled offline procedure with secret input and BCrypt hashing; no migration-seeded credential |
| Additional ADMIN | Approved, audited action by an existing ADMIN |
| MERCHANT user | ADMIN provisions or invites the user and assigns verified membership |
| Existing merchant ownership | Business verification before linking an account to an existing merchant identifier |
| Account recovery | Time-limited, single-use recovery token; never disclose a password |

Clients cannot self-select roles, privileges, or ownership of an existing merchant
identifier. One merchant may have multiple staff accounts. Disabling an account
or membership must not delete financial history. Restrict creation or removal of
privileged accounts so operational administrators cannot accidentally eliminate
all active administrator access.

Passwords use Spring PasswordEncoder with BCrypt and a measured work factor.
Store only encoded hashes, enforce supported password input limits without silent
truncation, and avoid password/hash exposure in DTOs, logs, or audit records.
No production secret or bootstrap password belongs in source, SQL, or examples.

### Authentication and access tokens

Proposed new endpoints, subject to approval:

- POST `/api/v1/auth/login`: credentials authenticate an enabled account; return
  an access token. No pre-existing JWT is required. Invalid credentials use a
  generic 401 response; malformed input uses 400. Apply rate limiting and return
  429 when the configured limit is exceeded.
- Account/merchant provisioning APIs, if approved, require ADMIN JWTs. Their
  exact URLs and DTOs must be specified before implementation.
- Refresh/recovery endpoints are a separate scope decision, not existing routes.

Use Spring's authentication manager for password verification and its OAuth2
resource-server JWT decoder for access-token validation. Token issuance is an
explicit authentication-service responsibility; resource-server configuration
alone does not implement login or token issuance.

Access tokens should initially last approximately 10–15 minutes. Prefer asymmetric
signing keys held in secret storage with environment-referenced configuration.
Signing keys are independent of provider HMAC secrets and the settlement token.
Allow only approved algorithms and support planned key rotation.

JWT validation includes signature, issuer, audience, expiration, not-before,
required claim types, enabled account status, and current authorization version.
Claims include immutable user ID in sub, server-issued roles, token ID, issue/time
claims, and authorization version. Do not use a mutable username as the ownership
identity or trust a merchant claim without current membership validation.

Account disablement, password reset, and role/membership revocation must invalidate
the relevant authorization state. Increment authorization version as appropriate
and check current account/membership data on protected requests. HTTP sessions
remain stateless even when authorization performs database checks.

There is no refresh token in the minimum initial scope. If approved later, use
rotating opaque refresh tokens stored only as hashes, with expiry, revocation,
reuse detection, and explicit logout behavior. Without refresh tokens, clients
reauthenticate after access-token expiry; deleting a client token is not server
revocation of an otherwise valid JWT.

## 6. Existing payment ownership and data preservation

Existing payments are not reassigned or rewritten. Their stored merchantId remains
the ownership identifier. Historical refunds and gateway attempts remain attached
to the same payment IDs.

Create merchant registry entries from the union of distinct merchant identifiers
in payments and idempotency records. Preserve exact strings, including case and
whitespace. Do not conflate identifiers by normalizing or trimming them.
Historical entries begin unclaimed/unverified; existence in the registry is not
proof that an account owns them.

After business verification, an ADMIN assigns an active membership to the existing
identifier. This grants access to its historical payments without changing them.
A new account supplying a matching merchant name or string never establishes
ownership automatically. Unclaimed data stays preserved and inaccessible to
MERCHANT users; explicitly authorized ADMIN access remains available.

Preserve payment/refund amounts, statuses, timestamps, versions, UUIDs, request
hashes, idempotency keys, gateway attempts, webhook payloads, and reconciliation
history. Never truncate, drop, reset, or reseed financial tables.

## 7. Settlement token and webhook HMAC compatibility

Use explicit, ordered SecurityFilterChain configurations:

| Area | Security behavior |
|---|---|
| Mock webhook paths | No JWT filter; preserve mandatory provider HMAC checks and raw request bytes |
| Settlement paths | Existing static bearer validation; dedicated settlement authority; retain controller credential check |
| Business/application paths | Stateless JWT authentication, role authorization, and service-level merchant isolation |
| Login and minimal health | Narrow explicit exceptions; no broad public API wildcard |
| Unmatched paths | Deny by default |

Disable generated form login and HTTP Basic fallback. Return JSON authentication
and access-denied responses through security exception handlers. Configure CORS
only for approved origins/methods/headers; preflight handling must not expose
business operations. Disable CSRF only where authentication remains header-based
and independent of ambient cookies. Reassess CSRF if cookies are introduced.

### Existing settlement credential

Keep the current Authorization bearer protocol and environment configuration.
Never pass this opaque token to the JWT decoder. Never implement ADMIN JWT OR
settlement-token authentication, and never let the token grant general ADMIN
privileges. Missing/short configuration remains 503 and incorrect credentials
remain 401. Retain constant-time verification and the controller check during
initial integration.

Requiring both JWT and the settlement token is not part of this initial design.
Any future dual-credential requirement needs approved protocol/header changes,
because both cannot occupy the same Authorization bearer header. Existing
settlement automation must continue to use its current credential.

### Unchanged mock webhook verification

Preserve provider-specific environment secrets, the existing raw-byte signing
input `timestamp + "." + raw_body`, HMAC-SHA256, constant-time comparison, and the
five-minute delivery timestamp window. Do not consume, normalize, or reserialize
the body in a security filter before verification.

A valid JWT never replaces a missing/invalid HMAC. A valid HMAC never authorizes
merchant APIs. Preserve event uniqueness, payload-conflict detection, transaction
correlation, deferred unknown payments, retry budgets, receipt statuses, and the
rule that a REFUNDED payment cannot be changed back to SUCCESS.

The endpoints remain mock-specific simulations, not live Razorpay/Stripe protocols.
No real gateway integration or routing change is proposed.

## 8. Proposed V8 database migration

Tentative filename: `V8__authentication_and_merchant_memberships.sql`.
This is a plan only; no migration file is to be created before approval.

| New table | Proposed fields and constraints |
|---|---|
| app_users | UUID primary key; unique normalized login; sufficiently sized password_hash; enabled/account state; authorization_version; creation/update timestamps |
| roles | Restricted application role names ADMIN and MERCHANT |
| user_roles | User/role foreign keys and unique assignment constraint |
| merchants | Exact existing merchant_id text primary/unique identifier, compatible with existing VARCHAR(100); verification/activation state; timestamps |
| merchant_memberships | User/merchant foreign keys; active state; unique user/merchant association; provisioning audit metadata |
| security_audit_events | Actor identity, operation, target merchant/resource, outcome, timestamp, correlation metadata; no credentials or raw tokens |

V8 is additive: create new tables/indexes and insert registry entries derived from
existing identifiers. Do not alter historical business rows or edit V1–V7. Role
names may be seeded as non-secret reference data; user credentials and privileged
accounts may not be seeded.

Use explicit uniqueness constraints, membership foreign keys, and lookup indexes.
Do not configure cascading deletion into payments/refunds/gateway/audit history.
Audit rows must survive account disablement and account lifecycle operations.

Foreign keys on existing payments/idempotency tables are not required for initial
authorization. If later approved, first inventory consistency, then add and validate
them in a subsequent migration without changing historical ownership strings.
Refresh-token persistence is also deferred unless explicitly approved.

Before release, test V7-to-V8 upgrades with representative historical payments,
partial/full refunds, idempotency records, gateway attempts, webhook events, and
reconciliation records. Verify all original values and V1–V7 checksums remain
unchanged, registry backfill is complete, and no membership is auto-granted.

## 9. Implementation phases and regression tests

Implementation is gated on approval of this document and explicit authorization
to proceed. Suggested phases:

1. Approve endpoint/role policy, ADMIN scope, provisioning, identity verification,
   token lifetime, and whether refresh/recovery flows are included.
2. Add migration-preservation and authorization acceptance tests; design additive
   V8 tables and constraints without changing existing financial data.
3. Implement controlled account provisioning, BCrypt verification, merchant
   verification, membership assignment, and security auditing.
4. Add approved Spring Security dependencies, login/token issuance, JWT validation,
   account-state checks, key configuration, and JSON error handling.
5. Configure separate webhook, settlement, and application security chains; preserve
   both existing credential protocols before protecting business endpoints.
6. Add transactional merchant isolation for creation, reads, processing claims,
   refunds, histories, and idempotent replay. Keep locks and lifecycle semantics.
7. Update existing business tests/clients to authenticate with correct merchant
   identities. Do not disable all filters or use ADMIN for every scenario.
8. Run the complete suite only against a verified isolated PostgreSQL instance.
9. Provision verified production identities and update client documentation before
   enforcement. Do not introduce a public compatibility bypass mode.

Required regression and acceptance coverage:

- Valid/invalid BCrypt credentials; password limits; disabled accounts; generic
  authentication failures; provisioning privilege restrictions and audit records.
- Missing, malformed, expired, tampered, wrong-issuer, wrong-audience, unsupported-
  algorithm, and structurally invalid JWTs; authorization-version invalidation.
- MERCHANT versus ADMIN permissions; revoked memberships; spoofed roles and
  merchant claims; ADMIN cross-merchant actions explicitly audited.
- Merchant A denied every payment/refund/gateway-history operation on merchant B,
  with no existence, status, balance, or replay-response disclosure.
- Rejected ownership before atomic claims, idempotency replay, gateway calls,
  refund insertion, or financial audit mutation.
- Identical idempotency keys remain independent across legitimate merchant scopes;
  existing request hashes and retry semantics remain unchanged.
- Valid HMAC requests work without JWT; invalid HMAC fails even with an ADMIN JWT;
  exact raw bytes, delivery timestamps, duplicate handling, and retry rules persist.
- Existing settlement token works without JWT; ADMIN/MERCHANT JWT-only access is
  rejected; wrong/missing settlement credential and missing configuration fail
  closed; settlement token cannot access other protected APIs.
- Existing lifecycle validation, currency routing, payment claims, optimistic
  locking, gateway exception handling, partial refunds, remaining-balance limits,
  duplicate refunds, and concurrent over-refund prevention remain intact.
- Webhook/reconciliation concurrency and rollback, bounded retries, exhaustion,
  immutable terminal states, and fully-refunded protection remain intact.
- V7-to-V8 upgrades preserve original business/audit rows, identifiers, ownership
  strings, hashes, and migration checksums; historical merchant IDs remain
  unclaimed until verified; no seeded production credentials.
- Security failures are JSON 401/403/404 as specified, rather than form redirects;
  health, CORS, and CSRF behavior match the selected credential transport.

Use `bash scripts/test-isolated.sh` for integration verification. Preserve the
existing pre-Flyway isolation guard. The script creates and verifies a fresh test
cluster/database on a non-5432 port and stops it afterward; it does not reset an
existing database. Never run bare `mvn clean test` against the application database
or weaken the guard to make tests pass.

## 10. Compatibility and approval gate

Payment/refund clients and existing unauthenticated MockMvc requests will require
JWTs. Preserve request/response shapes and business status codes where possible;
authentication and ownership failures intentionally introduce the matrix's
401/403/404 outcomes. Provisioning and client rollout must precede enforcement.

Webhook senders and settlement automation keep their current signing/token
protocols. Internal scheduled jobs remain independent of HTTP user identity.
Authorization must not widen transaction boundaries around gateway calls or remove
existing row-locking/idempotency protections.

This document contains no secret values and authorizes no code, dependency,
configuration, migration, or database changes. Implementation remains pending
explicit architecture approval and a subsequent instruction to proceed.
