Document-ID: PM-KB-COMMUNICATION
Title: Customer communication and safe next actions
Scenarios: INCONCLUSIVE, PROCESSING, FAILED, UNRESOLVED_REFUND
Sources: backend/API-REFERENCE.md | backend/API-REFERENCE.md
---
## Verified PayMesh behavior
PayMesh gateways and refunds are simulated. Python accepts supplied normalized snapshots without authenticated Java retrieval in this phase. Status observations may be confirmed within a snapshot while the underlying cause is unknown. Financial amounts, certainty and safe actions are controlled by deterministic analysis.

## General troubleshooting guidance (not evidence of an event)
Use concise, friendly language without internal codes or exception names. For processing, say: We are still waiting for the final payment confirmation. Recommend waiting for an update or contacting support; never advise automatic retries or claim bank arrival.
