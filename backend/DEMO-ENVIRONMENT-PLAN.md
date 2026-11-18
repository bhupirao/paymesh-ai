# PayMesh AI demo environment plan

This is a plan based on the current backend source and configuration. It does not create a database, account, key, or secret and does not start the application. The application database `paymesh_db` is out of scope for demo setup.

## 1. Existing configuration names

`src/main/resources/application.properties` maps the following environment variables to Spring properties:

| Purpose | Environment variable | Spring property | Current behavior |
| --- | --- | --- | --- |
| PostgreSQL JDBC URL | `PAYMESH_DB_URL` | `spring.datasource.url` | Defaults to `jdbc:postgresql://localhost:5432/paymesh_db`; override it for a demo. |
| PostgreSQL login | `PAYMESH_DB_USER` | `spring.datasource.username` | Defaults to `paymesh_user`. |
| PostgreSQL password | `PAYMESH_DB_PASSWORD` | `spring.datasource.password` | Required; no default. |
| JWT RSA private PEM file | `PAYMESH_JWT_PRIVATE_KEY_FILE` | `paymesh.jwt.private-key-file` | PKCS#8 RSA private key file path; no default key. |
| JWT RSA public PEM file | `PAYMESH_JWT_PUBLIC_KEY_FILE` | `paymesh.jwt.public-key-file` | X.509 RSA public key file path; no default key. |
| JWT issuer | `PAYMESH_JWT_ISSUER` | `paymesh.jwt.issuer` | Required for JWT configuration. |
| JWT audience | `PAYMESH_JWT_AUDIENCE` | `paymesh.jwt.audience` | Required for JWT configuration. |
| Mock Razorpay webhook HMAC secret | `PAYMESH_RAZORPAY_WEBHOOK_SECRET` | `paymesh.webhooks.razorpay-secret` | Empty by default; webhook verification fails closed until configured. |
| Mock Stripe webhook HMAC secret | `PAYMESH_STRIPE_WEBHOOK_SECRET` | `paymesh.webhooks.stripe-secret` | Empty by default; webhook verification fails closed until configured. |
| Settlement bearer token | `PAYMESH_SETTLEMENT_ADMIN_TOKEN` | `paymesh.settlement.admin-token` | Empty by default; settlement routes return unavailable until configured. |

Related existing runtime settings are `PORT` (`server.port`, default `8080`), `PAYMESH_SETTLEMENT_SCHEDULING_ENABLED` (default `false`), `PAYMESH_SETTLEMENT_POLL_MS` (default `30000`), and login rate-limit settings `PAYMESH_LOGIN_MAX_ATTEMPTS` (10), `PAYMESH_LOGIN_WINDOW_SECONDS` (60), and `PAYMESH_LOGIN_MAX_CLIENTS` (10000). Do not use the current datasource default for a demo.

## 2. Dedicated PostgreSQL database commands

These commands target only the PostgreSQL maintenance database named `postgres` for role/database creation, then direct the application to `paymesh_demo`. They do not connect to `paymesh_db`. Run them only when an operator later authorizes environment setup; they were not run for this plan. The `postgres` OS/database administrator account must have permission to create roles and databases.

Open an interactive session to the maintenance database:

```bash
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

At the `psql` prompt, create the dedicated demo role and database, set the role password using `psql`'s hidden prompt, and exit:

```sql
CREATE ROLE paymesh_demo_user LOGIN;
CREATE DATABASE paymesh_demo OWNER paymesh_demo_user;
\password paymesh_demo_user
\q
```

For a local backend process, set the demo-only connection variables in its shell. `read -s` asks for the password without echoing it; do not put a real password in shell history or commit it:

```bash
export PAYMESH_DB_URL='jdbc:postgresql://127.0.0.1:5432/paymesh_demo'
export PAYMESH_DB_USER='paymesh_demo_user'
read -s PAYMESH_DB_PASSWORD
export PAYMESH_DB_PASSWORD
```

Before any later startup, inspect `PAYMESH_DB_URL` and confirm it ends in `/paymesh_demo`. The application has Flyway enabled by default, so a normal application startup will apply pending migrations to the configured database. A demo startup must use the explicit demo URL above. Do not use the application's default URL, and do not use `paymesh_db` in `psql`, `createdb`, Compose, or application settings. No database commands were executed while preparing this document.

## 3. Intel Mac RSA key generation

Generate a 3072-bit RSA key pair under the operator's private config directory, outside the repository. These are future setup commands and were not run. `umask` and directory permissions limit access to the current user; the public key may be mounted alongside the private key for application validation.

```bash
umask 077
mkdir -p "$HOME/.config/paymesh-demo"
chmod 700 "$HOME/.config/paymesh-demo"
openssl genpkey -algorithm RSA \
  -pkeyopt rsa_keygen_bits:3072 \
  -out "$HOME/.config/paymesh-demo/jwt-private.pem"
chmod 600 "$HOME/.config/paymesh-demo/jwt-private.pem"
openssl pkey \
  -in "$HOME/.config/paymesh-demo/jwt-private.pem" \
  -pubout \
  -out "$HOME/.config/paymesh-demo/jwt-public.pem"
chmod 644 "$HOME/.config/paymesh-demo/jwt-public.pem"
```

Configure file paths and non-secret JWT identifiers for a local process:

```bash
export PAYMESH_JWT_PRIVATE_KEY_FILE="$HOME/.config/paymesh-demo/jwt-private.pem"
export PAYMESH_JWT_PUBLIC_KEY_FILE="$HOME/.config/paymesh-demo/jwt-public.pem"
export PAYMESH_JWT_ISSUER='https://paymesh-demo.local'
export PAYMESH_JWT_AUDIENCE='paymesh-demo-api'
```

Keep the private key outside Git, backups shared with untrusted users, and container images. For Compose, mount the containing directory read-only and configure the container-side file paths. Do not commit PEM files or put private-key contents in environment variables.

## 4. Existing first-ADMIN provisioning command

`README-ACCOUNTS.md` documents the only current initial ADMIN entry point. After an operator has built the jar and configured the intended database connection, the exact command is:

```bash
java -Dloader.main=com.paymesh.backend.security.accounts.InitialAdminProvisioner \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

It is an interactive offline console command: it requires an explicit confirmation phrase, prompts for the login and password twice without echo, refuses to run without a secure console, disables Flyway and settlement scheduling, validates the existing schema, and pins a non-web application context. It does not accept password arguments or environment-password fallback. It refuses if an ADMIN role assignment or successful initial-provision audit already exists. This command provisions only the first ADMIN; it is not a merchant-user or membership provisioning command. It was not executed.

## 5. Merchant/account provisioning capabilities and demo blocker

The `AccountAdministration` service supports these operations when passed its opaque, successfully authenticated `AuthenticatedAccount` principal:

| Operation | Existing service method | Policy enforced by implementation |
| --- | --- | --- |
| Create a MERCHANT account | `createMerchantAccount(actor, login, password)` | Privileged transaction checks current actor status/ADMIN role, hashes the password, assigns the MERCHANT role, and audits the operation. |
| Register a merchant | `registerMerchant(actor, merchantId)` | Creates/activates an unverified merchant registry record; does not claim ownership or grant membership. |
| Verify merchant ownership | `verifyMerchantOwnership(actor, merchantId, reference)` | ADMIN attestation with a bounded review reference; records verifier and audit metadata. |
| Assign merchant membership | `assignVerifiedMembership(actor, userId, merchantId)` | Requires an enabled MERCHANT user and an active, verified merchant; records membership. |
| Revoke membership | `revokeMembership(actor, userId, merchantId)` | Revokes access while retaining history and audit data. |

There is **no supported HTTP endpoint, command-line provisioner, or other operator-facing entry point** for these post-bootstrap methods. They are service methods, not a safe standalone provisioning interface. In particular, the repo has no documented way to create a demo merchant, complete ownership verification, create a MERCHANT login, and assign that login to the merchant. Historical merchants backfilled by V8 deliberately remain unverified/unclaimed, and role reference rows alone do not provision accounts.

This is a blocker for a merchant-authenticated end-to-end demo. The minimal recommended addition, for separate approval and implementation, is an offline, interactive merchant-provisioning command. It should authenticate an existing ADMIN through the internal credential service (never accept an actor UUID/role as proof), prompt securely for the merchant login/password and merchant ID, require an operator-supplied external ownership-review ticket/reference, and invoke the existing `AccountAdministration` operations in a safe audited sequence: register if needed, verify, create the MERCHANT account, then assign membership. It should use the same non-web context hardening and database safeguards as initial ADMIN provisioning, never run at normal application startup, and be idempotent or stop clearly on partial completion. Do not expose a public registration/bootstrap API or make historical merchant rows automatically verified.

Existing payment rows retain their merchant IDs. The V8 backfill does not establish verified ownership. Payments should remain inaccessible to a MERCHANT principal until an ADMIN has verified the corresponding merchant and assigned an active membership. Do not rewrite payment ownership to make a demo convenient. The create-payment request accepts a client-provided `merchantId`; the authenticated business service must validate that the current MERCHANT has active verified membership for that exact ID. Do not treat the request field as ownership proof.

## 6. Existing API request schemas

The following are the source-level schemas and routes currently present; they are not proposed new endpoints.

### Login

`POST /api/v1/auth/login`, JSON body:

```json
{
  "login": "merchant login",
  "password": "account password"
}
```

`login` is required, nonblank, and at most 255 characters. `password` is required and at most 72 characters; it is write-only in JSON metadata. Successful login returns a bearer access token response. Invalid credentials return a generic 401.

### Create payment

`POST /api/v1/payments`, requires the `Idempotency-Key` header and `PaymentRequest` JSON:

```json
{
  "merchantId": "verified merchant identifier",
  "amount": 200.00,
  "currency": "INR",
  "customerId": "customer-123",
  "paymentMethod": "UPI"
}
```

All fields are required. `merchantId`, `currency`, `customerId`, and `paymentMethod` must be nonblank. `amount` must be at least `0.01`, with up to 12 integer digits and 2 fractional digits. The example values are illustrative, not provisioned demo data.

### Process payment

`POST /api/v1/payments/{paymentId}/process`. The payment UUID is in the path; no request body is declared. Gateway routing remains internal to the existing orchestration service.

### Gateway history

`GET /api/v1/payments/{paymentId}/gateway-transactions`. No request body. It returns the payment's gateway transaction records after the controller first loads/authorizes the payment.

### Refund

`POST /api/v1/payments/{paymentId}/refund`, requires `Idempotency-Key` and:

```json
{
  "amount": 200.00
}
```

`amount` is required, positive (minimum `0.01`), at most 17 integer digits and 2 fractional digits.

### Webhook

`POST /api/v1/webhooks/mock-razorpay` or `POST /api/v1/webhooks/mock-stripe`. The body is raw UTF-8 JSON bytes with `Content-Type: application/json`; the required headers are `X-Paymesh-Timestamp` and `X-Paymesh-Signature`. The JSON decoded by the ingress is:

```json
{
  "eventId": "provider-event-123",
  "paymentId": "8a8d7317-e039-455a-bfa4-839eedd99337",
  "gatewayTransactionId": "replace-with-gateway-transaction-uuid",
  "status": "SUCCESS",
  "occurredAt": "2026-11-12T10:00:00Z"
}
```

`eventId` is nonblank and at most 255 characters; both IDs are UUIDs; status is one of `SUCCESS`, `FAILED`, `TIMEOUT`, or `UNKNOWN`; `occurredAt` is an ISO-8601 instant. The signature is HMAC-SHA256 over the exact bytes of `timestamp + "." + raw request body`, using the provider-specific secret. Keep webhook HMAC authentication independent from JWT; do not reserialize the body before verification.

### Reconciliation

Manual reconcile is `POST /api/v1/settlement/payments/{paymentId}/reconcile`. It has no request body and uses `Authorization: Bearer <PAYMESH_SETTLEMENT_ADMIN_TOKEN>`. Reconciliation history is `GET /api/v1/settlement/payments/{paymentId}/reconciliation`, same authorization and no body. The companion settlement endpoints are `GET /api/v1/settlement/payments/{paymentId}/webhooks` and `POST /api/v1/settlement/webhooks/{id}/retry` (no body); these also use the settlement token. This credential remains separate from application JWT.

## 7. Documentation corrections required

### `README-DEPLOY.md`

- Replace stale migration/authentication descriptions with the current V8 schema, JWT configuration, and security behavior.
- Remove or clearly mark examples that call business APIs without a bearer JWT; login is the only public auth route.
- Document all datasource, RSA key-file, issuer/audience, webhook-secret, and settlement-token variables listed above.
- Direct local demo setup to the dedicated `paymesh_demo` URL and clearly warn that the datasource property otherwise defaults to `paymesh_db`.
- Document the first-ADMIN offline command, its interactive requirements, and the absence of a merchant-provisioning entry point.
- Remove `mvn clean test` as a generic deployment/demo command; use the project-approved isolated test workflow when testing is required.
- Explain that the existing Compose file still names and targets `paymesh_db` and must be changed before it is safe for a dedicated demo.

### `README-WEBHOOKS.md`

- Update business API examples to authenticate with a valid JWT; do not add JWT to the HMAC webhook requests.
- State that the current account services have no supported merchant provisioning interface, so a merchant flow cannot be completed until a separately approved offline provisioner exists and ownership has been explicitly verified.
- Show exact signature construction over timestamp plus the original raw body, provider-specific environment secret names, timestamp tolerance, and required headers.
- Correct the demo sequence so an event is sent for a valid payment/gateway transaction in a state where webhook handling is meaningful; current examples that process a mock payment to terminal `SUCCESS` first may result in an ignored webhook/reconciliation path.
- Document settlement reconciliation/history/retry calls with the separate settlement bearer token, not the JWT.
- State that mock gateway lookup is simulated and that secrets must be configured externally, never committed.

## 8. Compose configuration changes required

Current `compose.yaml` hardcodes `paymesh_db`/`paymesh_user`, uses the persistent volume `paymesh_pgdata`, exposes port 8080, and passes only database settings to the backend. It does not pass JWT configuration, mount key files, or pass webhook/settlement secrets. It is therefore not a safe dedicated demo configuration as-is.

For a future, separately approved Compose update:

1. Parameterize the DB name, user, and volume for a dedicated demo project (`paymesh_demo`, `paymesh_demo_user`, and a distinct `paymesh_demo_pgdata`); do not reuse or rename the existing `paymesh_pgdata` volume.
2. Set the backend URL to `jdbc:postgresql://db:5432/paymesh_demo` (Compose service DNS `db`), with the demo user/password. Ensure the Postgres healthcheck checks the demo DB/user.
3. Require externally supplied nonempty values for both webhook secrets and the settlement token; do not add defaults. Keep those secrets in a local ignored env file or secret manager and out of Git.
4. Mount the RSA key directory read-only into the backend and point `PAYMESH_JWT_PRIVATE_KEY_FILE` and `PAYMESH_JWT_PUBLIC_KEY_FILE` to the mounted container paths. Supply issuer/audience values.
5. Use a distinct Compose project name and isolated named volume for the demo. Avoid `down -v` unless the operator explicitly intends to destroy the demo database; never attach the application volume.
6. Consider binding the demo HTTP port to loopback (`127.0.0.1`) and putting TLS at a trusted local proxy if requests leave the machine. Do not publish a plaintext service publicly.
7. Keep settlement scheduling opt-in unless the demo explicitly needs it, and retain bounded polling and webhook/request-body protections.
8. Add a startup/configuration check or documented preflight that prints/validates the selected database name without printing secrets and refuses a demo profile whose datasource is not `paymesh_demo`.
9. Do not attempt to run a merchant demo until the missing offline merchant provisioning workflow is approved and implemented; no public account endpoint should be added as a shortcut.

No code, configuration, Compose file, database, account, or secret was changed or created as part of this planning document.
