Document-ID: PM-KB-TIMEOUT
Title: Gateway timeout and unknown outcomes
Scenarios: GATEWAY_TIMEOUT, PROCESSING
Sources: backend/API-REFERENCE.md | backend/src/main/java/com/paymesh/backend/gateway/GatewayStatus.java
---
## Verified PayMesh behavior
Gateway outcomes are SUCCESS, FAILED and TIMEOUT. A timeout is an uncertain outcome, not proof of a failed charge. Simulated timeout recovery can later update the same gateway transaction row to SUCCESS. A final success row alone contains no historical timeout evidence.

## General troubleshooting guidance (not evidence of an event)
Wait for final confirmation before making another payment. Contact authorized support if the outcome stays unresolved. Never automatically retry an uncertain payment.
