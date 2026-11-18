Document-ID: PM-KB-CHECKOUT
Title: Customer checkout
Scenarios: CHECKOUT, PROCESSING, KNOWLEDGE
Sources: backend/src/main/resources/db/migration/V13__durable_customer_checkout.sql | backend/src/main/java/com/paymesh/backend/security/accounts/CheckoutTransactions.java
---
PROCESSING or UNCERTAIN checkout attempts block replacement payments. Java commits a token-scoped accepted attempt before the simulated gateway call. Only definitive FAILED permits a new confirmed attempt if the link remains eligible and unexpired, with at most five attempts. Failed history is retained. Success, including authorized reconciliation or webhook completion, atomically records the paid link. A pre-gateway crash may require manual review; status reads never re-execute the gateway. Accepted attempts remain obligations after later expiry or suspension. A receipt is not bank settlement.

This describes implemented code, not proof that V12/V13 is activated live.
