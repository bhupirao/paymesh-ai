Document-ID: PM-KB-RECONCILIATION
Title: Settlement reconciliation
Scenarios: RECONCILIATION_RECOVERY, PROCESSING
Sources: backend/API-REFERENCE.md | backend/src/main/java/com/paymesh/backend/settlement/ReconciliationService.java
---
## Verified PayMesh behavior
Reconciliation consults a simulated gateway ledger, not a live provider. A RESOLVED audit result with PROCESSING before and SUCCESS after supports reconciliation recovery. Job statuses include PENDING, RETRY, RESOLVED, EXHAUSTED and SKIPPED. A CREATED payment can return NOT_ELIGIBLE. Audit results and refund statuses are separate concepts. Reconciliation does not issue another payment.

## General troubleshooting guidance (not evidence of an event)
Ask authorized support to review unresolved evidence. Do not promise automated repair or present reconciliation as confirmation of bank settlement.
