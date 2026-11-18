// Synthetic Phase692 Python-oracle result mapped to the actual Java Admin public DTO.
export const adminStatisticsFixture={
  "correlationId": "00000000-0000-4000-8000-000000000001",
  "answer": "Complete supplied-scope aggregates. INR recorded payment aggregates: count 2, amount 200.00. SUCCESS: 2, 200.00 INR. INR recorded refund aggregates: count 0, amount 0.00.  USD recorded payment aggregates: count 0, amount 0.00.  USD recorded refund aggregates: count 0, amount 0.00.  Currencies and payments/refunds remain separate; these are not balance, settlement, revenue or profit.",
  "intent": "STATISTICS",
  "evidenceReferences": [
    {
      "reference": "statistics:s0",
      "resourceType": "STATISTICS",
      "resourceId": null
    }
  ],
  "knowledgeReferences": [],
  "limitations": [
    "Python analyzes supplied evidence; it does not authenticate, authorize or independently fetch Java records.",
    "Java alone must enforce ownership, current eligibility and financial actions.",
    "Simulated records do not establish bank debit, settlement, balance, profit or refund arrival.",
    "Previous assistant messages are not authoritative financial evidence.",
    "Aggregate completeness and scope are supplied by Java, not independently verified by Python."
  ],
  "suggestedFollowUps": [
    "What does the current payment status mean?",
    "How much was refunded?",
    "What does the gateway evidence show?"
  ],
  "moneyFacts": [
    {
      "kind": "PAYMENT_AGGREGATE",
      "amount": "200.00",
      "currency": "INR",
      "count": 2
    },
    {
      "kind": "REFUND_AGGREGATE",
      "amount": "0.00",
      "currency": "INR",
      "count": 0
    },
    {
      "kind": "PAYMENT_AGGREGATE",
      "amount": "0.00",
      "currency": "USD",
      "count": 0
    },
    {
      "kind": "REFUND_AGGREGATE",
      "amount": "0.00",
      "currency": "USD",
      "count": 0
    }
  ],
  "analysisMode": "DETERMINISTIC",
  "generationStatus": "DISABLED",
  "evidenceProvenance": {
    "source": "JAVA_AUTHORIZED_DATABASE_SNAPSHOT",
    "scope": "ADMIN_AUTHORIZED",
    "collectedAt": "2026-11-15T00:00:00Z",
    "limitations": [],
    "statisticsRange": {
      "from": "2026-11-01T00:00:00Z",
      "to": "2026-11-16T00:00:00Z",
      "timezone": "UTC",
      "endExclusive": true
    }
  }
};
export const adminKnowledgeFixture={
  "documentId": "PM-KB-STATISTICS",
  "chunkId": "PM-KB-STATISTICS:000:dc183abb7220",
  "title": "Recorded statistics",
  "sources": [
    "ai-service/knowledge_base/statistics.md"
  ],
  "score": 0.5
};
