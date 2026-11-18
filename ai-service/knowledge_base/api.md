Document-ID: PM-KB-API
Title: Payment API boundaries
Scenarios: CREATED, PROCESSING
Sources: backend/src/main/java/com/paymesh/backend/chat/ChatController.java
---
## General project guidance
Payment API requests are authorized, bounded and validated by Java. Exact decimal amounts and request idempotency protect intent. Never assume HTTP success means bank settlement.
