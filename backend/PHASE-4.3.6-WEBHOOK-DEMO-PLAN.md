# Phase 4.3.6 — Signed webhook and reconciliation demo plan

> **Historical pre-fault-simulation plan:** The conclusions below describe the
> source state before Phase 4.3.6A introduced the guarded demo-only deterministic
> timeout scenario. For current behavior and run instructions, see
> [PHASE-4.3.6A-FAULT-SIMULATION-REPORT.md](PHASE-4.3.6A-FAULT-SIMULATION-REPORT.md)
> and [README-DEMO.md](README-DEMO.md). This historical report is retained as
> evidence of the earlier read-only inspection; its statements that no request
> can produce a recoverable processing payment are superseded for the explicitly
> enabled, demo-profile scenario only. Normal gateway behavior remains unchanged.

## Scope and read-only boundary

This report was prepared by reading backend source only. The application at `http://127.0.0.1:18080` and either PostgreSQL database were not contacted. No payment, webhook, reconciliation, or other database records were created or changed. No Java/configuration/migration/test file was edited. The only file created is this report.

## 1. Mock gateway outcomes and routing

### Mock Razorpay

Source: `src/main/java/com/paymesh/backend/gateway/MockRazorpayGateway.java`, `MockRazorpayGateway.processPayment`.

- `SUCCESS`: amount is non-null and greater than zero, and currency equals `INR` ignoring case. It returns a random gateway transaction UUID.
- `FAILED`: amount is null or non-positive (`INVALID_AMOUNT`), or currency is null/not `INR` (`UNSUPPORTED_CURRENCY`). These responses have no gateway transaction UUID.
- It never returns `TIMEOUT` or `UNKNOWN`.

### Mock Stripe

Source: `src/main/java/com/paymesh/backend/gateway/MockStripeGateway.java`, `MockStripeGateway.processPayment`.

- `SUCCESS`: amount is non-null and greater than zero, and currency equals `USD` ignoring case. It returns a random gateway transaction UUID.
- `FAILED`: amount is null or non-positive (`INVALID_AMOUNT`), or currency is not `USD` (`UNSUPPORTED_CURRENCY`). These responses have no gateway transaction UUID.
- It never returns `TIMEOUT` or `UNKNOWN`.

The HTTP `PaymentRequest` validation in `src/main/java/com/paymesh/backend/dto/PaymentRequest.java` rejects absent or non-positive amounts before either gateway call. The public payment service routes a currency of INR to Mock Razorpay and USD to Mock Stripe. Other currencies produce an immediate router `FAILED` response (`UNSUPPORTED_CURRENCY`) with no transaction UUID.

Routing sources: `src/main/java/com/paymesh/backend/gateway/RoutingPaymentGateway.java`, `RoutingPaymentGateway.processPayment`; `src/main/java/com/paymesh/backend/gateway/GatewayRouter.java`, `GatewayRouter.route`; and `src/main/java/com/paymesh/backend/service/impl/PaymentOrchestrationServiceImpl.java`, `processPayment`.

`RoutingPaymentGateway` is the primary `PaymentGateway` injected into orchestration. It dispatches INR to Razorpay and USD to Stripe, records the simulated outcome, and does not try another gateway. `GatewayRouter.route` uses the same currency mapping but is not the orchestration bean. There is no fallback rule: a timeout does not switch providers. A `TIMEOUT` response, if a gateway ever supplied one, leaves the payment `PROCESSING`. An exception during the gateway call marks the gateway attempt `UNKNOWN`, keeps the payment `PROCESSING`, and returns HTTP 503 through `GlobalExceptionHandler`. Current mock gateways have no request value that produces either case.

`GatewayStatus` (`src/main/java/com/paymesh/backend/gateway/GatewayStatus.java`) contains `SUCCESS`, `FAILED`, and `TIMEOUT`; it has no `UNKNOWN` enum. `UNKNOWN` is an attempt/reconciliation observation used when the gateway call throws or lookup cannot establish an outcome. This distinction is important: a request body cannot ask these mocks to return `UNKNOWN`.

## 2. Payment request and nonterminal-payment finding

The exact current create-payment request shape is:

```http
POST /api/v1/payments
Idempotency-Key: <unique-key>
Authorization: Bearer <merchant JWT>
Content-Type: application/json
```

```json
{
  "merchantId": "DEMO_MERCHANT_A",
  "amount": 200.00,
  "currency": "INR",
  "customerId": "demo-customer-001",
  "paymentMethod": "UPI"
}
```

It creates a `CREATED` payment (normally HTTP 201; an idempotent replay is HTTP 200). Creation alone does not create a gateway transaction. Calling `POST /api/v1/payments/{paymentId}/process` with that valid INR request routes to Mock Razorpay and completes as `SUCCESS`; USD routes to Mock Stripe and also completes as `SUCCESS`. Unsupported currencies become `FAILED`. There is **no exact payment creation request that produces a `PROCESSING` payment suitable for webhook recovery** with the current mocks. No amount, customer ID, merchant ID, payment method, or supported currency selects timeout/unknown behavior.

Consequently, a successful recovery demonstration requires a payment that is already `PROCESSING` from an earlier uncertain/interrupted gateway outcome, plus its actual gateway transaction UUID. No payment-list endpoint exists to discover such a row, and this inspection does not know a payment ID. A normal create-then-process sequence cannot demonstrate recovery; a valid webhook against a `CREATED` payment is deferred because processing has not started, while a webhook against a terminal `SUCCESS` payment is ignored. Do not claim the current public mock API can deterministically create the recovery fixture.

For an eligible stuck payment, gateway identity must match its attempt: INR → `MOCK_RAZORPAY`; USD → `MOCK_STRIPE`. The submitted `gatewayTransactionId` must equal the attempt's transaction UUID (or the known simulated-ledger UUID if the attempt has none), and `occurredAt` must not predate the attempt by more than the code's one-second tolerance. `OutcomeApplier.apply` only changes a payment currently `PROCESSING`; it accepts terminal `SUCCESS` or `FAILED` observations. `TIMEOUT` and `UNKNOWN` stay deferred.

## 3. Webhook contract and signing

Controller source: `src/main/java/com/paymesh/backend/settlement/WebhookController.java`, methods `razorpay` and `stripe`.

| Provider | Method and path | Configured secret |
| --- | --- | --- |
| Mock Razorpay | `POST /api/v1/webhooks/mock-razorpay` | `PAYMESH_RAZORPAY_WEBHOOK_SECRET` → `paymesh.webhooks.razorpay-secret` |
| Mock Stripe | `POST /api/v1/webhooks/mock-stripe` | `PAYMESH_STRIPE_WEBHOOK_SECRET` → `paymesh.webhooks.stripe-secret` |

Both require `Content-Type: application/json`, `X-Paymesh-Timestamp`, and `X-Paymesh-Signature`. No JWT is required; `LegacyEndpointCatalog` deliberately routes these exact webhook endpoints through the independent HMAC-compatible security chain. The bounded body filter permits at most 65,536 bytes.

The timestamp is a decimal Unix epoch time in **seconds**. Verification accepts timestamps within 300 seconds before/after server time. The signature is HMAC-SHA256 over the exact UTF-8 request bytes:

```text
UTF8(timestamp + ".") || raw_request_body
```

The output is **hexadecimal** (normally 64 hex characters), parsed by `HexFormat`; it is not Base64. Comparison is constant-time via `MessageDigest.isEqual`. Upper/lower hex digits parse, but the authenticated bytes must be exactly the bytes sent. JSON reformatting after signing invalidates the signature.

`WebhookPayload` (`src/main/java/com/paymesh/backend/settlement/WebhookPayload.java`) fields:

```json
{
  "eventId": "unique-provider-event-id",
  "paymentId": "payment UUID",
  "gatewayTransactionId": "gateway transaction UUID",
  "status": "SUCCESS",
  "occurredAt": "2026-11-12T12:30:00Z"
}
```

`eventId` must be nonblank and at most 255 characters; both IDs are UUIDs; `status` is one of `SUCCESS`, `FAILED`, `TIMEOUT`, `UNKNOWN`; `occurredAt` is an ISO-8601 instant. A payload time more than 300 seconds in the future is rejected. It must also correspond to the current processing attempt as described above.

## 4. Duplicate handling and HTTP responses

`WebhookInbox.accept` (`src/main/java/com/paymesh/backend/settlement/WebhookInbox.java`) inserts with `ON CONFLICT (gateway, event_id) DO NOTHING`, then loads the existing row. The database key is provider plus event ID. If the same key is reused with different raw payload bytes, it throws `IdempotencyConflictException`, mapped to HTTP 409. An exact duplicate reuses the original event row and does not create another inbox record. The processor locks the event and only processes pending (`RECEIVED`/`DEFERRED`) events with attempts remaining and a due retry time.

`WebhookController.accept` returns HTTP 202 while the receipt is `RECEIVED` or `DEFERRED`; it returns HTTP 200 for `PROCESSED`, `IGNORED`, or `FAILED`. Therefore an exact duplicate of a processed event normally returns 200 with the existing receipt/status. A duplicate still pending before its retry time normally remains 202. Both responses carry a `WebhookInbox.Receipt` with `id`, `eventId`, `status`, `attempts`, and `detail`.

- Missing required signature or timestamp header: HTTP 400 from Spring MVC's required-header binding; the signature verifier is not reached.
- Present but malformed/missing-value signature, bad signature, malformed timestamp, or timestamp outside ±300 seconds: HTTP 401 with generic `Invalid webhook signature or timestamp`.
- Secret absent or shorter than 32 characters: HTTP 503 `Webhook secret is not configured`.
- Oversized body: HTTP 413.
- Valid signature but invalid JSON/fields: HTTP 400.
- Same provider/event ID with different raw payload: HTTP 409.

The signing check runs before JSON parsing and `WebhookInbox.accept`, so invalid signatures/timestamps create no webhook event row. This is sourced from `WebhookIngress.receive` and `WebhookSignatureVerifier.verify`.

## 5. Settlement reconciliation contract

Source: `src/main/java/com/paymesh/backend/settlement/SettlementAdminController.java`.

All settlement routes use the separate opaque admin token, not JWT:

```http
Authorization: Bearer <PAYMESH_SETTLEMENT_ADMIN_TOKEN>
```

The configured value is `PAYMESH_SETTLEMENT_ADMIN_TOKEN` → `paymesh.settlement.admin-token`; the environment value is the token only, without the `Bearer ` prefix. The controller compares the supplied header with `Bearer ` plus the configured token using constant-time comparison. A missing/wrong token returns 401; a missing/short (<32 characters) configured token returns 503.

| Method and path | Result |
| --- | --- |
| `POST /api/v1/settlement/payments/{paymentId}/reconcile` | JSON `Report`: `paymentId`, `status`, `attempts`, `nextAttemptAt`. |
| `GET /api/v1/settlement/payments/{paymentId}/reconciliation` | Up to 100 reconciliation-attempt row maps, ordered by attempt. |
| `GET /api/v1/settlement/payments/{paymentId}/webhooks` | Up to 100 webhook-event row maps, newest first. |
| `POST /api/v1/settlement/webhooks/{id}/retry` | A webhook receipt; 404 if event ID is absent. |

Reconciliation source: `ReconciliationService.reconcile` and `SimulatedStatusLookup.lookup` in `src/main/java/com/paymesh/backend/settlement/`. It consults the local simulated gateway ledger only; there is no external gateway call. `CREATED` returns `NOT_ELIGIBLE`, attempt 0. A `PROCESSING` payment with a known simulated `SUCCESS`/`FAILED` ledger outcome can resolve and report `RESOLVED`. Unknown or uncertain outcome reports `RETRY`, with bounded retries up to three; identity/outcome conflicts are `EXHAUSTED`. A terminal payment is not reversed: reconciliation records `SKIPPED` and leaves its status unchanged. Retry delays begin at 30 seconds and back off. The optional scheduler is disabled by default (`PAYMESH_SETTLEMENT_SCHEDULING_ENABLED=false`); manual endpoints remain available.

For a normally processed payment already at `SUCCESS`, a manual reconcile call is expected to report `SKIPPED` (not a recovery), because only `PROCESSING` payments are reconciled. `GET .../reconciliation` then returns its audit row. For a missing payment, reconcile returns 404.

## 6. Secret and token handling

The application properties name the secret environment variables but have no usable defaults. Do not inspect the running process environment, use `env`, `ps eww`, shell tracing, `curl -v`, or paste credentials/tokens into command history. Obtain the *existing* configured values through the same approved secret source used to launch the demo. For an interactive shell, hidden prompts can put those existing values into shell variables without echoing them:

```zsh
read -s 'PAYMESH_RAZORPAY_WEBHOOK_SECRET?Configured Mock Razorpay webhook secret: '
export PAYMESH_RAZORPAY_WEBHOOK_SECRET
read -s 'PAYMESH_STRIPE_WEBHOOK_SECRET?Configured Mock Stripe webhook secret: '
export PAYMESH_STRIPE_WEBHOOK_SECRET
read -s 'PAYMESH_SETTLEMENT_ADMIN_TOKEN?Configured settlement token: '
export PAYMESH_SETTLEMENT_ADMIN_TOKEN
```

Use a fresh merchant JWT from the existing login flow only when calling business endpoints, keep it in a shell variable or secure secret store, and never put a literal token in a curl command. To log in without displaying the returned JWT, the following captures Python's stdout into an unexported shell variable; the password is collected with `getpass` and is not an argument or environment value:

```zsh
read 'PAYMESH_MERCHANT_LOGIN?Merchant login: '
PAYMESH_MERCHANT_JWT=$(python3 - "$PAYMESH_MERCHANT_LOGIN" <<'PY'
import getpass, json, sys, urllib.request
login = sys.argv[1]
password = getpass.getpass('Merchant password: ')
body = json.dumps({'login': login, 'password': password}).encode()
request = urllib.request.Request('http://127.0.0.1:18080/api/v1/auth/login', data=body,
    headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request) as response:
    sys.stdout.write(json.load(response)['accessToken'])
PY
)
unset PAYMESH_MERCHANT_LOGIN
```

The examples below use zsh process substitution to provide an Authorization header to curl through a pipe, rather than placing the expanded token in curl's argv or terminal output. Do not use `set -x`. Unset temporary variables after use.

## 7. Safe demonstration commands

Run these only when you intend to submit demo requests. They target port 18080 and contain no database commands. The create-payment example writes a payment; it is shown as a normal-flow control and **does not** create a webhook-recoverable state.

### Normal create/process control (not a recovery fixture)

Set a fresh merchant JWT using the hidden login flow above, and run:

```zsh
curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_JWT") \
  --request POST 'http://127.0.0.1:18080/api/v1/payments' \
  --header 'Idempotency-Key: phase436-control-001' \
  --header 'Content-Type: application/json' \
  --data-raw '{"merchantId":"DEMO_MERCHANT_A","amount":200.00,"currency":"INR","customerId":"demo-customer-001","paymentMethod":"UPI"}'
```

Copy the returned `paymentId` into `PAYMENT_ID` privately (it is an identifier, not a credential). Processing the valid INR payment normally succeeds immediately:

```zsh
curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_JWT") \
  --request POST "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_ID/process"

curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_MERCHANT_JWT") \
  "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_ID/gateway-transactions"
```

Expected: process returns HTTP 200 and `status: SUCCESS`; history returns the gateway transaction UUID and `MOCK_RAZORPAY`. That terminal payment cannot demonstrate recovery. Do not use this control payment as a claim that webhook recovery succeeded.

### Eligible stuck payment: prepare an exact signed webhook

Only continue if you already know an eligible `PROCESSING` payment ID and the actual gateway transaction UUID for its current attempt. Set `PAYMENT_ID`, `GATEWAY_TRANSACTION_ID`, and `WEBHOOK_GATEWAY` (`MOCK_RAZORPAY` for INR or `MOCK_STRIPE` for USD) from an authorized source. This is not discoverable from a payment-list endpoint. The Python block creates an event body, signs the exact UTF-8 bytes, posts an invalid signature first (expected 401/no event write), then posts the valid signed event and repeats the exact event to demonstrate deduplication. It never prints a secret or token.

```zsh
export PAYMENT_ID='replace-with-eligible-processing-payment-uuid'
export GATEWAY_TRANSACTION_ID='replace-with-current-gateway-transaction-uuid'
export WEBHOOK_GATEWAY='MOCK_RAZORPAY'

python3 - <<'PY'
import datetime, hashlib, hmac, json, os, time, urllib.error, urllib.request, uuid

gateway = os.environ['WEBHOOK_GATEWAY']
if gateway == 'MOCK_RAZORPAY':
    path = '/api/v1/webhooks/mock-razorpay'
    secret = os.environ['PAYMESH_RAZORPAY_WEBHOOK_SECRET']
elif gateway == 'MOCK_STRIPE':
    path = '/api/v1/webhooks/mock-stripe'
    secret = os.environ['PAYMESH_STRIPE_WEBHOOK_SECRET']
else:
    raise SystemExit('WEBHOOK_GATEWAY must be MOCK_RAZORPAY or MOCK_STRIPE')

timestamp = str(int(time.time()))
payload = {
    'eventId': 'phase436-' + str(uuid.uuid4()),
    'paymentId': os.environ['PAYMENT_ID'],
    'gatewayTransactionId': os.environ['GATEWAY_TRANSACTION_ID'],
    'status': 'SUCCESS',
    'occurredAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
}
body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
signature = hmac.new(secret.encode('utf-8'), timestamp.encode('ascii') + b'.' + body, hashlib.sha256).hexdigest()
url = 'http://127.0.0.1:18080' + path

def send(sig):
    request = urllib.request.Request(url, data=body, method='POST', headers={
        'Content-Type': 'application/json',
        'X-Paymesh-Timestamp': timestamp,
        'X-Paymesh-Signature': sig,
    })
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode('utf-8')

print('invalid signature:', send('00'))
print('valid event:', send(signature))
print('exact duplicate:', send(signature))
PY
```

Expected for the eligible, correctly matched processing attempt: invalid signature HTTP 401 with no event row; first valid event HTTP 200 with `PROCESSED` and payment status resolved to `SUCCESS`; exact duplicate HTTP 200 with the same event receipt and no second processing. If the payment/transaction IDs do not match, it will be ignored; if payment is not yet processing, it is deferred (HTTP 202); if payment is already terminal, it is ignored. The demonstration's valid webhook requests write audit/inbox state and may change an eligible payment.

### Equivalent curl for a valid signed event

If using curl instead of the Python sender, prepare a raw body and signature from **the exact same string**, timestamp and provider-specific secret. This command signs for Razorpay; set `PAYMENT_ID` and `GATEWAY_TRANSACTION_ID` to an eligible current processing attempt first. For Stripe, switch the secret and endpoint as described below.

```zsh
export WEBHOOK_TIMESTAMP="$(date +%s)"
export WEBHOOK_BODY=$(python3 - <<'PY'
import datetime, json, os, uuid
payload = {
    'eventId': 'phase436-' + str(uuid.uuid4()),
    'paymentId': os.environ['PAYMENT_ID'],
    'gatewayTransactionId': os.environ['GATEWAY_TRANSACTION_ID'],
    'status': 'SUCCESS',
    'occurredAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
}
print(json.dumps(payload, separators=(',', ':'), ensure_ascii=False), end='')
PY
)
export WEBHOOK_SIGNATURE=$(python3 - "$WEBHOOK_TIMESTAMP" "$WEBHOOK_BODY" <<'PY'
import hashlib, hmac, os, sys
message = sys.argv[1].encode('ascii') + b'.' + sys.argv[2].encode('utf-8')
signature = hmac.new(os.environ['PAYMESH_RAZORPAY_WEBHOOK_SECRET'].encode('utf-8'), message, hashlib.sha256).hexdigest()
print(signature, end='')
PY
)
```

Then send exactly those bytes:

```zsh
curl --silent --show-error --include \
  --request POST 'http://127.0.0.1:18080/api/v1/webhooks/mock-razorpay' \
  --header 'Content-Type: application/json' \
  --header "X-Paymesh-Timestamp: $WEBHOOK_TIMESTAMP" \
  --header "X-Paymesh-Signature: $WEBHOOK_SIGNATURE" \
  --data-binary "$WEBHOOK_BODY"
```

For Stripe, use `/api/v1/webhooks/mock-stripe` and sign with `PAYMESH_STRIPE_WEBHOOK_SECRET`. Repeat the exact request immediately for duplicate protection; retain the same event ID, timestamp, signature, and raw body. A newly signed different body with the same provider/event ID returns HTTP 409.

An invalid-signature curl request can use the same otherwise valid body and timestamp with a deliberately malformed signature:

```zsh
curl --silent --show-error --include \
  --request POST 'http://127.0.0.1:18080/api/v1/webhooks/mock-razorpay' \
  --header 'Content-Type: application/json' \
  --header "X-Paymesh-Timestamp: $WEBHOOK_TIMESTAMP" \
  --header 'X-Paymesh-Signature: 00' \
  --data-binary "$WEBHOOK_BODY"
```

Expected HTTP 401. To verify the expired timestamp path, use an epoch value older than 300 seconds and compute a *correct* HMAC for that exact old timestamp and body; the server still returns HTTP 401. Omitting `X-Paymesh-Signature` entirely yields HTTP 400 from required-header binding.

### Reconcile and inspect event history

The token environment value must be the existing configured token. These commands pipe the Authorization header from a shell builtin into curl's config input; they do not echo or place the expanded token in curl arguments:

```zsh
curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  --request POST "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_ID/reconcile"

curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_ID/reconciliation"

curl --silent --show-error --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  "http://127.0.0.1:18080/api/v1/settlement/payments/$PAYMENT_ID/webhooks"
```

With an eligible stuck payment and matching known simulated ledger outcome, reconciliation can report `RESOLVED`; unknown lookup reports bounded `RETRY`/`EXHAUSTED`. With the normal control payment already `SUCCESS`, expected reconciliation result is `SKIPPED`, with an audit row, and it does not change payment status. After the demonstration, clear the temporary variables without displaying them:

```zsh
unset PAYMESH_MERCHANT_JWT PAYMESH_RAZORPAY_WEBHOOK_SECRET PAYMESH_STRIPE_WEBHOOK_SECRET
unset PAYMESH_SETTLEMENT_ADMIN_TOKEN PAYMENT_ID GATEWAY_TRANSACTION_ID WEBHOOK_GATEWAY
unset WEBHOOK_TIMESTAMP WEBHOOK_BODY WEBHOOK_SIGNATURE
```

## 8. Source inventory

- Gateway results/routing: `gateway/MockRazorpayGateway.java`, `gateway/MockStripeGateway.java`, `gateway/RoutingPaymentGateway.java`, `gateway/GatewayRouter.java`, `gateway/GatewayStatus.java`.
- Payment orchestration and request contract: `service/impl/PaymentOrchestrationServiceImpl.java`, `controller/PaymentController.java`, `dto/PaymentRequest.java`, `dto/PaymentResponse.java`.
- Webhook route/signature/validation: `settlement/WebhookController.java`, `settlement/WebhookSignatureVerifier.java`, `settlement/WebhookIngress.java`, `settlement/WebhookPayload.java`, `settlement/Observation.java`.
- Event deduplication and processing: `settlement/WebhookInbox.java`, `settlement/WebhookProcessor.java`, `settlement/OutcomeApplier.java`.
- Simulated reconciliation: `settlement/SimulatedGatewayLedger.java`, `settlement/SimulatedStatusLookup.java`, `settlement/ReconciliationService.java`, `settlement/ReconciliationRunner.java`, `settlement/SettlementScheduler.java`, `settlement/SettlementAdminController.java`.
- Auth/config compatibility: `security/auth/LegacyEndpointCatalog.java`, `security/auth/BusinessEndpointCatalog.java`, `security/auth/JwtSecurityConfiguration.java`, `resources/application.properties`.
- HTTP error mapping: `exception/GlobalExceptionHandler.java`, `security/BoundedRequestBodyFilter.java`.

## Conclusion

HMAC validation, provider/event deduplication, simulated-only reconciliation, and the separate settlement token are implemented. Signature encoding is hex. The primary demo limitation is that neither current mock gateway can emit `TIMEOUT` or `UNKNOWN`, and normal routed processing becomes terminal; there is no request body that creates a recoverable processing payment. A truly successful webhook recovery demonstration needs an existing eligible `PROCESSING` payment with its current gateway transaction UUID, or a separately approved deterministic mock fault-injection mechanism. No new fault-injection endpoint or state-changing workaround is recommended in this read-only plan.
