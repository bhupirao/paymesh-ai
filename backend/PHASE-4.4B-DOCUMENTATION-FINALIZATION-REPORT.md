# Phase 4.4B — Documentation finalization report

## 1. Summary

Updated the operator-facing README set, established `API-REFERENCE.md` as the source-checked API contract, and created `README-DEMO.md` for the guarded local demo. Historical documents are labeled as historical where their implementation state predates current authentication or timeout simulation. The report preserves the supplied 187-test and live-demo results as prior evidence; it does not present them as newly run or independently observed in this phase.

The resulting documentation describes a simulated backend for controlled local development/demo only. It does not claim real payment provider integration or production certification. The current Compose backend is not approved for the guarded demo because its service-to-database URL is not loopback-compatible with the existing demo guard.

## 2. Files created and modified

Modified:

- `README-DEPLOY.md` — replaced stale deployment, unauthenticated API smoke-test, V1–V5, and bare Maven instructions; documented current authentication, V1–V8, isolated test runner, and Compose limitation.
- `README-WEBHOOKS.md` — documented current HMAC, receipt, deduplication, reconciliation, and independent settlement-token behavior; removed old unauthenticated business request examples.
- `README-REFUNDS.md` — documented the current amount body, required `Idempotency-Key`, multiple partial refunds, full remaining-balance refund, over-refund rejection, simulated-only effect, and JWT scope.
- `README-ACCOUNTS.md` — marked Phase 2’s “no JWT” statements as historical and retained secure offline provisioning instructions.
- `README-BUSINESS-SECURITY.md` — linked the canonical API/demo docs and relabeled the 156-test Phase 3B figure as historical milestone evidence.
- `README-JWT.md` — added the actual login request schema, 15-minute lifetime and re-login renewal guidance, and canonical references.
- `PHASE-4.3.6-WEBHOOK-DEMO-PLAN.md` — added a historical pre-fault-simulation banner and links to the current fault-simulation report and demo runbook; its historical body remains intact.

Created:

- `API-REFERENCE.md` — canonical route, role, request/response, status, and idempotency contract.
- `README-DEMO.md` — guarded local runbook for provisioning checks, login, normal routing, refunds, webhook recovery, reconciliation, troubleshooting, and safe shutdown.
- `PHASE-4.4B-DOCUMENTATION-FINALIZATION-REPORT.md` — this report.

No Java source, test source, `pom.xml`, application properties, Flyway migration, Docker/Compose file, CI configuration, database record, or runtime process was modified.

## 3. Source-verified endpoint inventory

The complete per-route contract is in [API-REFERENCE.md](API-REFERENCE.md). This inventory was verified against the current controller and security catalog source, not inferred from old README text.

| Method and route | Authentication / scope | Source |
|---|---|---|
| `GET /api/v1/payments/health` | Public; static response | `src/main/java/com/paymesh/backend/controller/PaymentController.java` (`health`) |
| `GET /actuator/health` | Public aggregate Actuator health | `src/main/resources/application.properties`; security catalogs |
| `GET /actuator`, `GET /actuator/info` | ADMIN JWT | `src/main/resources/application.properties`; `BusinessEndpointCatalog` |
| `POST /api/v1/auth/login` | Public, login rate limit | `src/main/java/com/paymesh/backend/security/auth/AuthController.java` |
| `POST /api/v1/payments` | ADMIN or MERCHANT JWT; verified merchant and membership checks | `PaymentController.createPayment`; business security services |
| `GET /api/v1/payments/{paymentId}` | ADMIN or owning MERCHANT JWT | `PaymentController.getPaymentById` |
| `POST /api/v1/payments/{paymentId}/process` | ADMIN or owning MERCHANT JWT | `PaymentController.processPayment` |
| `GET /api/v1/payments/{paymentId}/gateway-transactions` | ADMIN or owning MERCHANT JWT | `GatewayTransactionController.history` |
| `POST /api/v1/payments/{paymentId}/refund` | ADMIN or owning MERCHANT JWT; amount and idempotency key required | `RefundController.refund` |
| `GET /api/v1/payments/{paymentId}/refund` | ADMIN or owning MERCHANT JWT | `RefundController.get` |
| `GET /api/v1/payments/{paymentId}/refunds` | ADMIN or owning MERCHANT JWT | `RefundController.history` |
| `POST /api/v1/webhooks/mock-razorpay` | Razorpay mock HMAC; no JWT | `WebhookController.razorpay` |
| `POST /api/v1/webhooks/mock-stripe` | Stripe mock HMAC; no JWT | `WebhookController.stripe` |
| `POST /api/v1/settlement/payments/{paymentId}/reconcile` | Separate settlement bearer token only | `SettlementAdminController.reconcile` |
| `GET /api/v1/settlement/payments/{paymentId}/reconciliation` | Separate settlement bearer token only | `SettlementAdminController.history` |
| `GET /api/v1/settlement/payments/{paymentId}/webhooks` | Separate settlement bearer token only | `SettlementAdminController.events` |
| `POST /api/v1/settlement/webhooks/{id}/retry` | Separate settlement bearer token only | `SettlementAdminController.retry` |

GET routes allow HEAD as registered by the exact catalogs; OPTIONS is restricted to cataloged paths and inherits their authorization chain. The security configuration denies unmatched routes/methods; no public wildcard was documented. There is no refresh-token endpoint, registration endpoint, arbitrary payment-status endpoint, or real provider transaction endpoint.

Key request/response facts checked in source:

- Payment request fields: `merchantId`, `amount`, `currency`, `customerId`, `paymentMethod`; payment response fields include `paymentId`, `status`, and `createdAt`.
- Gateway history response is `gatewayName` (not `gateway`) plus transaction/status/error/timestamp fields.
- Refund creation body is `{"amount":...}` with required `Idempotency-Key`; refund response includes `refundId`, `paymentId`, `amount`, `status`, `createdAt`.
- Login body is `{"login":...,"password":...}`; successful response exposes a bearer access token and `expiresIn: 900`.
- Webhook body uses `eventId`, UUID `paymentId`, UUID `gatewayTransactionId`, observation `status`, and ISO-8601 `occurredAt`. Timestamp header is Unix seconds; HMAC is hex SHA-256 over timestamp, dot, and raw body, within ±300 seconds.
- Settlement report fields are `paymentId`, `status`, `attempts`, `nextAttemptAt`; history endpoints return up to 100 row maps; retry returns a webhook receipt.

Primary source locations include `PaymentController.java`, `RefundController.java`, `GatewayTransactionController.java`, `AuthController.java`, `JwtSecurityConfiguration.java`, `BusinessEndpointCatalog.java`, `LegacyEndpointCatalog.java`, `WebhookController.java`, `WebhookSignatureVerifier.java`, `WebhookIngress.java`, `WebhookPayload.java`, `SettlementAdminController.java`, `ReconciliationService.java`, `PaymentRequest.java`, `PaymentResponse.java`, `RefundRequest.java`, and `GatewayTransactionResponse.java` under `src/main/java/com/paymesh/backend/`.

## 4. Resolution matrix

| Finding | Status | Resolution and residual note |
|---|---|---|
| H-01 — outdated unauthenticated business examples and incorrect refund/test instructions | **Resolved for current operator docs; historical example caveat remains** | Current deployment, refund, webhook, and demo examples use JWT for business APIs; refund examples include amount and idempotency key; test guidance uses only `bash scripts/test-isolated.sh`. The old Phase 4.3.6 plan body is preserved as requested and visibly marked historical; do not execute its superseded business examples. |
| M-09 — outdated docs and historical implementation claims | **Resolved with explicit historical labeling** | Phase 2 account claims and Phase 3B test count are labeled historical; the earlier webhook plan is labeled pre-fault-simulation and links to the later report. Historical audit evidence was preserved. |
| M-10 — bearer credentials exposed through curl command-line arguments | **Resolved in current command examples** | Settlement/JWT examples use protected curl config input or Python clients; no actual credential values are present. `README-DEMO.md` states the unsafe expanded-header form only in a negative instruction, not as a command to run. |
| L-01 — fragmented API contract documentation | **Resolved** | `API-REFERENCE.md` is the single human-readable endpoint contract and links to focused security, JWT, refund, webhook, deploy, and demo documents. |

## 5. Before / after documentation examples

| Before | After |
|---|---|
| `README-DEPLOY.md` showed unauthenticated payment creation and bodyless refund curls, claimed APIs were unauthenticated, described only V1–V5, and instructed `mvn clean test`. | Current protected requests require JWT; refund POST requires an amount and `Idempotency-Key`; migrations are documented as V1–V8; tests use `bash scripts/test-isolated.sh`. |
| `README-WEBHOOKS.md` said normal processing could not create a recoverable demo and used an expanded token in an Authorization header. | It now links to the source-backed timeout demo, documents the enabled-only demo selector, and uses curl config input for settlement credentials. |
| `README-REFUNDS.md` examples omitted JWT and described testing outside the guarded runner. | Examples are JWT-authenticated and explain partial/multiple/full refunds, replay, over-refund, and simulation semantics. |
| Current gateway examples used or implied `gateway`. | The canonical response schema and examples use the source property `gatewayName`. |

## 6. Demo and deployment documentation findings

Verified runtime property mappings in `src/main/resources/application.properties` include `PORT`, `PAYMESH_DB_URL`, `PAYMESH_DB_USER`, `PAYMESH_DB_PASSWORD`, `PAYMESH_RAZORPAY_WEBHOOK_SECRET`, `PAYMESH_STRIPE_WEBHOOK_SECRET`, `PAYMESH_SETTLEMENT_ADMIN_TOKEN`, `PAYMESH_SETTLEMENT_SCHEDULING_ENABLED`, `PAYMESH_SETTLEMENT_POLL_MS`, `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED`, `PAYMESH_JWT_PRIVATE_KEY_FILE`, `PAYMESH_JWT_PUBLIC_KEY_FILE`, `PAYMESH_JWT_ISSUER`, `PAYMESH_JWT_AUDIENCE`, and login limit variables. The demo runbook additionally sets Spring's standard `SERVER_ADDRESS=127.0.0.1` override so its host-run server binds only to loopback; `PORT=18080` sets its port.

The application JDBC fallback names `paymesh_db`; demo docs explicitly require `PAYMESH_DB_URL` to be set to loopback `paymesh_demo`. `DemoDatabaseGuard` in `src/main/java/com/paymesh/backend/security/accounts/DemoDatabaseGuard.java` permits local PostgreSQL `localhost`/`127.0.0.1`, exact database name `paymesh_demo`, and checks the connected database. `application.properties` defaults demo fault simulation off and settlement scheduling off. The report and runbook preserve these guards.

The current backend Compose service resolves PostgreSQL through a container hostname rather than loopback. That does not satisfy the guard. Existing Compose is therefore explicitly not recommended for the guarded demo. The safe future architecture is a database-only PostgreSQL container published on loopback plus host-run Spring Boot configured to the exact demo database. This is a plan only; no Compose configuration was changed or approved. Docs also do not claim Docker secret-file support for webhook/settlement environment properties.

An operational limitation remains in the initial ADMIN bootstrap path: unlike the merchant demo provisioner, `InitialAdminProvisioner` does not use the dedicated demo-target guard. The runbook tells operators to independently verify the exact datasource before running it and says not to bootstrap an already provisioned account. A narrowly scoped target guard for initial bootstrap is a recommended future change, outside this docs-only phase.

## 7. Static validation performed

Only read-only source/document inspection and local Markdown text checks were performed. No application start, HTTP request, Maven command, test, Docker command, migration, database connection, or secret-content inspection was performed.

Static checks reviewed the final docs for:

- Exact controller routes, DTO fields, security chain boundaries, configuration property names, migration range, and gateway timeout selector.
- Active docs for bare Maven test instructions, expanded bearer-header command examples, stale `gateway` response property, outdated “no partial refunds”/“no recoverable timeout” claims, and stale unauthenticated business curls.
- Relative Markdown links among the updated docs and cited existing reports.

The static link scan was repeated after creating this report; all local Markdown links resolve. Text checks found no executable expanded bearer-token curl examples. Mentions of `mvn clean test`, unauthorized use patterns, or superseded behavior occur only as explicit prohibitions/historical caveats. These are static checks, not Markdown rendering, shell execution, or API integration tests.

## 8. Unexecuted examples and prior evidence

The commands in `README-DEMO.md` are source-derived examples and were not run. They create payments and can mutate payment/webhook/reconciliation state if an operator executes them, so the runbook warns to stop after uncertain results and inspect state before retrying. The Python webhook example assumes the existing secret variables are loaded in the current shell and never prints their values.

The baseline of 187 passing tests and the described live webhook/reconciliation results were provided as previously verified evidence for this task. No tests or live requests were rerun, and this report does not independently verify those historical outcomes.

## 9. Remaining risks and recommended next phase

- The existing Compose topology remains unapproved for the guarded demo; implement and separately review the planned database-only loopback Compose architecture before documenting it as operational.
- Initial ADMIN provisioning lacks the merchant provisioner's exact demo-database target guard; add a fail-closed guard and focused offline-provisioning regression coverage before relying on that command for demo bootstrap.
- Deployment still requires secret lifecycle controls, HTTPS/ingress policy, synchronized clocks, operational monitoring, and a review of per-instance login rate limiting. This report does not certify production readiness.
- Historical Phase 4.3.6 request examples remain in the preserved historical report behind a clear warning. They are not current API instructions.
- All demo create/refund/webhook/reconcile commands are state-changing and were not independently executed in this phase.

Recommended next phase: implement and verify the database-only local Compose architecture and close the offline initial-ADMIN target-guard gap, then conduct an operator review of the demo commands in a disposable, explicitly approved `paymesh_demo` environment. Keep production readiness as a separate security and operations gate.

## 10. Scope confirmation and verdict

This phase changed Markdown documentation only. It did not modify application code, tests, build configuration, application runtime configuration, migrations, Docker/Compose/CI files, database records, or running services. No secrets or credential values were printed or inspected.

**Final verdict: CONDITIONALLY READY for controlled local development/demo documentation only.** The docs now describe current source behavior more accurately, but existing Compose remains unsuitable for the guarded demo, offline ADMIN bootstrap needs a target guard, examples remain unexecuted, and the backend is not production ready.
