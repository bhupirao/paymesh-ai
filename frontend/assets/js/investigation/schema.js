import { isUUID } from '../auth/session.js';
export const SCENARIOS = Object.freeze(['CREATED','PROCESSING','GATEWAY_TIMEOUT','SUCCESS','WEBHOOK_RECOVERY','RECONCILIATION_RECOVERY','FAILED','PARTIAL_REFUND','FULL_REFUND','UNRESOLVED_REFUND','INCONCLUSIVE']);
export const PAYMENT_STATES = Object.freeze(['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED']);
export const MODES = Object.freeze(['DETERMINISTIC','RAG_ASSISTED','RAG_LLM']);
export const GENERATION_STATES = Object.freeze(['DISABLED','NOT_ATTEMPTED','SUCCEEDED','NO_RELEVANT_CONTEXT','RETRIEVAL_UNAVAILABLE','TIMEOUT','UNAVAILABLE','INVALID_RESPONSE','VALIDATION_FAILED','CONTEXT_LIMIT']);
const CERTAINTIES = ['CONFIRMED','LIKELY','INCONCLUSIVE'];
function requireValid(value) { if (!value) throw new Error('Invalid investigation response'); }
function object(value, keys) {
  requireValid(value && typeof value === 'object' && !Array.isArray(value));
  const actual = Object.keys(value), expected = keys.split(' ');
  requireValid(actual.length === expected.length && expected.every(key => Object.hasOwn(value, key)));
}
const text = value => requireValid(typeof value === 'string' && value.trim().length > 0);
const strings = value => requireValid(Array.isArray(value) && value.every(item => typeof item === 'string'));
const one = (value, values) => requireValid(values.includes(value));
export function isTimestamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)$/.test(value) || !Number.isFinite(Date.parse(value))) return false;
  const local = new Date(value.slice(0,19) + 'Z');
  return Number.isFinite(local.getTime()) && local.toISOString().slice(0,19) === value.slice(0,19);
}
function freeze(value) {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}
export function validateInvestigation(envelope, paymentId) {
  object(envelope, 'evidenceProvenance investigation');
  const p = envelope.evidenceProvenance, i = envelope.investigation;
  object(p, 'source collectedAt unavailableEvidence scope');
  requireValid(p.source === 'JAVA_AUTHORIZED_DATABASE_SNAPSHOT' && isTimestamp(p.collectedAt)); text(p.scope);
  requireValid(p.unavailableEvidence && typeof p.unavailableEvidence === 'object' && !Array.isArray(p.unavailableEvidence));
  Object.entries(p.unavailableEvidence).forEach(([key, value]) => { text(key); text(value); });
  object(i, 'investigationId paymentId investigationStatus scenario generatedAt customerView technicalView evidenceReferences limitations analysisMode knowledgeReferences generationStatus');
  requireValid(isUUID(i.investigationId) && isUUID(i.paymentId) && isUUID(paymentId) && i.paymentId.toLowerCase() === paymentId.toLowerCase() && isTimestamp(i.generatedAt));
  one(i.investigationStatus, ['COMPLETED','INCONCLUSIVE']); one(i.scenario, SCENARIOS); one(i.analysisMode, MODES); one(i.generationStatus, GENERATION_STATES);
  // Mirror Java's actual implication, without inventing additional enum combinations.
  requireValid(i.analysisMode !== 'RAG_LLM' || i.generationStatus === 'SUCCEEDED');
  const c = i.customerView, t = i.technicalView;
  object(c, 'title summary whatHappened nextAction requiresUserAction');
  for (const key of ['title','summary','whatHappened','nextAction']) text(c[key]);
  requireValid(typeof c.requiresUserAction === 'boolean');
  object(t, 'observedPaymentStatus rootCause rootCauseCertainty supportingEvidence technicalExplanation recommendedActions certainty');
  one(t.observedPaymentStatus, PAYMENT_STATES); one(t.rootCauseCertainty, CERTAINTIES); one(t.certainty, CERTAINTIES);
  text(t.rootCause); text(t.technicalExplanation); strings(t.supportingEvidence); strings(t.recommendedActions);
  strings(i.evidenceReferences); strings(i.limitations);
  requireValid(Array.isArray(i.knowledgeReferences));
  for (const k of i.knowledgeReferences) {
    object(k, 'documentId chunkId title sources score');
    text(k.documentId); text(k.chunkId); text(k.title); strings(k.sources);
    requireValid(typeof k.score === 'number' && Number.isFinite(k.score));
  }
  return freeze(JSON.parse(JSON.stringify(envelope)));
}
export const GENERATION_DESCRIPTIONS = Object.freeze({
  DISABLED: 'Generation is disabled; this does not establish that a model was invoked.',
  NOT_ATTEMPTED: 'Local LLM generation was not attempted.',
  SUCCEEDED: 'Generation reported SUCCEEDED. Successful local LLM-assisted analysis requires RAG_LLM mode.',
  NO_RELEVANT_CONTEXT: 'No relevant knowledge context was returned; no successful LLM generation is established.',
  RETRIEVAL_UNAVAILABLE: 'Knowledge retrieval was unavailable; use the returned fallback analysis.',
  TIMEOUT: 'Generation reported a timeout. The returned analysis is not a successful LLM result.',
  UNAVAILABLE: 'Generation was unavailable. The returned analysis is not a successful LLM result.',
  INVALID_RESPONSE: 'The generation response could not be used; the returned explanation is a fallback.',
  VALIDATION_FAILED: 'Generated wording did not pass validation; the returned explanation is a fallback.',
  CONTEXT_LIMIT: 'Generation context limits prevented a usable LLM result.'
});
export function analysisLabel(i) {
  if (i.analysisMode === 'RAG_LLM' && i.generationStatus === 'SUCCEEDED') return 'Successful local LLM-assisted analysis';
  return i.analysisMode === 'RAG_ASSISTED' ? 'Knowledge-assisted analysis; no successful LLM-assisted result claimed' : 'Deterministic analysis; no successful LLM-assisted result claimed';
}
