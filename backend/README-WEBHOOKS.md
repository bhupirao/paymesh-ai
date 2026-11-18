# Simulated webhooks and reconciliation

This contract is for the local Mock Razorpay and Mock Stripe providers. It does not use the providers' live webhook formats, contact a real provider, or move money. The complete endpoint contract is in [API-REFERENCE.md](API-REFERENCE.md); the controlled timeout recovery walkthrough is in [README-DEMO.md](README-DEMO.md).

## Authentication and signatures

Webhook routes are authenticated independently from JWT using HMAC-SHA256. Configure `PAYMESH_RAZORPAY_WEBHOOK_SECRET` and `PAYMESH_STRIPE_WEBHOOK_SECRET` as distinct values, each at least 32 characters. Settlement administration uses a separate `PAYMESH_SETTLEMENT_ADMIN_TOKEN`; it is not an application JWT. Missing or invalid configured credentials fail closed. Do not print secrets, load them with shell tracing enabled, or put bearer credentials in curl arguments. Examples should use protected curl config input, such as:

```bash
curl --config <(printf 'header = "Authorization: Bearer %s"\n' "$PAYMESH_SETTLEMENT_ADMIN_TOKEN") \
  'http://127.0.0.1:18080/api/v1/settlement/payments/PAYMENT_UUID/reconciliation'
```

Webhook requests use `X-Paymesh-Timestamp` (decimal Unix epoch seconds) and `X-Paymesh-Signature`. The signature is lowercase/uppercase hexadecimal HMAC-SHA256 over `timestamp + "." + exact raw UTF-8 request bytes`; the comparison is constant-time. The accepted timestamp window is ±300 seconds. The body limit is 65,536 bytes. A signature must be calculated over the exact bytes sent, including JSON whitespace and UTF-8 encoding.

The body has `eventId`, `paymentId`, `gatewayTransactionId`, `status`, and `occurredAt`. The status observation is one of `SUCCESS`, `FAILED`, `TIMEOUT`, or `UNKNOWN`; `occurredAt` is an ISO-8601 instant. The event key is provider plus event ID. A duplicate with the exact same raw payload reuses the receipt and does not apply the outcome twice; the same provider/event ID with changed raw payload returns 409. Only eligible `PROCESSING` payments can transition. A terminal payment, including `REFUNDED`, is not changed back to `SUCCESS`.

## Response behavior

- Missing required headers: 400.
- Malformed, invalid, or expired signature/timestamp: 401.
- Missing/short configured webhook secret: 503.
- Oversized body: 413.
- Valid signature but invalid JSON/fields: 400.
- Conflicting duplicate event payload: 409.
- Receipt in `RECEIVED` or `DEFERRED`: 202; otherwise 200. An exact duplicate of a processed event returns its existing receipt/status, normally 200.

Invalid signatures are rejected before the inbox insert, so rejected events have no database side effect. Reconciliation consults the simulated gateway ledger only. It does not make an external provider status call or issue a second payment. The separate settlement token is required for reconciliation, audit history, webhook inbox history, and manual retry routes; missing or incorrect token returns 401, while a missing/short configured token returns 503.

## Configuration and scheduling

`PAYMESH_SETTLEMENT_SCHEDULING_ENABLED` defaults to `false`; manual operations remain available. If enabled, the settlement scheduler uses the configured poll interval, bounded due-work batches, and persisted retry limits. Retry work is bounded and does not reopen exhausted or terminal operations. Do not enable background scheduling for a demo unless that behavior is intentional.

## Isolated tests

Run tests only through:

```bash
bash scripts/test-isolated.sh
```

The historical 187-test result is previously verified evidence, not a test run performed during this documentation-only phase.
