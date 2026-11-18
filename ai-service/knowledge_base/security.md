Document-ID: PM-KB-SECURITY
Title: Payment API security
Scenarios: CREATED, PROCESSING
Sources: backend/src/main/java/com/paymesh/backend/chat/ChatController.java
---
## General project guidance
Authentication identifies a caller; authorization restricts their current session, role, Merchant membership and payment ownership. Chat cannot disclose credentials, execute payments or bypass authorization.
