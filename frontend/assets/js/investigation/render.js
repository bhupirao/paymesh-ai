import { renderPairs } from '../components/history.js';
import { analysisLabel, GENERATION_DESCRIPTIONS } from './schema.js';
function list(doc, title, values, empty = 'None returned.') {
  const section = doc.createElement('section'), heading = doc.createElement('h4'); heading.textContent = title; section.append(heading);
  if (!values.length) { const text = doc.createElement('p'); text.textContent = empty; section.append(text); }
  else { const ul = doc.createElement('ul'); for (const value of values) { const li = doc.createElement('li'); li.textContent = value; ul.append(li); } section.append(ul); }
  return section;
}
function card(doc, title) {
  const section = doc.createElement('section'), heading = doc.createElement('h4');
  section.className = 'investigation-card'; heading.textContent = title; section.append(heading); return section;
}
function pairs(doc, section, values) { const node = doc.createElement('div'); renderPairs(node, values, doc); section.append(node); }
export function renderInvestigation(container, envelope, doc = document) {
  container.replaceChildren(); if (!envelope) return;
  const i = envelope.investigation, p = envelope.evidenceProvenance, c = i.customerView, t = i.technicalView;
  const summary = card(doc, 'Investigation summary');
  pairs(doc, summary, [['Investigation UUID',i.investigationId],['Payment UUID',i.paymentId],['Investigation status',i.investigationStatus],['Actual scenario',i.scenario],['Analysis prepared at (generatedAt)',i.generatedAt],['Analysis mode',i.analysisMode],['Generation status',i.generationStatus],['Analysis description',analysisLabel(i)],['Generation explanation',GENERATION_DESCRIPTIONS[i.generationStatus]]]);
  const timing = doc.createElement('p'); timing.className = 'small text-secondary';
  timing.textContent = 'generatedAt is assigned before retrieval and LLM generation. It is not a completion timestamp; subtracting collectedAt is not inference duration. Elapsed browser time measures request waiting, not model-only inference.';
  summary.append(timing);
  const customer = card(doc, 'Customer view');
  pairs(doc, customer, [['Title',c.title],['Summary',c.summary],['What happened',c.whatHappened],['Next action',c.nextAction],['User action required',c.requiresUserAction ? 'Yes' : 'No']]);
  const technical = card(doc, 'Technical investigation');
  pairs(doc, technical, [['Observed payment status',t.observedPaymentStatus],['Observed-state / explanation certainty (certainty)',t.certainty],['Root cause',t.rootCause],['Root-cause certainty',t.rootCauseCertainty],['Technical explanation',t.technicalExplanation]]);
  const distinction = doc.createElement('p'); distinction.className = 'small text-secondary'; distinction.textContent = 'Observed-state certainty does not establish root-cause certainty. Labels are reported by the API, not converted to confidence percentages.';
  technical.append(distinction, list(doc,'Supporting evidence',t.supportingEvidence),list(doc,'Recommended actions',t.recommendedActions));
  const provenance = card(doc, 'Evidence and provenance');
  pairs(doc, provenance, [['Evidence source',p.source],['Evidence collected at',p.collectedAt],['Evidence scope',p.scope]]);
  const trust = doc.createElement('p'); trust.textContent = 'Java collected this evidence after authorization. Python analyzes supplied evidence; it does not independently authenticate or fetch Java records. Unavailable evidence is not proof that an event never occurred.';
  provenance.append(trust, list(doc,'Unavailable evidence',Object.entries(p.unavailableEvidence).map(([key,value]) => `${key}: ${value}`),'No unavailable evidence reported.'),list(doc,'Evidence references',i.evidenceReferences,'No evidence references returned.'));
  const knowledge = card(doc, 'RAG knowledge references');
  const relevance = doc.createElement('p'); relevance.textContent = 'Scores indicate retrieval relevance, not correctness probability or root-cause confidence. Source strings are displayed as text.'; knowledge.append(relevance);
  if (!i.knowledgeReferences.length) { const empty = doc.createElement('p'); empty.textContent = 'No knowledge references returned.'; knowledge.append(empty); }
  for (const reference of i.knowledgeReferences) {
    const item = doc.createElement('section'); item.className = 'knowledge-reference';
    pairs(doc,item,[['Document title',reference.title],['Document ID',reference.documentId],['Chunk ID',reference.chunkId],['Retrieval relevance score',String(reference.score)]]);
    item.append(list(doc,'Sources',reference.sources,'No source strings returned.')); knowledge.append(item);
  }
  const limitations = card(doc, 'Investigation limitations'); limitations.append(list(doc,'Returned limitations',i.limitations,'No limitations returned. Simulation and trust-boundary notices still apply.'));
  container.append(summary, customer, technical, provenance, knowledge, limitations);
}
