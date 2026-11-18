# Phase 4.4A — Backend Documentation and Deployment Readiness Audit

**Scope:** read-only source, repository, documentation and deployment-file review. No tests, builds, Docker commands, application requests, migrations, or database connections were made for this audit. No secret values, passwords, tokens, or private key contents were read or printed. This report is the only file created for the audit.

## A. Current readiness summary

The source implements a substantial **simulated payment backend** with payment/refund lifecycle controls, database-backed idempotency, secured merchant-aware APIs, RS256 JWT login, independently authenticated HMAC webhooks, a separate settlement token, simulated reconciliation, and a demo-only gateway-timeout scenario. The build declares Java 21 and Spring Boot 3.5.7. Migrations V1–V8 are present; application startup runs Flyway and then Hibernate schema validation.

The current source is **not ready for public or production deployment** based on repository configuration. The Compose stack has no JWT, webhook, or settlement credentials configured; publishes HTTP port 8080 on all host interfaces; has no backend health check; and uses a `db` network hostname which the demo-only loopback guard intentionally rejects. Several checked-in runbooks still describe the old unauthenticated API and outdated refund/gateway behavior. The service must not be represented as a real Razorpay/Stripe integration or as production certified.

For a controlled local demo, the source can support the reported workflow when the demo application is started on the host against a dedicated local `paymesh_demo` database and supplied with the existing secret/key configuration. The audit did not independently start or verify that runtime.

## B. Verified feature inventory

| Area | Source-backed behavior |
|---|---|
| Build | `pom.xml:8-21` declares Spring Boot 3.5.7 and Java 21. Spring-managed versions are used for Spring Security, Resource Server, JPA, Flyway and other dependencies (`pom.xml:23-85`). |
| Persistence | PostgreSQL and Flyway are configured in `src/main/resources/application.properties:6-16`; Flyway is enabled by default and Hibernate uses `ddl-auto=validate`. Migrations V1–V8 are in `src/main/resources/db/migration/`. V6 documents preservation of prior refund identifiers/amount/status/timestamps; V7 is additive; V8 says existing business rows and ownership strings remain unchanged and only adds account/merchant tables plus an exact-value merchant registry backfill. |
| Payments | `PaymentController` exposes create, read, process, and static health endpoints. Payment creation requires an `Idempotency-Key`; processing uses an atomic claim. Currency routing is INR → `MOCK_RAZORPAY`, USD → `MOCK_STRIPE`, with no cross-provider fallback (`RoutingPaymentGateway.java:16-23`). Both provider implementations are simulated (`MockRazorpayGateway.java`, `MockStripeGateway.java`). |
| Refunds | `RefundController.java:23-40` requires a positive amount and idempotency key for POST, and exposes latest/history reads. The service protects totals with payment-row locking. V6 supports multiple refund rows and per-key uniqueness. README-REFUNDS correctly states that the gateway refund is simulated and there is no external reversal (`README-REFUNDS.md:32-45`). The sum ceiling is enforced through supported service/locking paths, not a cross-table database CHECK (`README-REFUNDS.md:32-39`). |
| Authentication and isolation | `JwtConfiguration.java:18-39` loads RS256 keys and creates a fail-closed decoder if JWT settings are absent. `JwtTokenService.java:27-38` issues 15-minute tokens. `JwtSecurityConfiguration.java:21-99` uses stateless, ordered endpoint-specific chains and a deny-all fallback. `BusinessEndpointCatalog.java` enumerates protected business routes; secured facades and scoped repository predicates enforce account status, roles and merchant membership. |
| Provisioning | Initial ADMIN and merchant accounts are created through offline interactive commands, not public registration APIs (`InitialAdminProvisioner.java`, `MerchantAccountProvisioner.java`). Merchant provisioning is restricted to `paymesh_demo` and checks the actual connected database. Historical merchant values are not automatically claimed (`V8__authentication_and_merchant_memberships.sql`). |
| Webhooks | `/api/v1/webhooks/mock-razorpay` and `/api/v1/webhooks/mock-stripe` use PayMesh’s simulated HMAC-SHA256 contract, timestamp tolerance and hexadecimal signatures; they do not implement live provider signatures (`WebhookSignatureVerifier.java:26-49`). Events are deduplicated by provider/event ID and conflicting raw payloads are rejected (V7 unique constraint and `WebhookInbox`). |
| Settlement | `SettlementAdminController.java:28-65` protects reconciliation/history/retry operations with a constant-time comparison to a separate bearer token; a missing/short configured value produces 503. The endpoints do not use JWT as a substitute. Lookup is against the local simulated gateway ledger, not a provider API. |
| Fault simulation | `DemoGatewayFaultSimulationConfiguration.java:15-48` registers the simulator only for profile `demo` plus `paymesh.demo.gateway-timeout.enabled=true`, checks database configuration before Flyway and the connected URL/database before migration, and requires settlement scheduling off. `RoutingPaymentGateway` records the actual simulated SUCCESS first; `PaymentOrchestrationServiceImpl.java:103-113` then permits the optional simulator to report TIMEOUT while preserving the actual UUID/outcome. |
| Health | `management.endpoints.web.exposure.include=health,info` (`application.properties:5`). `GET /api/v1/payments/health` returns a static `RUNNING` result and does not check PostgreSQL (`PaymentController.java:34-42`). |

The user-provided milestone reports 187 isolated tests and successful live recovery demonstrations. This read-only audit did not rerun those tests or contact the running demo application. The most recent repository report also records 187 passing tests (`PHASE-4.3.6A-FAULT-SIMULATION-REPORT.md:39-47`).

### Configuration/environment inventory

The following names are read from runtime properties/configuration; no values were inspected for this audit:

| Purpose | Environment variables / binding |
|---|---|
| Listener | `PORT` → `server.port`, default 8080 (`application.properties:2-3`). |
| PostgreSQL | `PAYMESH_DB_URL` → `spring.datasource.url` (falls back to local `paymesh_db`); `PAYMESH_DB_USER` → datasource username (falls back to `paymesh_user`); `PAYMESH_DB_PASSWORD` → required datasource password (`:8-11`). |
| JWT | `PAYMESH_JWT_PRIVATE_KEY_FILE`, `PAYMESH_JWT_PUBLIC_KEY_FILE`, `PAYMESH_JWT_ISSUER`, `PAYMESH_JWT_AUDIENCE` (`:31-36`). All absent means login returns 503 and protected JWT APIs cannot authenticate; partial/invalid key configuration fails closed. |
| Webhooks | `PAYMESH_RAZORPAY_WEBHOOK_SECRET`, `PAYMESH_STRIPE_WEBHOOK_SECRET` (`:20-22`); blank defaults cause endpoint 503. |
| Settlement | `PAYMESH_SETTLEMENT_ADMIN_TOKEN` (blank default), `PAYMESH_SETTLEMENT_SCHEDULING_ENABLED` (false default), `PAYMESH_SETTLEMENT_POLL_MS` (30000 default) (`:23-26`). |
| Demo fault | `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED` (false default); additionally requires Spring profile `demo` and guarded local database (`:28-29`). |
| Login limiter | `PAYMESH_LOGIN_MAX_ATTEMPTS` (10), `PAYMESH_LOGIN_WINDOW_SECONDS` (60), `PAYMESH_LOGIN_MAX_CLIENTS` (10000) (`:37-39`). |
| Offline merchant provisioning | `PAYMESH_DEMO_DB_URL`, `PAYMESH_DB_USER`, and `PAYMESH_DB_PASSWORD` are read by `MerchantAccountProvisioner.java:24-31`; `PAYMESH_DEMO_DB_URL` is not an application datasource property. |
| Test harness only | `PAYMESH_ISOLATED_TEST_PORT`, `PAYMESH_TEST_DB_DATA_DIRECTORY`; the harness sets isolated `PAYMESH_DB_URL`, user and password itself (`scripts/test-isolated.sh:4-32`). |

Other shell names such as `PAYMESH_MERCHANT_JWT` used in reports are operator convenience variables, not application configuration bindings.

## C. Documentation gaps and mismatches

### H-01 — Existing API examples do not authenticate and no longer match current routes

`README-DEPLOY.md:36-47` creates/processes/payments/refunds with unauthenticated `curl`; it omits JWT on protected routes and its bodyless refund POST omits both the required `Idempotency-Key` and `{"amount":...}` body. `README-WEBHOOKS.md:39-47,90-97` likewise creates, processes and reads gateway history without JWT. `README-REFUNDS.md:7-15` omits JWT from POST and GET examples. The source requires JWT for these business routes (`BusinessEndpointCatalog.java:11-20`, `JwtSecurityConfiguration.java:33-43`); refund POST requirements are explicit in `RefundController.java:23-30`. These commands return 401 or 400 rather than demonstrating the documented flow.

`README-DEPLOY.md:49-50` says current endpoints are unauthenticated and authentication/merchant isolation still need implementation. This is contradicted by current security configuration. Its description of V1–V5-only refunds and lack of partial refunds (`README-DEPLOY.md:5-10`) is also stale relative to V6 and V8. The same document recommends bare `mvn clean test` (`:17,52-53`); README-REFUNDS gives a manual database URL/port followed by bare Maven (`README-REFUNDS.md:52-60`). The current isolation contract is `bash scripts/test-isolated.sh`; direct Maven runs fail closed unless the script's marked test environment is present (`scripts/test-isolated.sh:4-33`, `IsolatedDatabaseGuard`).

**Recommended correction:** replace these examples with current login/token handling, role/merchant requirements, payment request schema, processing, refund amount/key schema, and protected history requests. Use a supported merchant account and avoid fixed payment IDs or reusable idempotency keys. Explicitly mark all example payment requests as creating records.

### Documentation note — see M-09 below

`README-ACCOUNTS.md:3-6,129-133` says JWT/business-route authentication does not exist, despite its later merchant provisioning section and the current auth source. `README-WEBHOOKS.md:79-85` and `PHASE-4.3.6-WEBHOOK-DEMO-PLAN.md:54-58,340` state that no deterministic timeout/recovery request exists; the later `PHASE-4.3.6A-FAULT-SIMULATION-REPORT.md` documents the implemented reserved-customer scenario. `README-WEBHOOKS.md:24` describes V7 but omits V8. `README-BUSINESS-SECURITY.md:104-107` reports an earlier 156-test run, while the user-provided current baseline and Phase 4.3.6A report say 187.

**Recommended correction:** label phase artifacts as historical snapshots, link to the latest authoritative runbook, and remove current-state test counts from evergreen docs (or maintain a single current verification section).

### L-01 — API contract details are split across README files, with no OpenAPI contract

`README-BUSINESS-SECURITY.md:8-36` has a useful endpoint/authorization matrix, but request schemas, error semantics, and curl flows are split across JWT, refunds, webhooks, and deployment docs. `README-JWT.md:26-34` names login fields but provides no exact request example. `pom.xml:23-85` has no OpenAPI/springdoc dependency and no `openapi.yaml` is tracked.

**Recommended correction:** create one API reference/OpenAPI document with all current paths, body schemas, auth schemes (JWT, HMAC, settlement bearer), 401/403/404/409/413 responses, and runnable sanitized examples; link to it from focused READMEs.

## D. Docker and environment configuration gaps

### H-02 — Current Compose configuration cannot run the secured demo flows and is not safe to publish

`compose.yaml:16-27` starts the backend with only database settings. It supplies no JWT private/public key paths, issuer/audience, webhook secrets, or settlement token. Application defaults for JWT and those credentials are blank (`application.properties:20-36`), so login is unavailable (503), webhook/settlement operations fail closed (503), and protected business calls cannot authenticate. The Compose mapping `8080:8080` (`compose.yaml:22-23`) binds the web application over plain HTTP to all host interfaces by default. Business APIs remain protected in source, but this broad unencrypted publication is not suitable for a public deployment.

The backend container also has no health check, and Compose health-checks only PostgreSQL (`compose.yaml:11-21`). The `.env.example` contains only a database-password placeholder, not the runtime configuration needed to demonstrate authenticated APIs (`.env.example:1`).

**Recommended correction:** for local-only compose, bind backend ports to loopback and add an explicit demo/local configuration workflow that sources secrets from an approved local secret store. For any external deployment, terminate TLS at a trusted ingress, supply actual secret-file/secret-manager configuration, and document service health/readiness. Do not add credentials to the tracked `.env.example`.

### H-03 — The current backend-in-container topology is incompatible with the guarded demo database target

The guard accepts only `jdbc:postgresql://localhost[:port]/paymesh_demo` or `127.0.0.1` (`DemoDatabaseGuard.java:10-27`) and confirms both JDBC metadata URL and `SELECT current_database()` (`:30-44`). The demo profile applies this guard before Flyway (`DemoGatewayFaultSimulationConfiguration.java:25-48`). Current Compose instead points the backend container at `jdbc:postgresql://db:5432/paymesh_db` (`compose.yaml:24-27`). A container using `db` is deliberately rejected if simulation is enabled; changing it to `127.0.0.1` inside the backend container would target the backend container’s own loopback, not the PostgreSQL service. The current Compose stack also has no dedicated `paymesh_demo` database.

**Safe local architecture:** keep the guard unchanged. Run only a dedicated PostgreSQL service/container for `paymesh_demo`, with a distinct named volume and its host port bound to loopback (for example `127.0.0.1:5433:5432`). Run the Spring Boot demo process on the host with `PAYMESH_DB_URL=jdbc:postgresql://127.0.0.1:5433/paymesh_demo`, the demo profile/property, existing secret/key settings, and scheduling disabled. The application then sees an allowed loopback URL and still verifies `current_database()`. Do not use or attach the demo volume to `paymesh_db`. Keep the backend-in-container Compose profile’s simulation disabled unless a separately reviewed network/guard design is adopted; do not permit arbitrary hostnames in the guard.

### M-01 — Initial ADMIN provisioning has no database-target confirmation/guard

`InitialAdminProvisioner.java:28-30,49-65` disables Flyway and starts a non-web context, but its ordinary command path uses normal datasource configuration without validating a database allow-list or checking the actual database name. `application.properties:9-11` falls back to local `paymesh_db`. By comparison, `MerchantAccountProvisioner.java:24-31,51-56` checks the loopback demo URL and connected database before writes. An authorized operator can therefore provision an ADMIN into whichever database is configured, including the default target, by running the offline command.

**Recommended correction:** require an explicit intended target/confirmation for the initial ADMIN command and verify the actual database identity before the write. Keep the command offline and preserve the existing no-credentials-in-arguments protections. For non-demo production provisioning, the allowed target should be deployment-configured rather than hard-coded to `paymesh_demo`.

### M-02 — Runtime startup and schema migration use one configured datasource identity

`application.properties:6,9-16` leaves Flyway enabled by default and uses the application datasource; `compose.yaml:6-8,24-27` configures one database user for both application and schema ownership. Normal application startup can apply pending migrations with that runtime identity. No separate migration job/credential is described or tracked.

**Recommended correction:** production deployment should run Flyway as an explicit one-shot migration job with a migration credential, then run the app with a least-privilege runtime role. Document backup/restore and migration ordering; do not disable migrations without providing that separate step.

### M-03 — Health checks do not establish application readiness

`PaymentController.java:34-42` always returns `RUNNING` without database checks. Actuator exposes health/info (`application.properties:5`), but Compose checks only the database, not the backend (`compose.yaml:11-21`). No explicit liveness/readiness probes or groups are configured. `/actuator/health` can report aggregate health, but an HTTP status from `/api/v1/payments/health` is not evidence that payment storage is usable.

**Recommended correction:** define and document liveness/readiness semantics, configure deployment health checks, and ensure any newly exposed actuator subpaths receive explicit endpoint-catalog authorization rules. Keep health output minimal and never include secrets or connection details.

### M-04 — SQL logging is enabled in the base configuration

`application.properties:15-16` sets `spring.jpa.show-sql=true` and formatted SQL for every profile. SQL text is not itself a password, but verbose database logs add operational noise and can expose query structure; future binding/logging changes can expose financial/customer values.

**Recommended correction:** default SQL logging off and enable it only in an explicit local development profile. Ensure production logging never records SQL bind values or request credentials.

### M-05 — Ignore rules are not tracked and do not cover key files

The Git inventory contains no tracked `.gitignore`; a repository-parent `../.gitignore` exists locally but is untracked. Its entries ignore `.env` (`../.gitignore:16-18`) but do not ignore PEM/private-key or local secret directories. No key/certificate/password file matched the tracked-file inventory; `.env.example` contains only a placeholder. `.dockerignore` excludes `.env`, `.git` and build output (`.dockerignore:1-5`), and the current Dockerfile copies only `pom.xml` and `src` (`Dockerfile:3-4`), so no such secret file was found in the current image build context paths.

**Recommended correction:** add and track a repository-root ignore file covering `.env`, private-key/certificate formats, local secret mounts, generated key directories, and backups. Keep `.env.example` tracked with placeholders only. Continue copying only explicit build inputs or add equivalent ignore protections before any broad `COPY .` change.

### M-06 — No tracked CI workflow; Docker build skips tests

No GitHub Actions, GitLab CI, Jenkins, or Azure pipeline file is tracked. The isolation script is robust for local use (`scripts/test-isolated.sh:4-33` creates a marked temporary cluster on a non-5432 port, verifies its data directory, invokes `mvn clean test`, and stops PostgreSQL in an EXIT trap). The Dockerfile builds with `mvn -B -DskipTests package` (`Dockerfile:1-5`), so `docker compose up --build` does not verify tests.

**Recommended correction:** add a CI workflow that runs the existing isolation script against a supported Java 21/PostgreSQL toolchain, publishes test results, and separately builds the image only after success. Do not replace the isolation guard with a bare Maven command pointed at an application database.

### M-07 — Login throttling is process-local and settlement authentication is one shared static token

`README-JWT.md:64-82` describes the in-memory, per-instance login limiter and its reset on restart; a multi-instance deployment therefore needs a shared ingress/distributed budget. Settlement uses one static bearer token (`SettlementAdminController.java:23-25,59-65`), separate from JWT as intended, with no per-operator identity or built-in rotation overlap.

**Recommended correction:** retain the auth boundary, source the token from managed secret storage, rotate it through a documented controlled rollout, restrict settlement routes at ingress/network policy, and use a shared or ingress login rate budget for multi-instance deployment.

### M-08 — Container defaults are development-grade

`Dockerfile:1,6-10` uses floating Maven/Temurin and PostgreSQL image tags (`Dockerfile:1,6`; `compose.yaml:3`), has no non-root `USER` directive, and defines no runtime health check. These are not proof of a vulnerability in the local setup, but they leave image provenance, patch level, privilege reduction, and orchestration health unspecified.

**Recommended correction:** pin supported image versions (and preferably digests), run as a dedicated non-root UID, use a minimal runtime image, set resource/JVM limits, and provide a health check consistent with the secured health design.

### M-09 — Other documentation snapshots conflict with current implementation

Details are listed in Section C. `README-ACCOUNTS.md`, `README-WEBHOOKS.md`, `README-BUSINESS-SECURITY.md`, `README-DEPLOY.md`, and `PHASE-4.3.6-WEBHOOK-DEMO-PLAN.md` need current-state labels or updates. They should not remain the copy-paste operator guides while describing different endpoint authentication, refund schemas, migration versions, or demo capabilities.

## E. Security and secret-management findings

### Positive findings

- No production private key, webhook secret, settlement token, or operational password file was found in the tracked Git file inventory. No production credential literal was found in application configuration. The `.env.example` value is visibly a replacement placeholder.
- `JwtKeyMaterial` reads bounded local PKCS#8/X.509 PEM files, requires matching RSA moduli of at least 2048 bits, proves the pair, and suppresses key/parser contents in failures (`JwtKeyMaterial.java:24-55`). JWT is explicitly RS256 with issuer/audience/temporal and current-account validation (`JwtConfiguration.java:32-39`, `JwtTokenService.java:27-38`).
- Webhook secrets have no usable default; the verifier requires at least 32 characters, enforces a ±300-second delivery timestamp window, signs timestamp plus exact body bytes, parses hex, and compares in constant time (`application.properties:20-23`, `WebhookSignatureVerifier.java:26-49`).
- The settlement token is separate from JWT, compared in constant time, and missing/short server configuration fails with 503 (`SettlementAdminController.java:59-65`).
- Demo timeout activation is disabled by default and guarded to exact local `paymesh_demo`; ordinary gateway behavior has no simulator bean unless both profile and property match (`application.properties:28-29`, `DemoGatewayFaultSimulationConfiguration.java:15-48`).
- No live provider SDK/client or fallback behavior is present in the reviewed gateway classes. These are mock gateways and the settlement lookup is a local ledger only.

### M-10 — Webhook runbook places the settlement token in curl arguments

The settlement commands in `README-WEBHOOKS.md:71-76,116-119` interpolate `PAYMESH_SETTLEMENT_ADMIN_TOKEN` directly into `curl -H` arguments. Depending on platform/process inspection and diagnostics, expanded command-line arguments can expose the bearer credential to local process observers. The endpoint correctly uses constant-time comparison; this is an unsafe example, not an authentication bypass.

**Recommended correction:** change examples to provide the Authorization header through a protected curl config/stdin or a dedicated client that reads the secret from the environment without putting its value in argv or terminal output. Avoid shell tracing and never echo the expanded token.

### M-11 — Refund total safety depends on all writers following the service lock protocol

The application locks the payment before checking refund idempotency and totals, but the documentation explicitly notes there is no cross-table CHECK constraint (`README-REFUNDS.md:32-39`). Direct SQL or a future writer that bypasses this protocol can violate the aggregate refund ceiling.

**Recommended correction:** keep direct write privileges unavailable to ordinary operators/integrations, make the secured refund service the only supported write path, and either add database-enforced serialization/aggregate protection or formally constrain and audit every other refund writer before production use.

## F. Proposed safe local Docker deployment architecture

1. Preserve `DemoDatabaseGuard` as implemented. It is intentionally a loopback-only guard; do not add `db`, `host.docker.internal`, arbitrary DNS names, or production hosts to the allowed pattern.
2. Add a separate **database-only** demo Compose file (suggested `compose.demo.yaml`). Use database name `paymesh_demo`, dedicated `paymesh_demo_user`, a volume distinct from the normal `paymesh_db` volume, and a host port bound only to `127.0.0.1` (for example host port 5433 mapped to container 5432). It should not contain the backend service.
3. Run the Spring Boot demo process on the host. Supply `PAYMESH_DB_URL=jdbc:postgresql://127.0.0.1:5433/paymesh_demo`, the matching demo database user/password through local secret configuration, `SPRING_PROFILES_ACTIVE=demo`, `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED=true`, and `PAYMESH_SETTLEMENT_SCHEDULING_ENABLED=false`. Use the existing secret source for JWT key files, issuer/audience, both HMAC secrets and settlement token. Set the listener port to the intended local demo port (for example `PORT=18080`). The application verifies both its configured URL and actual database name before Flyway migration.
4. Keep the ordinary backend-in-container Compose profile separate, with the simulation property false and its normal internal service DNS. For a production/container deployment, use TLS ingress, secret-manager-backed settings, a separate migration job, non-root image, and explicit readiness/health policy.
5. Do not copy secrets into the Docker build context, tracked `.env`, command-line arguments, curl output, or reports. The current JWT implementation accepts private/public key **file paths**; webhook/settlement values currently bind as environment strings, so container deployments needing file-mounted secrets should either use a platform secret injector or implement and test explicit `_FILE` support before claiming Compose-secret compatibility.

This architecture gives the host application the loopback URL the existing guard requires while keeping the demo database in a container and separate from the application database. It does not weaken the guard and does not assume Docker Desktop container networking behaves like host networking.

## G. Exact files to create/update in the next implementation phase

No changes to these files were made during this audit. Recommended follow-up scope:

### Documentation and operator instructions

- Update `README-DEPLOY.md` with current auth, migration and safe local/deployment posture; remove obsolete unauthenticated payment/refund curls and bare Maven test instructions.
- Update `README-WEBHOOKS.md` with the Phase 4.3.6A reserved customer selector, JWT-authenticated payment/history commands, HMAC-safe event sender, no-token output and separate settlement flow. Explain that scheduler must be disabled for the webhook-first demo.
- Update `README-REFUNDS.md` with JWT handling for every business request and a safe supported request example.
- Update `README-ACCOUNTS.md` to label Phase 2 statements historical and reference current JWT/business authorization.
- Update `README-BUSINESS-SECURITY.md` to remove the stale 156-test count or replace it with a dated current verification reference.
- Add a canonical `API-REFERENCE.md` or `openapi.yaml` and link it from the focused README files.
- Mark `PHASE-4.3.6-WEBHOOK-DEMO-PLAN.md` as the superseded pre-fault-simulation plan and link to `PHASE-4.3.6A-FAULT-SIMULATION-REPORT.md`.

### Deployment and configuration

- Create `compose.demo.yaml` for the loopback-published `paymesh_demo` PostgreSQL-only service and distinct volume; keep backend host-run for the guarded simulation.
- Update `compose.yaml` for safe local port binding, runtime secrets, backend health/readiness, and non-demo profile behavior; do not enable demo fault simulation there.
- Update `Dockerfile` for pinned images, non-root runtime, and an appropriate health check.
- Add and track repository-root `.gitignore` rules for `.env`, key/certificate files, local secrets, backups and generated artifacts.
- Add an explicit production configuration file such as `src/main/resources/application-prod.properties` (or equivalent documented env configuration) to disable SQL output, require explicit DB config, and define health/readiness behavior.
- Add a migration/deployment entry point such as `compose.migrate.yaml` or a documented `scripts/migrate.sh`, with a separate migration identity and ordering contract.
- If Docker secret files are the deployment target, update the relevant configuration classes and `application.properties` to support explicit secret-file paths for HMAC and settlement credentials; add tests for missing, oversized, unreadable and valid files. Do not imply Docker secrets are wired into the current application automatically.

### Verification pipeline

- Create `.github/workflows/ci.yml` (or the repository’s chosen CI equivalent) to run `bash scripts/test-isolated.sh` with Java 21 and required PostgreSQL binaries before building/publishing a container image.
- Extend the isolated suite only for newly changed runtime/health/secret-loading behavior; do not run CI migrations against `paymesh_db` or `paymesh_demo`.

## H. Recommended implementation order

1. Correct and reconcile all README/API claims with source; fix protected API curl examples before asking operators to use them.
2. Add the database-only demo Compose design and verify its loopback URL/actual database identity without relaxing `DemoDatabaseGuard`.
3. Harden general container defaults and secret injection; separate production/migration configuration from the local demo configuration.
4. Implement readiness/health configuration and verify exact security-catalog behavior for every newly exposed health path.
5. Add the CI workflow using only the isolated script and make container publication depend on its result.
6. Review migration rollout/backup/restore and least-privilege DB roles, then perform a separately authorized deployment review. Do not claim production readiness until that review and environment-specific validation are complete.

## I. Remaining risks and limitations

- Payment providers, refunds and reconciliation are simulated; no money moves, no real gateway API is called, and no provider fallback is implemented.
- The demo timeout must remain disabled outside the dedicated demo profile/database. The current Compose backend topology cannot enable it while preserving the loopback-only guard.
- Initial ADMIN provisioning is offline but currently relies on operator datasource configuration rather than validating an explicit target database identity.
- Flyway runs as part of normal application startup using the configured datasource identity; production least privilege and migration ordering are not encoded in deployment files.
- Login rate limiting is per-instance memory; settlement authentication is a single shared static bearer token. Production requires ingress/distributed controls and managed rotation.
- Application readiness and Docker health are incomplete; the payment health route is static.
- Refund aggregate safety is enforced through the supported locked service path, not a database aggregate constraint; all writers must preserve that protocol.
- No tracked CI/CD workflow, OpenAPI document, or demonstrated Docker build/deployment was found. This audit intentionally ran none.
- No independent live-app verification was made in this audit. The 187-test and live-demo results are provided baseline/report evidence, not fresh audit execution.

## J. Final verdict

**CONDITIONALLY READY** for controlled local development/demo only, after operators use the guarded host-run backend plus dedicated loopback-published `paymesh_demo` database and current secret configuration. **NOT READY for public or production deployment** until high-severity documentation/runtime configuration issues and the deployment hardening items above are resolved and validated in the intended environment. This is not a production certification.

## Finding totals

- Critical: **0**
- High: **3**
- Medium: **11**
- Low: **1**

The high findings are H-01 (stale unauthenticated API examples), H-02 (Compose is incomplete for secured use and publishes plain HTTP broadly), and H-03 (the current container network target cannot satisfy the demo loopback database guard).
