Document-ID: PM-KB-LIFECYCLE
Title: Payment lifecycle
Scenarios: CREATED, PROCESSING, SUCCESS, FAILED, CANCELLED, INCONCLUSIVE
Sources: backend/API-REFERENCE.md | backend/src/main/java/com/paymesh/backend/enums/PaymentStatus.java
---
## Verified PayMesh behavior
Payments can be CREATED, PROCESSING, SUCCESS, FAILED, CANCELLED or REFUNDED. A processing claim prevents a second charge on a claimed or terminal payment. CREATED means processing has not started. PROCESSING is an observed state, not a diagnosis of the delay. SUCCESS records a successful simulated payment; it does not prove a bank debit.

## General troubleshooting guidance (not evidence of an event)
Check the current authorized payment record before taking any further action. Missing optional evidence is unavailable, not proof that an event did not happen.
