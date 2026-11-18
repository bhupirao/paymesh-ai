// Synthetic contract fixture for mocked tests only; never application fallback content.
export const fixturePaymentId = '842b460e-2451-4294-abc7-62c5525bc180';
export const otherPaymentId = '96829409-bb1a-4f82-b113-4bc9694bd2c0';
export function selectedPayment(status = 'SUCCESS', id = fixturePaymentId) {
  return { paymentId: id, merchantId: 'synthetic-merchant', amount: '25.00', currency: 'USD', customerId: 'synthetic-customer', paymentMethod: 'CARD', status, createdAt: '2026-11-14T00:00:00Z' };
}
export function details(status = 'SUCCESS', id = fixturePaymentId) {
  return { selected: id, payment: selectedPayment(status, id), loading: false, history: [], gateways: [], gatewayState: 'ready', intent: null };
}
export function envelope() {
  return {
    evidenceProvenance: { source: 'JAVA_AUTHORIZED_DATABASE_SNAPSHOT', collectedAt: '2026-11-14T01:00:00Z', unavailableEvidence: {}, scope: 'Synthetic test scope: Java authorized collection; Python analyzes supplied evidence. Bank behavior unverified.' },
    investigation: {
      investigationId: '11111111-1111-4111-8111-111111111111', paymentId: fixturePaymentId, investigationStatus: 'COMPLETED', scenario: 'SUCCESS', generatedAt: '2026-11-14T01:00:11.123456Z',
      customerView: { title: 'Synthetic title', summary: 'Synthetic summary', whatHappened: 'Synthetic observed event', nextAction: 'Synthetic returned action', requiresUserAction: false },
      technicalView: { observedPaymentStatus: 'SUCCESS', rootCause: 'Synthetic unknown cause', rootCauseCertainty: 'INCONCLUSIVE', supportingEvidence: ['synthetic:payment'], technicalExplanation: 'Synthetic technical explanation', recommendedActions: ['Synthetic action'], certainty: 'CONFIRMED' },
      evidenceReferences: ['synthetic:payment'], limitations: ['Synthetic limitation: no bank confirmation.'], analysisMode: 'RAG_LLM',
      knowledgeReferences: [{ documentId: 'synthetic-document', chunkId: 'synthetic-chunk', title: 'Synthetic knowledge title', sources: ['synthetic-source.md'], score: 0.42 }], generationStatus: 'SUCCEEDED'
    }
  };
}
