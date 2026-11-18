# Final security audit: Phase 3A through Phase 3C.5

Audit date: 2026-11-12  
Project: `/Users/bhupirao/Developer/paymesh-ai/backend`

## Verdict: PASS

No current HTTP authorization bypass or cross-merchant data exposure was found
in the reviewed routes. JWT authentication, scoped payment authorization,
webhook HMAC and separate settlement bearer checks remain enforced. The two
remaining application-level findings have been addressed with expanded exact
class checks and explicit JPA/transaction failure classification. The full
isolated suite passes.

This is a source review plus test run, not a production deployment assessment.
The two warning messages previously mentioned in conversation were never supplied;
their exact source and meaning could not be verified.

## Original audit findings

### 1. Medium — Trusted worker boundary relies on conventions

**Status: Addressed for current source-level injection paths.**

`InternalPaymentService`, `InternalRefundService` and
`InternalGatewayTransactionService` now declare narrow contracts instead of
inheriting public business service interfaces. `InternalFinancialBoundaryArchitectureTest`
checks their contracts and restricts current internal capability/repository
consumers to exact reviewed classes. HTTP controllers cannot inject these
capabilities or financial repositories under the test's source checks.

Internal interfaces and their `Financial*Operations` implementations remain
application-visible Spring beans, so architecture tests provide source-level
enforcement rather than a JVM module boundary. The test now checks direct source
references to each concrete financial implementation in addition to internal
interfaces and financial repositories, and permits only exact reviewed classes.
No current endpoint uses these capabilities without the reviewed authorized path.

Relevant files:

- `src/main/java/com/paymesh/backend/service/internal/InternalPaymentService.java`
- `src/main/java/com/paymesh/backend/service/internal/InternalRefundService.java`
- `src/main/java/com/paymesh/backend/service/internal/InternalGatewayTransactionService.java`
- `src/main/java/com/paymesh/backend/service/impl/FinancialPaymentOperations.java`
- `src/main/java/com/paymesh/backend/service/impl/FinancialRefundOperations.java`
- `src/main/java/com/paymesh/backend/service/impl/FinancialGatewayTransactionOperations.java`
- `src/test/java/com/paymesh/backend/security/InternalFinancialBoundaryArchitectureTest.java`

Future hardening could add operation-specific worker ports and stronger
package/module encapsulation. Current source checks include the concrete
implementation names and reject unreviewed consumers.

### 2. Medium — Request-body size limits

**Status: Addressed at application level; deployment edge still needs verification.**

`BoundedRequestBodyFilter` limits actual bytes read for the exact login and two
webhook POST paths, including requests with unknown/chunked length. Login is
limited to 4 KiB, each webhook to 64 KiB, and excess bodies return 413 before MVC
deserialization. Accepted webhook bytes are replayed unchanged so HMAC remains
over the original payload. Real HTTP tests cover oversized routes, UTF-8 byte
counting, rejected webhook side effects and login rate-limit ordering.

Relevant files:

- `src/main/java/com/paymesh/backend/security/BoundedRequestBodyFilter.java`
- `src/main/java/com/paymesh/backend/security/auth/LoginRateLimitFilter.java`
- `src/test/java/com/paymesh/backend/security/BoundedRequestBodyHttpIntegrationTest.java`
- `src/test/java/com/paymesh/backend/settlement/SettlementIntegrationTest.java`

Remaining deployment limitation: verify production servlet connector and reverse
proxy behavior for chunked requests and configure compatible edge limits. The
application filter buffers accepted bodies in memory, bounded at 64 KiB per
webhook request.

### 3. Low — Auth namespace default-deny

**Status: Addressed.**

Only POST `/api/v1/auth/login` is permitted. All other paths and methods under
`/api/v1/auth/**` are denied for anonymous users and valid ADMIN/MERCHANT JWT
holders. The test probe moved outside that namespace and has no production
security exception. Tests cover ADMIN, MERCHANT, anonymous and non-POST login.

Relevant files:

- `src/main/java/com/paymesh/backend/security/auth/JwtSecurityConfiguration.java`
- `src/test/java/com/paymesh/backend/security/auth/JwtAuthenticationIntegrationTest.java`
- `README-BUSINESS-SECURITY.md`

### 4. Low — ADMIN audit atomicity wording

**Status: Documentation overstatement corrected; final-outcome audit remains a policy choice.**

`README-BUSINESS-SECURITY.md` now says secured facade writes and their ADMIN audit
events share a transaction. Payment processing is explicitly qualified: the
authorized claim and `ADMIN_PAYMENT_PROCESSING_CLAIMED` event commit before the
gateway call; this records acceptance, not final gateway success/failure. An
accepted operation can finish after membership revocation, preserving the
existing payment lifecycle. No database transaction spans the gateway call.

The code does not add correlated ADMIN audit events for final gateway completion
or failure. This is disclosed in the documentation and remains a potential audit
trail enhancement, not a claim of end-to-end transaction atomicity.

Relevant files:

- `README-BUSINESS-SECURITY.md`
- `src/main/java/com/paymesh/backend/security/business/BusinessProcessingClaims.java`
- `src/main/java/com/paymesh/backend/service/impl/PaymentOrchestrationServiceImpl.java`

### 5. Low — Infrastructure failure classification

**Status: Addressed for Spring data, JPA persistence and transaction-system failures.**

`JwtAccountValidator` and `BusinessAccess` distinguish Spring
`DataAccessException` and map it through `SecurityStateUnavailableException` to a
generic 503. Invalid JWTs and invalid credentials remain generic 401. A regression
test simulates a token-state data access outage and verifies 503; existing tests
continue to cover invalid token/credential 401 responses. The outer
`SecurityAvailabilityFilter` emits only a generic body and writes a sanitized
warning without credentials or exception text.

Both validators now classify Spring `DataAccessException`, JPA
`PersistenceException` and `TransactionSystemException` as unavailable security
state before handling malformed claims. Other unexpected runtime failures remain
fail-closed and may still be reported as authentication failure; operators should
monitor the sanitized availability log and extend classification only for
identified persistence exception types.

Relevant files:

- `src/main/java/com/paymesh/backend/security/BusinessAccess.java`
- `src/main/java/com/paymesh/backend/security/auth/JwtAccountValidator.java`
- `src/main/java/com/paymesh/backend/security/SecurityStateUnavailableException.java`
- `src/main/java/com/paymesh/backend/security/SecurityAvailabilityFilter.java`
- `src/main/java/com/paymesh/backend/security/auth/SecurityResponses.java`
- `src/test/java/com/paymesh/backend/security/auth/JwtAuthenticationIntegrationTest.java`

Regression coverage simulates both translated Spring data-access failure and an
untranslated JPA persistence exception. Generic 401 behavior for invalid tokens
and credentials remains covered.

## Other controls reviewed

### JWT authentication

`JwtSecurityConfiguration`, `JwtKeyMaterial`, `JwtAccountValidator`,
`JwtTokenService` and `AuthController` implement RS256 tokens with configured key
files, issuer/audience checks, temporal limits, 15-minute expiry, enabled account,
current role and authorization-version validation. Sessions are stateless. No
production registration handler, default signing key or operational ADMIN
account was identified. Login throttling is bounded and per instance.

### Merchant isolation and ADMIN scope

Payment, refund, processing and gateway history endpoints require JWT roles.
Service facades authorize parent payments and query scope using current account,
server-side role, verified active merchant and active membership data. Request
`merchantId` alone cannot establish access. Cross-merchant resources are hidden
with 404; forbidden creation is 403. The design explicitly permits audited ADMIN
cross-merchant financial access and still requires verified active merchants for
creation. Refund calculations and payment transitions remain behind secured
facades and existing financial cores.

### Webhooks and settlement

Webhook endpoints remain outside JWT enforcement and verify timestamped
HMAC-SHA256 signatures with constant-time comparison over unchanged raw request
bytes before persistence. Settlement endpoints continue to use their separate
constant-time static bearer token; application JWTs do not substitute. Health
routes remain public as designed.

## Phase 3C.4 failure-path coverage

Current tests cover:

- Login: wrong, unknown and disabled credentials return generic 401; absent JWT
  configuration fails closed with 503; rate limiting returns 429.
- JWT validation: signature tampering, unsupported algorithm, wrong issuer or
  audience, missing/expired/future temporal claims, disabled accounts, stale
  authorization versions and changed server roles are rejected.
- Authentication state outage: token-state `DataAccessException` returns generic
  503, while malformed/invalid JWTs remain 401.
- Business authorization: missing authentication, disabled account, revoked or
  unverified membership, merchant spoofing and cross-merchant access are covered;
  tests assert 401/403/404 behavior and no unauthorized financial side effects.
- Admin and external credentials: ADMIN action audit rollback, HMAC independent
  of JWT, settlement token independent of JWT, and public health behavior.

Coverage does not simulate every underlying database/JPA exception type; the
remaining classification concern is described under finding 5.

## Final regression run and safety

Command: `bash scripts/test-isolated.sh`.

Result: **170 tests, 0 failures, 0 errors, 0 skips; BUILD SUCCESS.** The run began
against the script-verified isolated database
`paymesh_isolated_1794454759_62794` at `127.0.0.1:55441`, with data directory
`/private/tmp/paymesh-webhook-test.pFjDwN/data`. The test script reported
`server stopped` after completion.

Application database safety: the isolation guard verified the temporary database
name and physical PostgreSQL data directory before tests; the configured URL was
not the application database on port 5432. No migrations were run against the
application database, no production records were accessed or changed, and no
operational ADMIN account was created.

Deployment limitations include per-instance login throttling, no refresh tokens,
no overlapping JWT signing-key rotation, dependence on correct ownership
verification and secure key files, and required proxy/body-limit configuration.
The exact two warning messages previously referenced were unavailable and could
not be independently assessed.

Final verdict is **PASS**: the audited source-level worker boundaries cover
current interface and concrete implementation references; JWT and business
authorization distinguish the recognized database/JPA/transaction outage
classes from invalid authentication. Continue to review new worker consumers
and new persistence exception types as they are introduced.
