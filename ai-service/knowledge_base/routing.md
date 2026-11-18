Document-ID: PM-KB-ROUTING
Title: Simulated gateway routing
Scenarios: GATEWAY, KNOWLEDGE
Sources: backend/src/main/java/com/paymesh/backend/gateway/GatewayRouter.java | backend/src/main/java/com/paymesh/backend/security/accounts/PaymentLinks.java
---
Payment links and checkout allow INR with UPI or CARD through MOCK_RAZORPAY and USD with CARD through MOCK_STRIPE. USD with UPI is rejected for links/checkout. Legacy payment routing selects the simulated gateway by currency and is not redefined by the link validation contract. Routing guidance does not prove that a transaction occurred. Only supplied authorized gateway records support an observed gateway status; no fallback gateway is inferred.
