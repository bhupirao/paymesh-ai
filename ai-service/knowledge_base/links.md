Document-ID: PM-KB-LINKS
Title: Payment links
Scenarios: CHECKOUT, KNOWLEDGE
Sources: backend/src/main/resources/db/migration/V12__merchant_payment_links.sql | backend/src/main/java/com/paymesh/backend/security/accounts/PaymentLinks.java
---
ACTIVE payment links do not create financial payments. Java derives Merchant ownership and validates amount, currency, method and expiry. Expiry is enforced by server time at initiation. Cancelled or expired links cannot initiate checkout. Accepted unresolved attempts block cancellation and replacement. PAID links retain a successful payment association and cannot execute again, including after a full refund. A public checkout token is a capability: never submit one to the AI engine or model.

This describes implemented code, not proof that V12/V13 is activated live.
