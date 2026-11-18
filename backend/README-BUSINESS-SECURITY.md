# Business authorization

This file records the current business authorization model. The canonical route and DTO reference is [API-REFERENCE.md](API-REFERENCE.md); the controlled demo procedure is [README-DEMO.md](README-DEMO.md).

## Endpoint inventory

JWT roles are checked against current server-side account state. Neither a client
merchant identifier nor JWT roles alone establish ownership.

| Method | Endpoint | Authentication and authorization |
|---|---|---|
| POST | `/api/v1/payments` | ADMIN or MERCHANT JWT; verified, active target merchant; MERCHANT needs active membership |
| GET | `/api/v1/payments/{paymentId}` | ADMIN or owning MERCHANT JWT |
| POST | `/api/v1/payments/{paymentId}/process` | ADMIN or owning MERCHANT JWT |
| GET | `/api/v1/payments/{paymentId}/gateway-transactions` | ADMIN or owning MERCHANT JWT |
| POST | `/api/v1/payments/{paymentId}/refund` | ADMIN or owning MERCHANT JWT |
| GET | `/api/v1/payments/{paymentId}/refund` | ADMIN or owning MERCHANT JWT |
| GET | `/api/v1/payments/{paymentId}/refunds` | ADMIN or owning MERCHANT JWT |
| POST | `/api/v1/webhooks/mock-razorpay` | Existing provider HMAC; JWT does not substitute |
| POST | `/api/v1/webhooks/mock-stripe` | Existing provider HMAC; JWT does not substitute |
| POST | `/api/v1/settlement/payments/{paymentId}/reconcile` | Existing settlement admin bearer only |
| GET | `/api/v1/settlement/payments/{paymentId}/reconciliation` | Existing settlement admin bearer only |
| GET | `/api/v1/settlement/payments/{paymentId}/webhooks` | Existing settlement admin bearer only |
| POST | `/api/v1/settlement/webhooks/{id}/retry` | Existing settlement admin bearer only |
| GET | `/api/v1/payments/health` | Public, unchanged |
| GET | `/actuator/health` | Public, unchanged |
| GET | `/actuator`, `/actuator/info` | ADMIN JWT |
| POST | `/api/v1/auth/login` | Existing rate-limited credential login |

Only POST `/api/v1/auth/login` is permitted through the authentication namespace.
Every other method/path under `/api/v1/auth/**` is denied, including requests with
valid ADMIN or MERCHANT JWTs. The JWT integration test's transport probe lives
outside that namespace and is subject to the normal default-deny chain; it adds no
production endpoint or security exception.

GET routes also allow HEAD. OPTIONS is limited to cataloged paths and follows
the matching chain's authentication requirements. Unmatched routes are denied.
There is no additional public payment-history or reconciliation route.

## Ownership and failures

MERCHANT access requires an enabled account with current authorization version,
current MERCHANT role, active membership, and a verified, active merchant. Exact
stored merchant identifiers are used without rewriting historical values. Multiple
verified memberships are supported. Historical merchants remain unclaimed until
the existing authorized verification process is completed.

The approved design explicitly permits ADMIN cross-merchant financial access.
ADMIN actions through secured business facades record audit events in the same
database transaction; failure to persist those events rolls back that facade's
financial writes. Payment processing is the documented boundary: the authorized
claim and `ADMIN_PAYMENT_PROCESSING_CLAIMED` audit commit before the gateway call.
Gateway completion/failure happens later in separate transactions, so this event
records accepted processing rather than its final outcome. Revocation prevents
new requests but does not cancel an already accepted gateway operation.
ADMIN creation still requires an existing verified, active merchant. No automatic
merchant registration or claim is introduced.

Missing, invalid, expired, disabled-account or stale-version JWTs return 401.
Authenticated callers without the required role or creation membership return
403. Resource lookups outside merchant scope return the same 404 as absent
resources, including refund history, refund creation and processing. An unknown
ADMIN creation target returns 404; an unverified target returns 403. Idempotency
replays are authorized before returning a previously linked payment/refund.

## Transaction and worker boundaries

Public PaymentService, RefundService and GatewayTransactionService implementations
are secured facades. Database predicates independently check account, roles and
merchant scope; parent authorization precedes child reads and mutations. Account
and membership changes serialize against these transactions using the existing
account-administration advisory lock protocol (shared for business operations,
exclusive for administration).

Trusted internal financial implementations retain existing payment calculations,
idempotency, refund locking and lifecycle rules. They are used by background
settlement/provider processing and after an authorized processing claim; they are
not HTTP authorization entry points. New business entry points must use secured
services and scoped repository access.

Processing authorization and the CREATED-to-PROCESSING claim commit before the
gateway call. No authorization transaction or account lock spans that call.
Revocation blocks subsequent requests but does not cancel an already accepted
gateway operation; its internal completion preserves the existing lifecycle and
settlement race handling. Automated settlement remains a trusted internal worker.

Webhook verification is unchanged. Settlement endpoints retain constant-time
static-token verification separately from JWT; missing/wrong tokens return 401,
and absent server token configuration returns 503. An ADMIN JWT is not a
settlement credential. Health endpoints continue to ignore JWT headers.

## Verification and deployment limits

Run tests only with `bash scripts/test-isolated.sh`. The existing pre-Flyway
physical-cluster isolation guard remains mandatory. Tests use temporary RSA keys
and accounts only in the verified isolated PostgreSQL cluster.

Coverage includes missing JWTs, real ADMIN/MERCHANT signed JWTs, database scope
predicates, direct service authorization, cross-merchant reads and writes,
merchant spoofing, revoked/unverified/inactive memberships, disabled accounts,
refund ownership and totals, ADMIN audit rollback, processing after revocation,
unchanged provider HMAC, static settlement authentication and public health.
Existing financial, concurrency, migration and authentication regressions remain
in the complete suite. No V1–V8 migration or application database is changed.

Historical Phase 3B run: `bash scripts/test-isolated.sh`, 156 tests, zero failures,
zero errors and zero skips (BUILD SUCCESS), with 16 business authorization tests.
This is milestone evidence, not a current test count. The later supplied baseline
was 187 passing tests; this documentation phase did not rerun tests.

Deployment still requires verified ownership provisioning, HTTPS, protected RSA
key files, synchronized clocks and suitable ingress controls. Existing login
rate limits are per instance; distributed limiting and overlapping signing-key
rotation remain future work. No refresh tokens or public provisioning APIs are
introduced. Trusted internal code and future administrative writers must preserve
the scoped-service and administration-lock conventions.

## Phase 3B file manifest

Files created or modified relative to the start of Phase 3B:

- `README-JWT.md`
- `README-BUSINESS-SECURITY.md`
- `src/main/java/com/paymesh/backend/repository/GatewayTransactionRepository.java`
- `src/main/java/com/paymesh/backend/repository/PaymentRepository.java`
- `src/main/java/com/paymesh/backend/settlement/SettlementAdminController.java`
- `src/main/java/com/paymesh/backend/service/impl/PaymentOrchestrationServiceImpl.java`
- `src/main/java/com/paymesh/backend/service/impl/FinancialRefundOperations.java`
- `src/main/java/com/paymesh/backend/service/impl/RefundServiceImpl.java`
- `src/main/java/com/paymesh/backend/service/impl/FinancialPaymentOperations.java`
- `src/main/java/com/paymesh/backend/service/impl/GatewayTransactionServiceImpl.java`
- `src/main/java/com/paymesh/backend/service/impl/PaymentServiceImpl.java`
- `src/main/java/com/paymesh/backend/service/impl/FinancialGatewayTransactionOperations.java`
- `src/main/java/com/paymesh/backend/service/internal/InternalPaymentService.java`
- `src/main/java/com/paymesh/backend/service/internal/InternalGatewayTransactionService.java`
- `src/main/java/com/paymesh/backend/service/internal/InternalRefundService.java`
- `src/main/java/com/paymesh/backend/security/auth/BusinessEndpointCatalog.java`
- `src/main/java/com/paymesh/backend/security/auth/JwtSecurityConfiguration.java`
- `src/main/java/com/paymesh/backend/security/auth/LegacyEndpointCatalog.java`
- `src/main/java/com/paymesh/backend/security/business/BusinessResourceNotFoundException.java`
- `src/main/java/com/paymesh/backend/security/business/BusinessScopePredicate.java`
- `src/main/java/com/paymesh/backend/security/business/BusinessSecurityErrors.java`
- `src/main/java/com/paymesh/backend/security/business/BusinessProcessingClaims.java`
- `src/main/java/com/paymesh/backend/security/business/BusinessAccess.java`
- `src/main/java/com/paymesh/backend/security/accounts/MerchantRepository.java`
- `src/test/java/com/paymesh/backend/settlement/OrchestrationSettlementRaceTest.java`
- `src/test/java/com/paymesh/backend/settlement/SettlementIntegrationTest.java`
- `src/test/java/com/paymesh/backend/integration/PaymentGatewayExceptionIntegrationTest.java`
- `src/test/java/com/paymesh/backend/integration/PaymentOptimisticLockingIntegrationTest.java`
- `src/test/java/com/paymesh/backend/integration/PaymentIdempotencyIntegrationTest.java`
- `src/test/java/com/paymesh/backend/integration/PaymentLifecycleIntegrationTest.java`
- `src/test/java/com/paymesh/backend/integration/PaymentOrchestrationConcurrencyIntegrationTest.java`
- `src/test/java/com/paymesh/backend/integration/PaymentAtomicClaimIntegrationTest.java`
- `src/test/java/com/paymesh/backend/integration/RefundIntegrationTest.java`
- `src/test/java/com/paymesh/backend/testing/BusinessJwtTestSupport.java`
- `src/test/java/com/paymesh/backend/service/PaymentOrchestrationServiceImplTest.java`
- `src/test/java/com/paymesh/backend/security/auth/JwtAuthenticationIntegrationTest.java`
- `src/test/java/com/paymesh/backend/security/business/BusinessAuthorizationIntegrationTest.java`
