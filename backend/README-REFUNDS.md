# Refunds

Refunds are simulated records. No real payment provider reversal occurs. A refund can be created only for a payment currently in `SUCCESS`; an amount must be positive and have at most two decimal places. The JSON body is `{"amount":200.00}` and every POST requires a unique `Idempotency-Key` (1–255 nonblank characters).

Partial refunds are supported. Multiple refunds may be created against one payment while their successful total remains at or below the original payment amount. A partial refund leaves the payment `SUCCESS`; a refund equal to the remaining refundable balance changes it to `REFUNDED`. Requests over the remaining balance and requests for ineligible states return 409. The payment row is locked while the idempotency key and remaining balance are checked, and refund creation and final status update occur in that transaction. Replays with the same key and amount return the original refund (HTTP 200); reuse of a key with a different amount returns 409. A new refund returns 201.

## Authenticated request example

Use an access token from `POST /api/v1/auth/login`. The token is valid for 15 minutes. The example passes it to curl using protected config input, not as a command-line argument:

```bash
PAYMENT_ID='your-payment-uuid'
curl --include \
  --config <(printf 'header = "Authorization: Bearer %s"\n' "$MERCHANT_TOKEN") \
  --request POST "http://127.0.0.1:18080/api/v1/payments/$PAYMENT_ID/refund" \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: refund-demo-unique-001' \
  --data-binary '{"amount":200.00}'
```

Do not repeat a state-changing command after an uncertain response until you have checked its outcome. To intentionally test idempotency, reuse the same key and exact body. For a distinct refund, use a new key and request only the remaining amount. A full refund is represented by the entire remaining refundable amount in the same request field; there is no separate full-refund endpoint or bodyless operation.

## Read routes

- `GET /api/v1/payments/{paymentId}/refund` returns the latest refund object, or 404 if none exists.
- `GET /api/v1/payments/{paymentId}/refunds` returns all refund objects in creation order; an existing payment with no refunds returns `[]`.

Both routes require a JWT and enforce payment ownership. Response fields are `refundId`, `paymentId`, `amount`, `status`, and `createdAt`. See [API-REFERENCE.md](API-REFERENCE.md) for the full request, response, and error contract.

## Storage and concurrency

Flyway V6 changed refund cardinality and added refund idempotency support. V8 adds authentication and merchant membership schema. Do not edit V1–V8 after application. Refund writes lock the payment row and sum successful refunds under the lock; the unique `(payment_id, idempotency_key)` constraint also prevents duplicate-key inserts. This protection assumes application refund writers use the same service/locking protocol; it is not a cross-table database CHECK constraint for arbitrary direct SQL writers.

Use only the isolated test runner for automated tests:

```bash
bash scripts/test-isolated.sh
```

The historical 187-test baseline was supplied as previously verified evidence and was not rerun during documentation finalization.
