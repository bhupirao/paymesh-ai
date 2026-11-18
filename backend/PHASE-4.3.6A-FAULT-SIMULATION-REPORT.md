# Phase 4.3.6A — Controlled Demo Gateway Timeout

## Result

Implemented a deterministic, opt-in demo timeout that preserves the mock gateway's actual simulated SUCCESS while presenting TIMEOUT to orchestration. This leaves the payment `PROCESSING`, records a real gateway transaction UUID, and supports recovery through the existing signed webhook or settlement reconciliation flows.

No schema change was needed. V1–V8 were not modified. No operational application was restarted, no demo payments were created during implementation, and neither `paymesh_demo` nor `paymesh_db` was contacted. Automated database tests used only the isolated database created by `scripts/test-isolated.sh`.

## Modified files

- `src/main/java/com/paymesh/backend/gateway/DemoGatewayTimeoutSimulator.java` — narrowly transforms a known successful response for one reserved demo customer.
- `src/main/java/com/paymesh/backend/security/accounts/DemoGatewayFaultSimulationConfiguration.java` — registers the simulator only under the `demo` profile and explicit enable property; rejects unsafe database/migration settings and verifies the connected database before Flyway runs.
- `src/main/java/com/paymesh/backend/service/impl/PaymentOrchestrationServiceImpl.java` — consults the optional simulator after the routed gateway call and before persisting the orchestration observation. Existing direct and ordinary application construction remains unsimulated.
- `src/main/resources/application.properties` — declares `paymesh.demo.gateway-timeout.enabled`, defaulting to `false`.
- `src/test/java/com/paymesh/backend/security/accounts/DemoGatewayFaultSimulationConfigurationTest.java` — covers disabled/profile gating, unsafe target rejection, and selector constraints.
- `src/test/java/com/paymesh/backend/settlement/SettlementIntegrationTest.java` — adds HTTP integration coverage for deterministic timeout, ledger identity/outcome, signed webhook recovery and duplicate delivery, reconciliation, duplicate processing, and normal INR/USD flows.
- `PHASE-4.3.6A-FAULT-SIMULATION-REPORT.md` — this report.

## Behavior and safeguards

`RoutingPaymentGateway` still routes INR to Mock Razorpay and USD to Mock Stripe, receives the provider's SUCCESS and generated UUID, and records that outcome in `SimulatedGatewayLedger`. Only afterward does the optional demo simulator replace the orchestration response with `TIMEOUT`, keeping the same provider and UUID. The gateway transaction attempt records the timeout observation and UUID; the payment stays `PROCESSING`. The ledger remains `SUCCESS` for later status lookup.

The selector is the exact reserved `customerId` `PAYMESH_DEMO_GATEWAY_TIMEOUT`. It only transforms `SUCCESS` responses with a non-null transaction UUID from `MOCK_RAZORPAY` or `MOCK_STRIPE`. It cannot request a failure, choose a gateway, inject a transaction ID, or alter a production payment request schema. With the simulation absent, the selector has no effect.

Production registration requires both `SPRING_PROFILES_ACTIVE=demo` and `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED=true`. The property defaults to false. When enabled, startup fails closed unless the configured datasource URL is a local PostgreSQL URL ending exactly in `/paymesh_demo`, Flyway is enabled and uses the guarded datasource, and settlement scheduling is disabled. Immediately before Flyway migration, the connected JDBC URL and `SELECT current_database()` are checked through the existing `DemoDatabaseGuard`. This does not weaken or bypass that guard.

No payment, merchant, refund, webhook, settlement, JWT, or public administrative endpoint was added or changed. The feature continues to use JWT and existing merchant ownership for payment calls, existing webhook HMAC/timestamp/deduplication for webhook recovery, and the separate settlement bearer token for reconciliation. Payment claim/idempotency rules still prevent duplicate gateway attempts. Refund protection and internal financial capability boundaries are unchanged.

## Automated verification

Focused integration tests use the isolated test database and the normal secured HTTP payment endpoints. They assert the generated gateway transaction identity is retained, the payment remains `PROCESSING`, and the ledger still reports `SUCCESS`; then they resolve independent payments through a correctly signed webhook and settlement reconciliation. The webhook test repeats the same signed event and checks the payment version and inbox attempt count do not advance twice. Another test verifies a repeated process call conflicts without another attempt/ledger charge. INR and USD normal customer cases both remain `SUCCESS`.

The full suite was run only with:

```text
bash scripts/test-isolated.sh
```

Final result:

- Tests run: **187**
- Failures: **0**
- Errors: **0**
- Skipped: **0**
- Build: **BUILD SUCCESS**
- Isolated PostgreSQL shutdown: **confirmed** (`server stopped` from the script)
- Application/demo database safety: the run used a `paymesh_isolated_*` database on port 55441; neither `paymesh_db` nor `paymesh_demo` was accessed.

An initial run had one faulty assertion in the null-transaction selector test. The assertion was corrected and the complete suite was rerun successfully.

## Demo configuration and safe restart

Do not enable the simulation in the currently running server. To use the feature later, first stop the demo application using its normal operator procedure. Start it with the existing secrets and JWT key configuration supplied by the same secret source used for the current demo. Do not print secrets, tokens, passwords, or private keys. The relevant non-secret settings are:

```zsh
export SPRING_PROFILES_ACTIVE=demo
export PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED=true
export PAYMESH_DB_URL='jdbc:postgresql://127.0.0.1:5432/paymesh_demo'
export PAYMESH_DB_USER='paymesh_demo_user'
export PAYMESH_SETTLEMENT_SCHEDULING_ENABLED=false
```

`PAYMESH_DB_PASSWORD`, JWT key-file settings, issuer/audience, both webhook secrets, and `PAYMESH_SETTLEMENT_ADMIN_TOKEN` must already be supplied through the existing secure environment/secret source. The guarded profile requires the demo database to be reachable at the configured local target; this implementation does not create it. Use the project's normal packaged application/start command, with the above environment and the existing secret values. Do not override `spring.flyway.url`, disable Flyway, or enable settlement scheduling when the simulation is enabled. Startup will refuse any configured or connected database other than `paymesh_demo`.

## Demo commands

The examples assume a fresh merchant JWT is already held in `PAYMESH_MERCHANT_JWT` for the relevant demo merchant, and that the existing secrets are present in their named environment variables. Do not put literal tokens or secret values in command text. These requests intentionally create demo payments when run; they were not executed during this implementation.

### Payment A — INR timeout then signed Mock Razorpay webhook

Create using the merchant A identity (`DEMO_MERCHANT_A`), with a fresh idempotency key:

```zsh
PAYMENT_A=$(curl --silent --show-error \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_JWT") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header "Idempotency-Key: phase436a-A-$(uuidgen)" \
  --header 'Content-Type: application/json' \
  --data-raw '{"merchantId":"DEMO_MERCHANT_A","amount":200.00,"currency":"INR","customerId":"PAYMESH_DEMO_GATEWAY_TIMEOUT","paymentMethod":"UPI"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["paymentId"])')
```

Process it. Expected HTTP 200 response has `status: PROCESSING`:

```zsh
curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_JWT") \
  --request POST "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_A/process"
```

Read gateway history and copy the actual `gatewayTransactionId` from the response (the API returns a generated UUID; do not invent one):

```zsh
curl --silent --show-error \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_JWT") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_A/gateway-transactions"
```

Set `GATEWAY_TRANSACTION_ID_A` to that returned UUID, then post a correctly signed event and repeat the identical event/body to demonstrate deduplication. This Python sender signs the exact compact UTF-8 JSON bytes as `HMAC-SHA256(secret, timestamp + b'.' + body)`, encoded as lowercase hexadecimal. It reads the existing `PAYMESH_RAZORPAY_WEBHOOK_SECRET` from the environment and never prints it:

```zsh
export PAYMENT_A GATEWAY_TRANSACTION_ID_A
python3 - <<'PY'
import datetime, hashlib, hmac, json, os, time, urllib.error, urllib.request, uuid

timestamp = str(int(time.time()))
payload = {
    'eventId': 'phase436a-A-' + str(uuid.uuid4()),
    'paymentId': os.environ['PAYMENT_A'],
    'gatewayTransactionId': os.environ['GATEWAY_TRANSACTION_ID_A'],
    'status': 'SUCCESS',
    'occurredAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
}
body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
secret = os.environ['PAYMESH_RAZORPAY_WEBHOOK_SECRET'].encode('utf-8')
signature = hmac.new(secret, timestamp.encode('ascii') + b'.' + body, hashlib.sha256).hexdigest()
request = urllib.request.Request(
    'http://127.0.0.1:18080/api/v1/webhooks/mock-razorpay', data=body, method='POST',
    headers={'Content-Type': 'application/json', 'X-Paymesh-Timestamp': timestamp,
             'X-Paymesh-Signature': signature})
for attempt in ('first', 'duplicate'):
    try:
        with urllib.request.urlopen(request) as response:
            print(attempt, response.status, response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        print(attempt, error.code, error.read().decode('utf-8'))
PY
```

Expected: first delivery returns HTTP 200 with `PROCESSED`; exact duplicate returns the existing HTTP 200 receipt. Payment A becomes `SUCCESS`; there is still one gateway attempt and one webhook inbox event. The duplicate must not apply the outcome again.

### Payment B — USD timeout then settlement reconciliation

Use a fresh JWT for the merchant that owns `DEMO_MERCHANT_B` and create a separate USD payment:

```zsh
PAYMENT_B=$(curl --silent --show-error \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_B_JWT") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header "Idempotency-Key: phase436a-B-$(uuidgen)" \
  --header 'Content-Type: application/json' \
  --data-raw '{"merchantId":"DEMO_MERCHANT_B","amount":25.00,"currency":"USD","customerId":"PAYMESH_DEMO_GATEWAY_TIMEOUT","paymentMethod":"CARD"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["paymentId"])')

curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_B_JWT") \
  --request POST "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_B/process"

curl --silent --show-error \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_B_JWT") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_B/gateway-transactions"
```

Processing is expected to return HTTP 200 with `PROCESSING`; history contains the generated gateway transaction UUID and a `TIMEOUT` observation. Resolve it with the independent settlement token (not JWT):

```zsh
curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  --request POST "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_B/reconcile"

curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_B/reconciliation"
```

Expected reconcile response is HTTP 200 with `status: RESOLVED`; payment B becomes `SUCCESS` from the simulated ledger lookup. The history endpoint shows the reconciliation audit row. The process endpoint cannot be used a second time to create another attempt.

## Deployment limits

- This is a deterministic mock-only demo behavior; it does not call Razorpay, Stripe, or any external gateway.
- The reserved customer ID should be used only for the intended demo cases. It does not modify any other request.
- Do not enable this profile/property against a shared, staging, or production database. The runtime guard permits only local `paymesh_demo` and deliberately refuses alternate Flyway targets or disabled Flyway.
- When simulation is enabled, keep settlement scheduling disabled so Payment A remains available for webhook recovery until its signed event is submitted.
- No changes were made to Compose; configure the profile/property and existing secrets only through the approved local demo launch environment.
