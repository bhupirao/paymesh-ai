Document-ID: PM-KB-ELIGIBILITY
Title: Merchant eligibility
Scenarios: KNOWLEDGE, CHECKOUT
Sources: backend/src/main/java/com/paymesh/backend/security/accounts/MerchantPortal.java | backend/src/main/java/com/paymesh/backend/security/accounts/CheckoutTransactions.java
---
An enabled ACTIVE Merchant with an active verified registry and unambiguous active membership is required for financial initiation. Pending, rejected, suspended, disabled or ambiguous account ownership does not grant new financial access. Java authenticates users, verifies current sessions and authorizes records. A role or scope string supplied to Python proves none of these checks. Python analyzes only the snapshot it receives and never queries a database or grants authorization.
