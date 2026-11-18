Document-ID: PM-KB-STATISTICS
Title: Recorded statistics
Scenarios: STATISTICS, KNOWLEDGE
Sources: backend/src/main/java/com/paymesh/backend/security/accounts/DashboardAnalytics.java | frontend/PHASE-6.8.3-CUSTOMER-CHECKOUT-REPORT.md
---
Keep every currency separate. Payment counts and recorded amounts are grouped by actual payment status; refund counts and amounts use actual successful refund records. Complete statistics require authorized aggregate queries with explicit scope, not only a recent-record preview or one list page. Links are not payments; genuine checkout attempts create actual payment rows and must not be counted a second time as links. Recorded volume is not available balance, bank settlement, revenue or profit. Incomplete aggregates cannot establish missing groups as zero.
