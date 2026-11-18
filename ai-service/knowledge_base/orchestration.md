Document-ID: PM-KB-ORCHESTRATION
Title: Payment orchestration
Scenarios: CREATED, PROCESSING
Sources: backend/src/main/java/com/paymesh/backend/chat/ChatController.java
---
## General project guidance
Payment orchestration coordinates validated payment creation, gateway routing and durable processing. Simulated gateway timeout remains unresolved until supported status evidence is available; no duplicate execution or bank settlement is inferred.
