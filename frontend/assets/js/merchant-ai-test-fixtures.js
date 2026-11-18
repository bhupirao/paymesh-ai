// Synthetic fixture derived offline from Phase692 Python oracle and Java public DTO mapping. No live credentials.
export const publicChatFixture={
  "correlationId": "00000000-0000-4000-8000-000000000001",
  "answer": "The supplied current payment status is SUCCESS. A successful simulated payment is recorded; no prior failure, timeout or recovery is inferred.",
  "intent": "PAYMENT_STATUS",
  "evidenceReferences": [
    {
      "reference": "payment:selected",
      "resourceType": "PAYMENT",
      "resourceId": "c072351f-4646-4288-b8ca-6758d4e521f3"
    }
  ],
  "knowledgeReferences": [],
  "limitations": [
    "Python analyzes supplied evidence; it does not authenticate, authorize or independently fetch Java records.",
    "Java alone must enforce ownership, current eligibility and financial actions.",
    "Simulated records do not establish bank debit, settlement, balance, profit or refund arrival.",
    "Previous assistant messages are not authoritative financial evidence."
  ],
  "suggestedFollowUps": [
    "What does the current payment status mean?",
    "How much was refunded?",
    "What does the gateway evidence show?"
  ],
  "moneyFacts": [],
  "analysisMode": "DETERMINISTIC",
  "generationStatus": "DISABLED",
  "evidenceProvenance": {
    "source": "JAVA_AUTHORIZED_DATABASE_SNAPSHOT",
    "collectedAt": "2026-11-15T00:00:00Z",
    "scope": "MERCHANT_OWNED",
    "limitations": [],
    "statisticsRange": null
  }
};
export const knownChatReference={
  "documentId": "PM-KB-LIFECYCLE",
  "chunkId": "PM-KB-LIFECYCLE:000:a5e6d8329184",
  "title": "Payment lifecycle",
  "sources": [
    "ai-service/knowledge_base/lifecycle.md"
  ],
  "score": 0.5
};
