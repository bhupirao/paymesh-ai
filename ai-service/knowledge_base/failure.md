Document-ID: PM-KB-FAILURE
Title: Payment failure reasons
Scenarios: FAILED, INCONCLUSIVE
Sources: backend/API-REFERENCE.md | backend/src/main/java/com/paymesh/backend/gateway/MockStripeGateway.java
---
## Verified PayMesh behavior
FAILED records a failed simulated payment. Actual mock gateway error codes include UNSUPPORTED_CURRENCY and INVALID_AMOUNT. Unsupported currency means no supported mock gateway is available for that currency; invalid amount means the simulated gateway rejected the amount. Unknown error evidence does not establish an exact root cause.

## General troubleshooting guidance (not evidence of an event)
Use simple explanations only when evidence supports them. Otherwise say the exact reason could not be determined. Do not claim that the bank account was or was not debited.
