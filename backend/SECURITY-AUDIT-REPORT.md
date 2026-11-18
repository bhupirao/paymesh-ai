# Phase 3A and Phase 3B security audit report

Report date: 2026-11-11

Project root: `/Users/bhupirao/Developer/paymesh-ai/backend`

## Scope and review limitations

This report records the completed static review of JWT authentication (Phase 3A)
and business authorization (Phase 3B), including `README-BUSINESS-SECURITY.md`,
security filter chains, controllers, account and membership services, financial
service facades and internal implementations, scoped repository queries, webhook
verification, settlement authentication, and relevant test source code.

The audit did not modify code or database records, create accounts, run migrations,
or execute tests. This document is the only file created by the report-saving task.
The application database was not accessed. Static review does not establish the
absence of vulnerabilities or verify deployment configuration.

The two displayed warning messages mentioned in the review request were not
available in the conversation or supplied as text. Their exact wording, origin,
severity and diagnoses remain unverified. The findings below are independently
supported by the inspected source; they must not be treated as resolutions of
those two warnings. Obtain their exact text and source locations for follow-up.

## Severity summary

| Severity | Findings | Assessment |
|---|---:|---|
| Critical | 0 | None identified in the reviewed code paths |
| High | 0 | None identified in the reviewed code paths |
| Medium | 2 | Internal worker boundary enforcement; actual request-body limits |
| Low | 3 | Auth namespace default policy; audit documentation; infrastructure error classification |

No current HTTP authorization bypass or cross-merchant data exposure was
identified. The internal-worker finding describes a structural bypass risk from
future or incorrectly wired application code, rather than an identified remotely
reachable bypass in the current controllers.

## Findings and recommended fixes, in priority order

### 1. Medium: trusted internal worker boundaries rely on convention

Affected files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/internal/InternalRefundService.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/internal/InternalPaymentService.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/internal/InternalGatewayTransactionService.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/impl/FinancialRefundOperations.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/impl/FinancialPaymentOperations.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/impl/FinancialGatewayTransactionOperations.java`

The internal interfaces extend ordinary business service interfaces, and their
public Spring implementations perform financial operations without merchant
authorization or ADMIN business-access auditing. This is deliberate for trusted
processing, but isolation currently depends on correct wiring and developer
discipline. `@Primary` selects the secured facade for ordinary injection; it does
not prevent explicit injection of an unrestricted internal bean.

Current HTTP controllers use secured services, and orchestration authorizes its
processing claim before calling internal operations. No current HTTP path to
these unrestricted operations was identified.

Recommended fix: introduce narrower internal worker capabilities rather than
inheriting the complete public business interface. Restrict access through
package/module boundaries where practical, and add architecture tests enforcing
which components may depend on internal services, implementations and unrestricted
repositories. Preserve trusted webhook/reconciliation execution without public
bypass flags or fabricated merchant principals.

Timing: address before adding new business entry points or expanding internal
service consumers in the next phase.

### 2. Medium: request-size checks do not bound actual body consumption

Affected files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/LoginRateLimitFilter.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/WebhookController.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/WebhookIngress.java`

The login filter checks declared `Content-Length` against 4096 bytes. A chunked
request with unknown content length can proceed to JSON deserialization without
that limit bounding the bytes actually read. The existing webhook 65536-byte
check runs after Spring has materialized the request as a byte array. Neither
check alone prevents oversized request allocation. The webhook issue is an
existing intake limitation, not an identified Phase 3B HMAC regression.

This creates resource-exhaustion exposure unless a verified upstream limit already
provides the missing protection. Per-client request-count limiting does not bound
the size of a single request. Deployment ingress configuration was not verified.

Recommended fix: enforce limits while reading actual request bytes, including
chunked requests, and configure matching ingress limits. Reject excess bodies
with 413 before unbounded deserialization/materialization. Preserve the exact raw
webhook bytes for signature verification. Add oversized declared-length and
chunked-body regression tests in a separately authorized implementation task.

Timing: address before production exposure, or verify an equivalent enforced
ingress control. This does not require delaying unrelated offline development.

### 3. Low: the authentication namespace is not strictly default-deny

Affected files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/JwtSecurityConfiguration.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/test/java/com/paymesh/backend/security/auth/JwtAuthenticationIntegrationTest.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/README-BUSINESS-SECURITY.md`

The authentication chain matches `/api/v1/auth/**`, permits POST login, and allows
all remaining requests in that namespace with any valid JWT. There is no current
public provisioning handler, and this is not an unrestricted public wildcard.
However, a future handler in the namespace would inherit authentication-only
access instead of requiring an explicitly reviewed endpoint/role rule.

The README statement that unmatched routes are denied therefore needs this
qualification: unmatched auth-namespace requests are permitted through the
security chain for authenticated callers, although absent handlers still do not
become functional endpoints. The existing protected probe is test-only.

Recommended fix: enumerate approved auth endpoints and deny remaining requests.
Adapt the test-only probe through test-specific security configuration or test
real protected routes without broadening production permissions. Keep production
endpoint inventory and documentation aligned with the filter chains.

Timing: address before introducing additional auth-namespace handlers.

### 4. Low: the README overstates ADMIN audit transaction coverage

Affected files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/README-BUSINESS-SECURITY.md`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/business/BusinessProcessingClaims.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/impl/PaymentOrchestrationServiceImpl.java`

The README says successful ADMIN service operations record audit events in the
same transaction and that audit failure rolls back financial writes. This holds
for the secured facade transactions, but processing has a narrower boundary:
the claim and `ADMIN_PAYMENT_PROCESSING_CLAIMED` audit commit before gateway work.
Subsequent gateway and payment completion use separate trusted operations. That
audit establishes acceptance of processing, not its final result.

This transaction separation avoids holding an authorization transaction across a
gateway call and allows an accepted operation to finish after revocation. No
unauthorized processing was identified from this behavior. The concern is audit
coverage and an overbroad documentation guarantee.

Recommended fix: state explicitly that audit atomicity covers the processing
claim transaction, not the complete gateway lifecycle. Consider correlated final
completion/failure audit events with actor, resource and outcome attribution.
Do not attempt to obtain end-to-end atomicity by holding database locks across
gateway calls or imply that an external gateway action can be rolled back by a
database transaction.

Timing: clarify before relying on the README's audit guarantees in the next phase
or operational review.

### 5. Low: infrastructure failures may be misclassified as authentication failures

Affected files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/business/BusinessAccess.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/JwtAccountValidator.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/JwtSecurityConfiguration.java`

Broad runtime-exception handling during current account/role validation converts
failures into bad credentials or invalid tokens. Database availability or query
failures inside those blocks can therefore appear as 401 responses rather than
infrastructure errors. This fails closed and does not grant access, but obscures
outages and can lead clients to retry credentials unnecessarily.

Recommended fix: distinguish expected credential/claim/account-state rejection
from infrastructure failures. Keep generic authentication responses, return an
appropriate generic availability error for infrastructure faults, and retain
sanitized operational diagnostics without tokens, passwords or key material.

Timing: recommended operational hardening; not an identified authorization bypass
or an unconditional blocker for the next development phase.

## Controls verified by source inspection

### Existing endpoint protection

`/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/BusinessEndpointCatalog.java`
explicitly catalogs the seven financial routes:

| Method | Endpoint | Required application role |
|---|---|---|
| POST | `/api/v1/payments` | ADMIN or MERCHANT |
| GET | `/api/v1/payments/{paymentId}` | ADMIN or MERCHANT |
| POST | `/api/v1/payments/{paymentId}/process` | ADMIN or MERCHANT |
| GET | `/api/v1/payments/{paymentId}/gateway-transactions` | ADMIN or MERCHANT |
| POST | `/api/v1/payments/{paymentId}/refund` | ADMIN or MERCHANT |
| GET | `/api/v1/payments/{paymentId}/refund` | ADMIN or MERCHANT |
| GET | `/api/v1/payments/{paymentId}/refunds` | ADMIN or MERCHANT |

All require JWT authentication and applicable service-level authorization.
Actuator discovery `/actuator` and `/actuator/info` require ADMIN. Health endpoints
`/api/v1/payments/health` and `/actuator/health` remain public. No additional public
payment-history or reconciliation handler was identified. GET routes include HEAD;
OPTIONS permissions are limited to cataloged paths and their matching chains.

### JWT authentication

Relevant files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/JwtConfiguration.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/JwtKeyMaterial.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/JwtAccountValidator.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/JwtTokenService.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/AuthController.java`

The inspected code uses configured asymmetric RSA keys and RS256, 15-minute access
tokens, issuer/audience and temporal validation, enabled-account checks,
authorization-version validation, and exact current server-role matching. Login
uses the existing BCrypt credentials service and generic authentication rejection.
Sessions are stateless; public registration and refresh tokens are not introduced.
No production key fallback or operational ADMIN creation was identified in these
flows.

### Merchant ownership and ADMIN privileges

Relevant files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/business/BusinessAccess.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/business/BusinessScopePredicate.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/repository/PaymentRepository.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/repository/GatewayTransactionRepository.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/accounts/MerchantRepository.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/impl/PaymentServiceImpl.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/impl/RefundServiceImpl.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/service/impl/GatewayTransactionServiceImpl.java`

Scoped predicates check enabled account, current authorization version, actual
server roles, active membership, and verified active merchant state. Service
checks authorize the parent payment before refund/history access, gateway-history
access, processing claims, and financial mutations. Supplied merchant identifiers
do not establish ownership. Payment idempotency references are checked before
replay results are returned. No cross-merchant response path was identified.

ADMIN cross-merchant access is explicitly permitted by `SECURITY-DESIGN.md`, rather
than inferred as a universal bypass. Creation still requires an existing verified,
active target merchant. ADMIN access does not waive financial lifecycle, refund
limits, or idempotency rules. Scoped resource misses use 404, forbidden creation
uses 403, and invalid/missing authentication uses 401.

Business transactions use the shared side of the account-administration advisory
lock protocol; privileged account/membership writers use the exclusive side.
Current processing claims authorize before mutation. Completion of an accepted
operation after revocation is documented and deliberate, not a newly authorized
request.

### Webhook HMAC preservation

Relevant files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/LegacyEndpointCatalog.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/WebhookController.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/WebhookSignatureVerifier.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/WebhookIngress.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/WebhookProcessor.java`

POST `/api/v1/webhooks/mock-razorpay` and POST `/api/v1/webhooks/mock-stripe` remain
outside JWT filtering and retain provider HMAC checks. Timestamp validation,
HMAC-SHA256 over timestamp and raw body, and constant-time comparison occur before
event acceptance. JWTs do not substitute for signatures. Current HTTP webhook
processing reaches the trusted worker through verified ingress.

### Settlement token separation

Relevant files:

- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/LegacyEndpointCatalog.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/SettlementAdminController.java`
- `/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/settlement/ReconciliationRunner.java`

The four existing settlement routes retain independent static bearer-token checks:

- POST `/api/v1/settlement/payments/{paymentId}/reconcile`
- GET `/api/v1/settlement/payments/{paymentId}/reconciliation`
- GET `/api/v1/settlement/payments/{paymentId}/webhooks`
- POST `/api/v1/settlement/webhooks/{id}/retry`

Controller methods verify the dedicated credential before accessing settlement
operations or records. Comparison remains constant-time. Missing/wrong credentials
return 401; missing server token configuration returns 503. ADMIN and MERCHANT
JWTs are not substitutes, and the opaque settlement token is not sent through
the JWT decoder. No current settlement-token bypass was identified.

## Existing documented deployment limitations

The login limiter is per instance and resets on restart:
`/Users/bhupirao/Developer/paymesh-ai/backend/src/main/java/com/paymesh/backend/security/auth/LoginRateLimiter.java`.
Multi-instance production deployments need shared limiting or enforced ingress
budgets. Trustworthy client-address handling and appropriate proxy configuration
remain necessary; raw client-supplied forwarding headers must not establish trust.

Signing-key rotation overlap and refresh tokens are not implemented. RSA key files
must be protected, HTTPS enforced, clocks synchronized, and merchant ownership
verified through the approved provisioning process. These are acknowledged
deployment requirements, not evidence that a current HTTP caller can bypass JWT
or merchant authorization.

## Required follow-up before later phases

1. Enforce trusted internal service boundaries before expanding business entry
   points or internal consumers.
2. Enforce actual request-byte limits before production exposure, or verify an
   equivalent upstream control.
3. Make the auth namespace default-deny before adding handlers there.
4. Correct audit atomicity documentation before relying on its guarantees; decide
   whether correlated final processing outcome events are required.
5. Improve infrastructure error classification and sanitized observability.
6. Obtain and review the exact two displayed warning messages.

No critical/high finding establishes a blanket requirement to stop all further
development. The sequencing conditions above should be resolved before the
affected expansion or deployment. Recommended regression tests are future work;
none were executed during this audit or report-saving task.

## Test evidence status

`README-BUSINESS-SECURITY.md` records the prior isolated suite result as 156 tests,
zero failures, zero errors and zero skips, including 16 business authorization
integration tests. That is historical evidence from implementation, not a fresh
verification performed by this audit. Relevant existing test sources were
inspected, but no test command was run for this review.

The review and report-saving task stop here. No security implementation changes
or later development phases were started.

## Follow-up: final two findings addressed

Subsequent implementation clarified the ADMIN audit transaction boundary in
`README-BUSINESS-SECURITY.md`: facade operations are atomic with their audit
events, while payment processing's claim/audit commits before the gateway call
and does not represent the final outcome. The implementation preserves the
accepted-processing behavior after revocation.

Authentication-state database errors are now distinguished from invalid token
claims and credentials. `SecurityStateUnavailableException` maps these failures
to generic HTTP 503 responses; invalid credentials and tokens retain generic 401
responses. Business account/role lookup and the JWT token-state validator apply
this distinction. A regression test simulates token-state database unavailability.

These changes resolve findings 4 and 5 as originally stated, subject to successful
isolated-suite verification. The remaining findings are unchanged by this
follow-up.

Verification completed with `bash scripts/test-isolated.sh`: 169 tests, zero
failures, zero errors and zero skips (BUILD SUCCESS); the isolated PostgreSQL
server reported `server stopped`. Regression coverage simulates a token-state
database failure and verifies HTTP 503 while the existing invalid-token tests
continue to verify generic HTTP 401. These two findings are resolved in the
reviewed implementation.
