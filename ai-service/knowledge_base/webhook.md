Document-ID: PM-KB-WEBHOOK
Title: Webhook confirmation and recovery
Scenarios: WEBHOOK_RECOVERY, SUCCESS
Sources: backend/API-REFERENCE.md | backend/README-WEBHOOKS.md
---
## Verified PayMesh behavior
Webhook recovery uses simulated provider events. Only a matching gateway transaction identity and eligible PROCESSING payment can receive a terminal outcome. PROCESSED inbox status and a matching SUCCESS observation support webhook confirmation. RECEIVED, DEFERRED, IGNORED and FAILED inbox states do not establish successful recovery. A webhook is not bank settlement evidence.

## General troubleshooting guidance (not evidence of an event)
Explain delayed confirmation only when supporting evidence is supplied. Do not invent an earlier timeout from a current successful gateway row.
