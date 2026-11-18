Document-ID: PM-KB-REFUNDS
Title: Partial and full refunds
Scenarios: PARTIAL_REFUND, FULL_REFUND, UNRESOLVED_REFUND
Sources: backend/API-REFERENCE.md | backend/README-REFUNDS.md
---
## Verified PayMesh behavior
Refunds are simulated records; current refund status supports only SUCCESS. Sum successful refund amounts with Decimal. Partial refund leaves payment SUCCESS. Refunding the remaining balance changes payment to REFUNDED. Total successful refunds cannot exceed the original amount through the locked application flow. A missing complete refund history cannot corroborate a full refund.

## General troubleshooting guidance (not evidence of an event)
Explain original amount, successful refund total and remaining amount. Successful refund recording is not proof of arrival in a bank account. Do not give bank arrival timelines or automatically retry a refund.
