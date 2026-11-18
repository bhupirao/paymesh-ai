# Controlled local demo runbook

This runbook targets a **fresh, separate** guarded `paymesh_demo` database in the database-only Compose project. PostgreSQL is published on loopback port 15432; the backend runs on the host at loopback port 18080. It does not use the existing host PostgreSQL service on port 5432, import/copy existing data, or use a Compose backend container. Existing databases, accounts, and payment records remain untouched. The demo timeout simulation is explicitly enabled only for this demo profile. Do not use this setup as a production deployment.

## A. Existing local configuration directory

The operator configuration directory is `$HOME/.config/paymesh-demo/` and is outside the repository. The existing files are:

- `demo.env` — non-secret demo configuration.
- `secrets.env` — credentials/secrets; do not display or commit this file.
- `demo-compose.env` — new configuration for the fresh port-15432 PostgreSQL
  container and host-run demo. Create it from `demo-compose.env.example`; do not
  overwrite existing `demo.env` or database configuration.
- `helpers.sh` — shell helper definitions. Source it in each new shell before relying on functions such as `paymesh_login`.
- `jwt-private.pem` and `jwt-public.pem` — RS256 key pair. The private key must remain private.

The directory and secret-bearing files are locally protected. Do not run `cat`, `env`, shell tracing (`set -x`), or commands that print secret contents. To load the configured environment in bash/zsh:

```bash
set -a
source "$HOME/.config/paymesh-demo/demo.env"
source "$HOME/.config/paymesh-demo/secrets.env"
set +a
source "$HOME/.config/paymesh-demo/helpers.sh"
```

For a fresh terminal, repeat these commands. If `paymesh_login` is unavailable, the helper file was not sourced in that shell; use the getpass login fallback below. Never inspect or echo the JWT or secret variables.

## B. Required settings and database target

The runtime must use:

- `PAYMESH_DEMO_DB_URL` and `PAYMESH_DB_URL` set to
  `jdbc:postgresql://127.0.0.1:15432/paymesh_demo`.
- `PAYMESH_DB_USER`, `PAYMESH_DB_PASSWORD` for that dedicated database.
- `PAYMESH_DEMO_DB_PASSWORD` for the PostgreSQL container. Set it to the same
  newly chosen value as `PAYMESH_DB_PASSWORD` for the host backend.
- `SPRING_PROFILES_ACTIVE=demo`.
- `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED=true`.
- `PAYMESH_SETTLEMENT_SCHEDULING_ENABLED=false`.
- `PORT=18080`.
- `SERVER_ADDRESS=127.0.0.1` so the host-run server binds only to loopback.
- `PAYMESH_JWT_PRIVATE_KEY_FILE` and `PAYMESH_JWT_PUBLIC_KEY_FILE` pointing to the two PEM files above; matching `PAYMESH_JWT_ISSUER` and `PAYMESH_JWT_AUDIENCE`.
- Existing `PAYMESH_RAZORPAY_WEBHOOK_SECRET`, `PAYMESH_STRIPE_WEBHOOK_SECRET`, and `PAYMESH_SETTLEMENT_ADMIN_TOKEN` from the protected secret source.

The JWT file variable names are `PAYMESH_JWT_PRIVATE_KEY_FILE` and `PAYMESH_JWT_PUBLIC_KEY_FILE`. The secret values are never shown here. Webhook HMAC secrets and settlement token must each be configured securely; this source reads environment configuration and the docs do not claim Docker secret-file support for those values.

Create a new external environment file from the tracked placeholder example;
do not overwrite existing local files. Load it after existing non-database
secrets so its explicit port-15432 database configuration wins. Do not enable
shell tracing:

```bash
umask 077
cp demo-compose.env.example "$HOME/.config/paymesh-demo/demo-compose.env"
${EDITOR:-vi} "$HOME/.config/paymesh-demo/demo-compose.env"
set +x
set -a
source "$HOME/.config/paymesh-demo/secrets.env"
source "$HOME/.config/paymesh-demo/demo-compose.env"
set +a
python3 - <<'PY'
import os, re, sys
url = os.environ.get('PAYMESH_DB_URL', '')
ok = re.fullmatch(r'jdbc:postgresql://127\.0\.0\.1:15432/paymesh_demo', url)
if not ok:
    raise SystemExit('Refusing startup: expected the dedicated loopback port-15432 paymesh_demo target')
PY
export PAYMESH_JWT_PRIVATE_KEY_FILE="$HOME/.config/paymesh-demo/jwt-private.pem"
export PAYMESH_JWT_PUBLIC_KEY_FILE="$HOME/.config/paymesh-demo/jwt-public.pem"
```

The two database password variables in `demo-compose.env` must be set to the
same new value. Start the database-only Compose service and wait for its health
check:

```bash
docker compose --project-name paymesh-demo-db \
  --env-file "$HOME/.config/paymesh-demo/demo-compose.env" \
  -f compose.demo.yaml up -d
docker compose --project-name paymesh-demo-db \
  --env-file "$HOME/.config/paymesh-demo/demo-compose.env" \
  -f compose.demo.yaml ps
```

This creates a new empty database and separate persistent volume. Existing
`paymesh_demo` on port 5432 and `paymesh_db` are not used. The backend's
`DemoDatabaseGuard` validates the loopback JDBC URL and actual database name
before Flyway. Keep that guard unchanged and do not accept the application
fallback target.

SQL statement output, Hibernate bind-value logging, and formatted SQL are disabled by default. Do not enable SQL diagnostics during the demo because queries can include customer or financial values.

### Database network boundary

The demo backend must connect to `127.0.0.1:15432` from the host. It cannot use
Compose DNS name `db` under `DemoDatabaseGuard`. `compose.demo.yaml` contains
PostgreSQL only; do **not** use the normal full-stack `compose.yaml` for this
guarded workflow.

## C. Start and health checks

After the new database is healthy and the environment checks above pass, start the host-run backend from the backend project root using the normal application entry point:

```bash
mvn spring-boot:run
```

This command is documentation only; it has not been executed as part of the documentation phase. Do not start a second instance if one is already running. Check both health views:

```bash
curl --fail-with-body --silent --show-error 'http://127.0.0.1:18080/api/v1/payments/health'
curl --fail-with-body --silent --show-error 'http://127.0.0.1:18080/actuator/health'
```

The payment health response is static (`service` and `status`) and does not
prove database connectivity. `/actuator/health` is aggregate health;
`/actuator/health/liveness` does not depend on PostgreSQL and
`/actuator/health/readiness` includes the database contributor. Health component
details are hidden. The payment health and health-group paths are public;
Actuator discovery and info remain ADMIN-only. None of these endpoints returns
payment records.

## D. Offline account provisioning

The existing ADMIN, merchants, and payment records remain on their original
database and are neither copied nor changed. This fresh Compose database starts
with no application accounts. To use it, provision accounts only in this new
isolated database after the application has applied V1–V8. Do not recreate or
modify accounts in the existing database. There is no public registration or
account-provisioning endpoint.

If an initial ADMIN genuinely does not exist, use the interactive offline command below with the protected demo configuration loaded. It requires `PAYMESH_DEMO_DB_URL` to be an exact loopback PostgreSQL URL for `paymesh_demo`, `PAYMESH_DB_USER=paymesh_demo_user`, and a nonblank `PAYMESH_DB_PASSWORD`. It rejects a missing/blank target, `paymesh_db`, any other database name, remote or DNS hosts, and malformed JDBC URLs before opening a database connection.

```bash
java -Dloader.main=com.paymesh.backend.security.accounts.InitialAdminProvisioner \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

It first requires the exact target confirmation `BOOTSTRAP ADMIN IN paymesh_demo`, then the existing `PROVISION INITIAL ADMIN` confirmation. Login/password prompts are interactive; passwords are not echoed, accepted as arguments, or logged. Conflicting datasource URL, user, type, JNDI, external config-location, application JSON, and alternate datasource overrides are rejected or pinned. The context pins the validated datasource URL/user, uses a direct `DriverManagerDataSource`, excludes JNDI, disables Flyway and settlement scheduling, forces non-web mode, and retains Hibernate schema validation. Before any account or audit write it verifies the actual JDBC URL, datasource type, connected database name, and database user. It does not create a database or run migrations; V8 must already exist. Repeated initial ADMIN creation is refused. Use this only for the new isolated demo database if it has no ADMIN; the existing demo ADMIN is not affected.

The existing guarded offline merchant command is:

```bash
java -Dloader.main=com.paymesh.backend.security.accounts.MerchantAccountProvisioner \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

It requires the exact `paymesh_demo` loopback target, existing current schema, `PAYMESH_DEMO_DB_URL`, expected demo database user, and securely supplied database password. It authenticates an existing ADMIN, prompts for external ownership-review reference and merchant credentials, and explicitly confirms provisioning. It does not create the database, run migrations, or change historical payment ownership. Only use it if the merchant/account is actually missing. Existing demo accounts already exist and should not be recreated.

## E. Merchant login and token handling

The login body is `{"login":"...","password":"..."}`. Tokens are RS256 and expire after 15 minutes. There is no refresh endpoint: obtain a replacement by logging in again. Use the already sourced `paymesh_login` helper if its local implementation is understood, or the following fallback, which prompts for the password without echo and captures the token without printing it:

```bash
read -r -p 'Merchant login: ' PAYMESH_LOGIN_NAME
MERCHANT_TOKEN="$(python3 - "$PAYMESH_LOGIN_NAME" <<'PY'
import getpass, json, sys, urllib.request
login = sys.argv[1]
password = getpass.getpass('Merchant password: ')
request = urllib.request.Request(
    'http://127.0.0.1:18080/api/v1/auth/login',
    data=json.dumps({'login': login, 'password': password}).encode(),
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request) as response:
    sys.stdout.write(json.load(response)['accessToken'])
PY
)"
unset PAYMESH_LOGIN_NAME
```

Login once using Merchant A and store its access token as `MERCHANT_A_TOKEN`; repeat with Merchant B to set `MERCHANT_B_TOKEN`. Do not print either variable. All examples pass tokens through curl's config input rather than `-H "Authorization: Bearer $TOKEN"`.

## F. Normal payment routing and idempotency

Payment creation requires a verified merchant, a JWT, an `Idempotency-Key`, and this body shape:

```json
{"merchantId":"DEMO_MERCHANT_A","amount":200.00,"currency":"INR","customerId":"customer-unique","paymentMethod":"UPI"}
```

Use a newly generated unique key and customer ID for each new demo payment. Create payment (state-changing; inspect the result before proceeding):

```bash
PAYMENT_A_CREATE_KEY="demo-payment-a-$(python3 -c 'import uuid; print(uuid.uuid4())')"
curl --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_A_TOKEN") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header 'Content-Type: application/json' \
  --header "Idempotency-Key: $PAYMENT_A_CREATE_KEY" \
  --data-binary '{"merchantId":"DEMO_MERCHANT_A","amount":200.00,"currency":"INR","customerId":"demo-normal-unique-001","paymentMethod":"UPI"}'
```

INR routes to `MOCK_RAZORPAY`; USD routes to `MOCK_STRIPE`. Normal supported-currency payments succeed immediately unless the guarded demo fault selector applies. There is no cross-provider fallback. A payment's process route is `POST /api/v1/payments/{paymentId}/process`; it takes no body and repeated calls cannot create a second gateway charge. Payment, process, and history routes all require JWT and merchant scope. Gateway history uses the response property `gatewayName`.

For an ordinary USD routing check, use Merchant B, a fresh key, and a non-reserved customer ID; process the returned payment UUID once and inspect gateway history:

```bash
USD_KEY="demo-usd-$(python3 -c 'import uuid; print(uuid.uuid4())')"
curl --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_B_TOKEN") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header 'Content-Type: application/json' --header "Idempotency-Key: $USD_KEY" \
  --data-binary '{"merchantId":"DEMO_MERCHANT_B","amount":25.00,"currency":"USD","customerId":"demo-usd-control-unique","paymentMethod":"CARD"}'
```

For an intentional creation idempotency check, repeat the exact same create request with the same key and body; it returns the existing payment. A new payment attempt must use a new key. The request examples create records and have not been run during this documentation phase.

## G. Refund lifecycle

Refunds are simulated; no external reversal occurs. A refund request is `{"amount":N}` and requires its own unique `Idempotency-Key`. Partial refunds can be repeated with new keys while their total is within the original amount; a partial refund leaves payment SUCCESS and a final refund of the remaining amount changes it to REFUNDED. Over-refunding or refunding an ineligible payment returns 409. An exact replay uses the same key and body and returns the original record. Do not retry a refund with a new key after an uncertain response before checking its result. See [README-REFUNDS.md](README-REFUNDS.md).

## H. Webhook recovery demo (Payment A)

This demonstration creates a new payment and mutates payment/inbox records. Run once per new event/payment and stop if any command returns an unexpected result. Use Merchant A's token.

1. Create INR 200.00, UPI payment with `customerId` exactly `PAYMESH_DEMO_GATEWAY_TIMEOUT` and a new unique key. The demo-only selector is active only when the `demo` profile and `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED=true` are both present and the database guard accepts `paymesh_demo`.
2. Process the payment once. Expected payment status is `PROCESSING`; gateway attempt history reports `gatewayName: "MOCK_RAZORPAY"`, observed timeout, and the actual generated `gatewayTransactionId` UUID. The commands below retain the returned IDs in variables and do not print credentials.
3. Send a correctly formed webhook using those actual identifiers. The HMAC secret must match the provider. Timestamp is decimal Unix seconds and must be within ±300 seconds. Signature is hexadecimal HMAC-SHA256 over timestamp, a literal dot, and the exact raw UTF-8 body bytes. Body fields are `eventId`, `paymentId`, `gatewayTransactionId`, `status`, and ISO-8601 `occurredAt`.
4. A deliberately wrong signature returns 401 and is rejected before inbox persistence. A valid matching event returns 200 with receipt status `PROCESSED` and moves the eligible payment to `SUCCESS`.
5. Repeat the identical event/body immediately with a freshly computed timestamp/signature if desired; the same receipt is returned and attempts stay at 1. Reusing the same provider/event ID with a changed body returns 409. Do not modify the event ID/body to retry an uncertain write without checking the inbox first.
6. Read the payment and gateway history using Merchant A's JWT. Verify `SUCCESS` and the original gateway transaction ID are preserved.

Create and process Payment A (each invocation creates a record; inspect the result and do not rerun after uncertainty):

```bash
PAYMENT_A_KEY="demo-timeout-a-$(python3 -c 'import uuid; print(uuid.uuid4())')"
PAYMENT_A_JSON="$(curl --silent --show-error --fail-with-body \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_A_TOKEN") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header 'Content-Type: application/json' --header "Idempotency-Key: $PAYMENT_A_KEY" \
  --data-binary '{"merchantId":"DEMO_MERCHANT_A","amount":200.00,"currency":"INR","customerId":"PAYMESH_DEMO_GATEWAY_TIMEOUT","paymentMethod":"UPI"}')"
PAYMENT_A_ID="$(printf '%s' "$PAYMENT_A_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["paymentId"])')"
curl --include --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_A_TOKEN") \
  --request POST "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_A_ID/process"
ATTEMPTS_A="$(curl --silent --show-error --fail-with-body \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_A_TOKEN") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_A_ID/gateway-transactions")"
GATEWAY_TX_A="$(printf '%s' "$ATTEMPTS_A" | python3 -c 'import json,sys; rows=json.load(sys.stdin); assert rows; print(rows[-1]["gatewayTransactionId"])')"
```

Send the invalid signature, valid webhook, exact duplicate, and conflicting same-ID payload. Python reads the configured secret from the environment and does not print it. The same event body bytes are used for the valid request and duplicate; the conflict changes body content while retaining the event ID and signs those changed bytes correctly:

```bash
export PAYMENT_A_ID GATEWAY_TX_A
python3 - <<'PY'
import datetime, hashlib, hmac, json, os, time, urllib.error, urllib.request, uuid

timestamp = str(int(time.time()))
event_id = 'demo-a-' + str(uuid.uuid4())
payload = {'eventId': event_id, 'paymentId': os.environ['PAYMENT_A_ID'],
           'gatewayTransactionId': os.environ['GATEWAY_TX_A'], 'status': 'SUCCESS',
           'occurredAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')}
body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
secret = os.environ['PAYMESH_RAZORPAY_WEBHOOK_SECRET'].encode('utf-8')
url = 'http://127.0.0.1:18080/api/v1/webhooks/mock-razorpay'

def send(raw, sig):
    req = urllib.request.Request(url, data=raw, method='POST', headers={
        'Content-Type':'application/json', 'X-Paymesh-Timestamp':timestamp,
        'X-Paymesh-Signature':sig})
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()

signature = hmac.new(secret, timestamp.encode('ascii') + b'.' + body, hashlib.sha256).hexdigest()
print('invalid-signature:', send(body, '0' * 64))
print('valid-event:', send(body, signature))
print('exact-duplicate:', send(body, signature))
changed = dict(payload, status='FAILED')
changed_body = json.dumps(changed, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
changed_sig = hmac.new(secret, timestamp.encode('ascii') + b'.' + changed_body, hashlib.sha256).hexdigest()
print('changed-payload-same-event-id:', send(changed_body, changed_sig))
PY
```

Expected statuses are 401, 200 PROCESSED, same receipt/status with attempts still 1, and 409, respectively. Then verify payment and transaction identity:

```bash
curl --include --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_A_TOKEN") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_A_ID"
curl --include --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_A_TOKEN") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_A_ID/gateway-transactions"
```

Use `POST /api/v1/webhooks/mock-razorpay`, `X-Paymesh-Timestamp`, and `X-Paymesh-Signature`. Secret is `PAYMESH_RAZORPAY_WEBHOOK_SECRET`; no JWT is sent to the webhook route. Missing headers or invalid payload are 400; absent/short server secret is 503; body over 65,536 bytes is 413. `occurredAt` cannot be more than 300 seconds in the future. Signature timestamp is checked independently against current server time.

## I. Reconciliation recovery demo (Payment B)

1. Create a separate USD 25.00 CARD payment for `DEMO_MERCHANT_B`, with a new unique idempotency key and `customerId` exactly `PAYMESH_DEMO_GATEWAY_TIMEOUT`.
2. Process once. Expected: PROCESSING/TIMEOUT and `gatewayName: "MOCK_STRIPE"`. **Do not send a webhook for this payment.**
3. Missing settlement token returns 401. Merchant JWT on the settlement route also returns 401; JWT is not settlement authorization.
4. With the existing protected `PAYMESH_SETTLEMENT_ADMIN_TOKEN` variable, call reconcile. Expected 200 report with `status: "RESOLVED"`, `attempts: 1` for the known simulated SUCCESS ledger outcome.
5. Retrieve payment through Merchant B JWT and verify SUCCESS. Retrieve reconciliation history using settlement token; verify a PROCESSING-to-SUCCESS audit and that the original gateway transaction identity remains unchanged.

Example settlement request with token supplied through curl config input:

```bash
PAYMENT_B_KEY="demo-timeout-b-$(python3 -c 'import uuid; print(uuid.uuid4())')"
PAYMENT_B_JSON="$(curl --silent --show-error --fail-with-body \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_B_TOKEN") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header 'Content-Type: application/json' --header "Idempotency-Key: $PAYMENT_B_KEY" \
  --data-binary '{"merchantId":"DEMO_MERCHANT_B","amount":25.00,"currency":"USD","customerId":"PAYMESH_DEMO_GATEWAY_TIMEOUT","paymentMethod":"CARD"}')"
PAYMENT_B_ID="$(printf '%s' "$PAYMENT_B_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["paymentId"])')"
curl --include --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_B_TOKEN") \
  --request POST "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_B_ID/process"
curl --include --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_B_TOKEN") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_B_ID/gateway-transactions"

# Missing settlement credentials must return 401; this intentionally makes no change.
curl --include --request POST "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_B_ID/reconcile"
# Merchant JWT is not settlement authorization and must return 401.
curl --include --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_B_TOKEN") \
  --request POST "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_B_ID/reconcile"

curl --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  --request POST "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_B_ID/reconcile"
curl --include --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_B_TOKEN") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_B_ID"
curl --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_B_ID/reconciliation"
```

Reconciliation consults the local simulated ledger only; no real gateway lookup occurs. Repeated requests obey bounded attempt behavior. Audit/history routes are settlement-token-only.

## J. Troubleshooting and safe recovery

- **Connection refused:** verify that the host backend is already running on loopback port 18080; do not start a duplicate process or restart it without coordinating with the current operator.
- **Expired JWT:** log in again; access tokens last 15 minutes. There is no refresh endpoint.
- **`paymesh_login` unavailable:** source `helpers.sh` in that terminal or use the getpass login fallback above.
- **Incorrect database URL:** fail closed. Verify the configured URL is loopback and ends with `/paymesh_demo`; never use the `paymesh_db` fallback. The application guard checks the actual connected database before migration.
- **Missing secrets:** load the protected `secrets.env` into the current shell without displaying it. Do not generate/rotate secrets during a live demonstration unless the application is restarted and the configuration is coordinated.
- **Wrong gateway field:** current gateway history response property is `gatewayName`, not `gateway`.
- **Timeout not enabled:** verify the demo profile and `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED=true`, and confirm the running server was started with those settings against guarded `paymesh_demo`. The selector has no effect in ordinary startup.
- **Payment already terminal:** webhook recovery only applies to an eligible PROCESSING payment. Reconciliation does not reverse terminal states. Start a fresh payment only after checking whether prior work committed.
- **Uncertain state-changing response:** do not generate a new idempotency key and repeat. Read payment state, history, webhook receipt, or reconciliation audit first. Reuse the same key and exact request only to test idempotency.
- **Webhook 401/400/409:** check timestamp/signature byte agreement, timestamp tolerance, required headers, exact raw body, and provider event-ID uniqueness. Changed body under an existing event ID intentionally conflicts.

## K. Shutdown and data preservation

Stop the host-run backend gracefully with Ctrl-C in the terminal that started
it. Stop only the new database-only project while preserving its data:

```bash
docker compose --project-name paymesh-demo-db \
  --env-file "$HOME/.config/paymesh-demo/demo-compose.env" \
  -f compose.demo.yaml down
```

Do not add `-v`; that removes the dedicated volume. Do not delete, reset, or
recreate either existing database. Unset temporary bearer tokens and secrets
without printing them:

```bash
unset MERCHANT_TOKEN MERCHANT_A_TOKEN MERCHANT_B_TOKEN PAYMESH_SETTLEMENT_ADMIN_TOKEN
unset PAYMESH_RAZORPAY_WEBHOOK_SECRET PAYMESH_STRIPE_WEBHOOK_SECRET
```

## Evidence and limits

The historical 187-test and live recovery results in earlier phase reports are
milestone evidence. Phase 4.4 final test totals and Docker verification status
are recorded in `PHASE-4.4-FINAL-JAVA-BACKEND-REPORT.md`. The commands in this
runbook are operational examples; do not repeat state-changing requests after
an uncertain response. The demo remains simulated and is not production
certification.

## Phase 5.4: existing port-5432 Java/Python integration

For the existing host PostgreSQL demo described in Phase 5.4, use the guarded
restart and authenticated read-only commands in
[PHASE-5.4-JAVA-PYTHON-INTEGRATION-REPORT.md](PHASE-5.4-JAVA-PYTHON-INTEGRATION-REPORT.md).
Those commands target existing `paymesh_demo` on 5432 and port 18080, with existing
accounts and data. They do not use this runbook's fresh port-15432 Compose setup.
The new investigation endpoint defaults disabled; enable `PAYMESH_AI_ENABLED=true`
or the documented command-line setting after deploying the new JAR. Leave FastAPI
on loopback port 8000 and llama.cpp on its existing port 8082.
