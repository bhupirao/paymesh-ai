Document-ID: PM-KB-IDEMPOTENCY
Title: Idempotency and duplicate-payment prevention
Scenarios: CREATED, PROCESSING, GATEWAY_TIMEOUT
Sources: backend/API-REFERENCE.md | backend/src/main/java/com/paymesh/backend/service/impl/RefundServiceImpl.java
---
## Verified PayMesh behavior
Payment creation uses an Idempotency-Key; reuse with changed request conflicts. Payment processing uses the payment ID and persisted processing claim, not a separate idempotency header. Refund keys are scoped to payment and amount; exact replay returns the stored refund. A new key represents a distinct operation and must not be used to bypass uncertainty.

## General troubleshooting guidance (not evidence of an event)
After an uncertain response, inspect the authorized outcome before another operation. This investigation service never executes payment, refund or reconciliation actions.
