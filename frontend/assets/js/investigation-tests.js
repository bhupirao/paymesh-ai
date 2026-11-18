import { SCENARIOS, MODES, GENERATION_STATES, PAYMENT_STATES, validateInvestigation, analysisLabel } from './investigation/schema.js';
import { createInvestigation } from './investigation/model.js';
import { renderInvestigation } from './investigation/render.js';
import { envelope, details, fixturePaymentId as id, otherPaymentId as other } from './investigation/fixtures.js';
import { tokenResponse } from './test-fixtures.js';
import { setSession, clearSession, checkExpiry, getSession } from './auth/session.js';
import { createRefundWorkspace } from './features/refunds.js';
import { createPaymentWorkflow } from './features/payments.js';
import { API } from './api/config.js';
const original = window.fetch, clock = Date.now;
const results = [], json = (body, status = 200) => new Response(JSON.stringify(body), { status });
const assert = (value, label) => { if (!value) throw new Error(label); results.push(label); };
const rejected = (fn, label) => { let failed = false; try { fn(); } catch { failed = true; } assert(failed, label); };
let state, sent = [];
const model = createInvestigation(next => { state = next; }); model.start();
const container = document.querySelector('#render-test');
function reset() { clearSession(); setSession(tokenResponse(), 'test'); sent = []; model.observe(details()); window.fetch = async (url, options) => { sent.push({ url, ...options }); return json(envelope()); }; }
try {
  const validated = validateInvestigation(envelope(), id);
  assert(validated.investigation.paymentId === id, 'actual envelope validated');
  assert(Object.isFrozen(validated) && Object.isFrozen(validated.investigation.customerView), 'validated snapshot deeply frozen');
  const offset = envelope(); offset.investigation.generatedAt = '2026-11-14T06:30:11+05:30';
  assert(validateInvestigation(offset,id).investigation.generatedAt.endsWith('+05:30'), 'aware offset timestamps accepted');
  const variations = [
    value => { value.investigation.paymentId = other; }, value => { value.investigation.investigationId = 'bad'; },
    value => { value.investigation.generatedAt = '2026-02-30T00:00:00Z'; }, value => { value.evidenceProvenance.collectedAt = 'yesterday'; },
    value => { value.evidenceProvenance.source = 'UNAUTHENTICATED_INPUT'; }, value => { value.evidenceProvenance.unavailableEvidence = []; },
    value => { value.evidenceProvenance.unavailableEvidence.refunds = 3; }, value => { delete value.investigation.customerView.summary; },
    value => { value.investigation.customerView.requiresUserAction = 'true'; }, value => { value.investigation.technicalView.certainty = '99%'; },
    value => { value.investigation.technicalView.rootCauseCertainty = 'PROVEN'; }, value => { value.investigation.technicalView.observedPaymentStatus = 'SETTLED'; },
    value => { value.investigation.technicalView.supportingEvidence = {}; }, value => { value.investigation.evidenceReferences = [3]; },
    value => { value.investigation.limitations = null; }, value => { value.investigation.knowledgeReferences[0].score = '0.42'; },
    value => { value.investigation.knowledgeReferences[0].score = Infinity; }, value => { delete value.investigation.knowledgeReferences[0].sources; },
    value => { value.investigation.scenario = 'BANK_SETTLED'; }, value => { value.investigation.analysisMode = 'AUTONOMOUS'; },
    value => { value.investigation.generationStatus = 'HALLUCINATED'; }, value => { value.investigation.investigationStatus = 'FAILED'; },
    value => { value.investigation.customerView.extra = 'hidden'; }, value => { value.evidenceProvenance.scope = ''; }
  ];
  for (const change of variations) { const value = envelope(); change(value); rejected(() => validateInvestigation(value,id), 'malformed or mismatched envelope rejected'); }
  for (const scenario of SCENARIOS) {
    const value = envelope(); value.investigation.scenario = scenario; renderInvestigation(container, validateInvestigation(value,id));
    assert(container.textContent.includes(scenario), `actual scenario ${scenario} rendered`);
  }
  for (const status of PAYMENT_STATES) { const value = envelope(); value.investigation.technicalView.observedPaymentStatus = status; assert(validateInvestigation(value,id).investigation.technicalView.observedPaymentStatus === status, `observed status ${status}`); }
  for (const mode of MODES) { const value = envelope(); value.investigation.analysisMode = mode; if (mode !== 'RAG_LLM') value.investigation.generationStatus = 'NOT_ATTEMPTED'; renderInvestigation(container,validateInvestigation(value,id)); assert(container.textContent.includes(mode), `analysis mode ${mode}`); }
  for (const status of GENERATION_STATES) {
    const value = envelope(); value.investigation.generationStatus = status; value.investigation.analysisMode = status === 'SUCCEEDED' ? 'RAG_LLM' : 'RAG_ASSISTED';
    renderInvestigation(container, validateInvestigation(value,id)); assert(container.textContent.includes(status), `actual generation status ${status}`);
    if (status !== 'SUCCEEDED') { value.investigation.analysisMode = 'RAG_LLM'; rejected(() => validateInvestigation(value,id), 'RAG_LLM requires SUCCEEDED'); }
  }
  assert(analysisLabel(envelope().investigation) === 'Successful local LLM-assisted analysis', 'RAG_LLM SUCCEEDED correctly labeled');
  for (const mode of ['DETERMINISTIC','RAG_ASSISTED']) { const value = envelope(); value.investigation.analysisMode = mode; assert(!analysisLabel(value.investigation).startsWith('Successful'), 'fallback never labeled successful LLM'); }
  const content = envelope(); content.evidenceProvenance.unavailableEvidence = { gatewayTransactions: 'Synthetic withheld evidence' }; renderInvestigation(container,validateInvestigation(content,id));
  for (const text of ['Synthetic title','Synthetic summary','Synthetic observed event','Synthetic returned action','No','Synthetic unknown cause','INCONCLUSIVE','CONFIRMED','Synthetic technical explanation','Synthetic action','JAVA_AUTHORIZED_DATABASE_SNAPSHOT','2026-11-14T01:00:00Z','2026-11-14T01:00:11.123456Z','gatewayTransactions','Synthetic withheld evidence','Synthetic limitation','Synthetic knowledge title','synthetic-document','synthetic-chunk','synthetic-source.md','0.42']) assert(container.textContent.includes(text), 'actual customer technical provenance knowledge and limitation fields');
  assert(container.textContent.includes('Root-cause certainty') && container.textContent.includes('Observed-state / explanation certainty') && !container.textContent.includes('42%'), 'separate certainty labels and relevance not percentages');
  const requiresAction = envelope(); requiresAction.investigation.customerView.requiresUserAction = true; renderInvestigation(container,validateInvestigation(requiresAction,id));
  assert(container.textContent.includes('Yes'), 'actual requiresUserAction true rendered');
  const empty = envelope(); empty.investigation.knowledgeReferences = []; empty.investigation.evidenceReferences = []; renderInvestigation(container,validateInvestigation(empty,id));
  assert(container.textContent.includes('No knowledge references returned') && container.textContent.includes('No evidence references returned'), 'empty references explicit');
  const unsafe = envelope(); unsafe.investigation.customerView.summary = '<img src=x onerror=alert(1)>'; unsafe.investigation.knowledgeReferences[0].sources = ['https://untrusted.example','<a href=x>source</a>']; renderInvestigation(container,validateInvestigation(unsafe,id));
  assert(container.textContent.includes('<img') && !container.querySelector('img') && !container.querySelector('a'), 'safe text with no untrusted links');
  reset(); assert(sent.length === 0 && state.available && state.phase === 'ready', 'authorized selection ready but never automatic');
  let resolve;
  window.fetch = (url, options) => { sent.push({ url, ...options }); return new Promise(done => { resolve = done; }); };
  const originalTimer = globalThis.setTimeout; let timeout;
  try { globalThis.setTimeout = (fn, ms) => { timeout = ms; return originalTimer(fn, ms); }; var pending = model.run(); } finally { globalThis.setTimeout = originalTimer; }
  await model.run();
  assert(state.phase === 'loading' && state.busy && sent.length === 1, 'loading and duplicate prevention');
  assert(timeout === 65000 && timeout === API.investigationTimeoutMs, 'investigation-specific 65 second browser timeout');
  assert(sent[0].url === `/api/v1/payments/${id}/investigate` && sent[0].method === 'POST' && sent[0].headers.Authorization.startsWith('Bearer '), 'correct Java-authorized same-origin endpoint');
  assert(sent[0].body === undefined && !('Idempotency-Key' in sent[0].headers) && !('Content-Type' in sent[0].headers), 'bodyless request without invented key');
  resolve(json(envelope())); await pending;
  assert(state.phase === 'completed' && state.result && !state.busy, 'COMPLETED result accepted');
  const inconclusive = envelope(); inconclusive.investigation.investigationStatus = 'INCONCLUSIVE'; inconclusive.investigation.scenario = 'INCONCLUSIVE';
  window.fetch = async () => json(inconclusive); await model.run(); assert(state.phase === 'inconclusive' && state.result, 'INCONCLUSIVE result is not network failure');
  for (const status of PAYMENT_STATES) { model.observe(details(status)); assert(state.available && !state.result, `all payment states eligible for explicit analysis ${status}`); }
  for (const code of [400,401,403,404,422,429,502,503,504]) {
    reset(); window.fetch = async (url, options) => { sent.push({ url, ...options }); return json({ message: 'raw-secret-not-to-display' },code); };
    await model.run(); assert(!state.result && !state.message.includes('raw-secret') && (code === 401 ? !getSession() : state.phase === 'failed'), `safe investigation ${code} handling`);
    assert(sent.length === 1, 'failed investigation never retries automatically');
  }
  reset(); window.fetch = async () => { throw new TypeError('private stack'); }; await model.run(); assert(state.phase === 'failed' && state.message.includes('may still'), 'network failure does not claim server cancellation');
  window.fetch = async () => { throw Object.assign(new Error('synthetic abort'), { name: 'AbortError' }); }; await model.run(); assert(state.message.includes('browser timed out') && !state.result, 'client timeout safe lifecycle');
  let fireTimeout;
  const savedTimer = globalThis.setTimeout;
  window.fetch = (url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(Object.assign(new Error('synthetic abort'), { name: 'AbortError' }))));
  let actualTimeout;
  try { globalThis.setTimeout = (callback, ms) => { if (ms === 65000) { fireTimeout = callback; return 0; } return savedTimer(callback, ms); }; actualTimeout = model.run(); }
  finally { globalThis.setTimeout = savedTimer; }
  assert(typeof fireTimeout === 'function', 'real timeout schedules investigation duration');
  fireTimeout(); await actualTimeout;
  assert(state.phase === 'failed' && state.message.includes('browser timed out') && !state.busy, 'timer abort produces safe timeout result');
  window.fetch = async () => new Response('not-json'); await model.run(); assert(state.message.includes('invalid or mismatched') && !state.result, 'invalid JSON no partial result');
  window.fetch = async () => { const value = envelope(); value.investigation.paymentId = other; return json(value); }; await model.run(); assert(state.message.includes('invalid or mismatched'), 'mismatched payment result withheld');
  window.fetch = async () => json(envelope()); await model.run(); assert(state.phase === 'completed', 'explicit retry only restores successful result');
  model.observe({ ...details(), history: [{ refundId: 'changed' }] }); assert(!state.result && state.message.includes('cleared'), 'refund history change invalidates snapshot');
  await model.run(); model.observe(details('REFUNDED')); assert(!state.result, 'payment state change invalidates snapshot without re-investigating');
  model.observe(details(), true); const callsBefore = sent.length; assert(!state.available && !await model.run() && sent.length === callsBefore, 'financial intent blocks investigation');
  model.observe({ ...details(), intent: { key: 'unresolved-test' } }); assert(!state.available && !await model.run(), 'unresolved refund intent blocks investigation');
  model.observe({ ...details(), loading: true }); assert(!state.available, 'details loading blocks investigation');
  model.observe({ ...details(), gatewayState: 'loading' }); assert(!state.available, 'initial gateway refresh blocks investigation');
  reset(); window.fetch = () => new Promise(done => { resolve = done; }); const late = model.run(); model.observe(details('SUCCESS', other)); resolve(json(envelope())); await late;
  assert(state.payment.paymentId === other && !state.result && !state.busy, 'late success cannot populate another payment');
  reset(); window.fetch = () => new Promise(done => { resolve = done; }); const lateError = model.run(); model.observe(details('SUCCESS',other)); resolve(json({},503)); await lateError;
  assert(!state.result && state.phase === 'ready' && state.payment.paymentId === other, 'late error cannot replace new selection lifecycle');
  reset(); window.fetch = () => new Promise(done => { resolve = done; }); const stale = model.run(); model.observe({ ...details(), loading: true }); resolve(json(envelope())); await stale;
  assert(!state.result, 'refresh during investigation invalidates pending evidence snapshot');
  reset(); window.fetch = () => new Promise(done => { resolve = done; }); const loggedOut = model.run(); clearSession(); resolve(json(envelope())); await loggedOut;
  assert(!state.result && !state.payment && !state.busy, 'logout clears pending investigation and private results');
  reset(); window.fetch = () => new Promise(done => { resolve = done; }); const replaced = model.run(); setSession(tokenResponse(['ADMIN']), 'replacement'); model.observe(details('SUCCESS',other)); resolve(json({},401)); await replaced;
  assert(getSession().identity === 'replacement' && !state.result && state.payment.paymentId === other, 'late 401 cannot clear replacement session');
  reset(); window.fetch = async () => json(envelope()); await model.run(); Date.now = () => clock() + 901000; checkExpiry(); Date.now = clock;
  assert(!state.result && !state.payment, 'expiry clears investigation data');
  assert(sent.every(call => call.url.startsWith('/api/v1/payments/')), 'no direct Python or LLM browser calls');
  // Actual financial controllers retain guards while the read-only investigation owns its operation lock.
  reset(); let refundState;
  const refunds = createRefundWorkspace(next => { refundState = next; }, { mutationBlocked: () => model.busy() });
  window.fetch = async url => json(url.endsWith('/gateway-transactions') || url.endsWith('/refunds') ? [] : details().payment);
  await refunds.select(id); assert(refunds.eligible(), 'refund eligible before investigation lock');
  window.fetch = () => new Promise(done => { resolve = done; }); const busyAI = model.run();
  assert(!refunds.eligible() && !await refunds.review('1.00'), 'investigation lock blocks actual refund review');
  resolve(json(envelope())); await busyAI; assert(refunds.eligible(), 'refund availability restored after analysis'); refunds.dispose();
  let payState; const payments = createPaymentWorkflow(next => { payState = next; });
  payments.review({ merchantId: 'synthetic', amount: '1.00', currency: 'USD', customerId: 'synthetic', paymentMethod: 'CARD' });
  model.observe(details(), Boolean(payState.intent && payState.creation !== 'done'));
  assert(!state.available && !await model.run(), 'unsubmitted creation intent blocks AI'); payments.dispose();
  document.querySelector('#result').textContent = `PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch (error) { document.querySelector('#result').textContent = `FAIL: ${error.message}`; }
finally { Date.now = clock; window.fetch = original; clearSession(); model.dispose(); }
