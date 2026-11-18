import { decimal, parsePaymentJSON, serializeCreation } from './api/decimal.js';
import { createPaymentWorkflow, validateIntent, canProcess } from './features/payments.js';
import { tokenResponse, paymentId } from './test-fixtures.js';
import { setSession, clearSession, getSession, checkExpiry } from './auth/session.js';
import { renderPayment } from './components/payment.js';
const original = window.fetch, clock = Date.now, results = [];
const assert = (value, label) => { if (!value) throw new Error(label); results.push(label); };
const reject = (fn, label) => { let failed = false; try { fn(); } catch { failed = true; } assert(failed, label); };
const input = () => ({ merchantId: 'explicit-merchant', amount: '999999999999.99', currency: 'INR', customerId: 'customer', paymentMethod: 'UPI' });
const returned = (status = 'CREATED', changes = {}) => ({ ...input(), paymentId, status, createdAt: '2026-11-14T00:00:00Z', ...changes });
const json = (data, status = 200) => new Response(JSON.stringify(data), { status });
let state, sent = [];
const flow = createPaymentWorkflow(value => { state = value; });
flow.start();
try {
  for (const value of ['0.01', '1', '1.2', '1.20', '999999999999.99']) assert(decimal(value).endsWith(value === '1' ? '.00' : value === '1.2' ? '.20' : value), `valid decimal ${value}`);
  for (const value of ['0', '0.00', '-1', '+1', '01', '.01', '1.', '1.001', '1000000000000', '1e2', 'NaN', '1,000', ' 1', 1]) reject(() => decimal(value), 'invalid decimal rejected');
  for (const field of ['merchantId', 'customerId', 'paymentMethod']) reject(() => validateIntent({ ...input(), [field]: ' ' }), `${field} required`);
  reject(() => validateIntent({ ...input(), currency: 'EUR' }), 'currency restricted');
  reject(() => validateIntent({ ...input(), customerId: 'x'.repeat(17000) }), 'request size bounded');
  assert(validateIntent({ ...input(), paymentMethod: 'CUSTOM_LABEL', currency: 'USD' }).paymentMethod === 'CUSTOM_LABEL', 'actual nonblank method contract');
  assert(serializeCreation(validateIntent(input())).includes('"amount":999999999999.99'), 'exact numeric JSON amount without Number conversion');
  const parsed = parsePaymentJSON('{"amount":999999999999.99,"customerId":"amount: 123 \\"","nested":{"amount":0.01}}');
  assert(parsed.amount === '999999999999.99' && parsed.nested.amount === '0.01', 'lossless response amount parsing');
  setSession(tokenResponse(), 'test');
  window.fetch = async (url, options) => { sent.push({ url, ...options }); return json(returned(), 201); };
  assert(flow.review(input()) && sent.length === 0 && state.creation === 'review', 'review does not submit');
  const firstKey = state.intent.key;
  assert(/^[0-9a-f-]{36}$/.test(firstKey), 'crypto UUID intent key');
  assert(!flow.review({ ...input(), amount: '1' }) && state.intent.body.amount === input().amount, 'locked intent cannot change');
  await flow.submit();
  assert(sent[0].url === '/api/v1/payments' && sent[0].method === 'POST', 'creation method and URL');
  assert(sent[0].headers['Idempotency-Key'] === firstKey && sent[0].headers.Authorization.startsWith('Bearer '), 'creation auth and key headers');
  assert(sent[0].body === serializeCreation(validateIntent(input())), 'exact confirmed request body');
  assert(state.creation === 'done' && state.created.paymentId === paymentId && state.message.includes('201'), '201 creation accepted');
  assert(sent.length === 1, 'creation never automatically processes');
  flow.newIntent(); flow.review(input()); assert(state.intent.key !== firstKey, 'new intent new key');
  let resolve;
  window.fetch = (url, options) => { sent.push({ url, ...options }); return new Promise(done => { resolve = done; }); };
  const pending = flow.submit(); await flow.submit();
  assert(state.creation === 'pending' && sent.length === 2, 'duplicate creation blocked');
  assert(!flow.newIntent(true), 'new intent blocked while pending');
  resolve(json({}, 504)); await pending;
  assert(state.creation === 'uncertain' && state.message.includes('same key'), '504 creation uncertainty');
  const retryKey = state.intent.key, retryBody = sent[1].body;
  assert(!flow.newIntent() && state.intent.key === retryKey, 'unresolved new intent needs acknowledgement');
  window.fetch = async (url, options) => { sent.push({ url, ...options }); return json(returned('SUCCESS'), 200); };
  await flow.submit();
  assert(sent[2].headers['Idempotency-Key'] === retryKey && sent[2].body === retryBody, 'uncertain retry retains exact key and bytes');
  assert(state.creation === 'done' && state.message.includes('200') && state.created.status === 'SUCCESS', '200 replay accepts current lifecycle status');
  for (const [code, fragment] of [[400,'rejected'],[403,'Access denied'],[404,'not accessible'],[409,'Idempotency conflict'],[413,'size limit'],[502,'uncertain'],[503,'uncertain']]) {
    flow.newIntent(true); flow.review(input()); window.fetch = async () => json({}, code); await flow.submit();
    assert(state.message.includes(fragment), `creation ${code} feedback`);
  }
  for (const mismatch of [{ merchantId: 'other' }, { amount: '0.01' }, { paymentId: 'bad' }, { currency: 'USD' }, { status: 'SUCCESS' }]) {
    flow.newIntent(true); flow.review(input()); window.fetch = async () => json(returned('CREATED', mismatch), 201); await flow.submit();
    assert(state.creation === 'uncertain' && !state.created, 'mismatched creation response never succeeds');
  }
  flow.newIntent(true); flow.review(input()); window.fetch = async () => new Response('malformed', { status: 201 }); await flow.submit();
  assert(state.creation === 'uncertain', 'malformed creation response uncertain');
  flow.newIntent(true); flow.review(input()); window.fetch = async () => { throw new TypeError('network'); }; await flow.submit();
  assert(state.creation === 'uncertain', 'lost response retains recoverable intent');
  for (const status of ['PROCESSING','SUCCESS','REFUNDED','FAILED','CANCELLED']) assert(!canProcess(returned(status)) && !flow.reviewProcess(returned(status)), `cannot process ${status}`);
  assert(canProcess(returned()), 'CREATED is eligible');
  sent = [];
  window.fetch = async (url, options) => { sent.push({ url, ...options }); return json(returned('SUCCESS')); };
  await flow.process(); assert(sent.length === 0, 'processing requires explicit review');
  assert(flow.reviewProcess(returned()) && sent.length === 0 && state.processReview.amount === input().amount, 'processing review keeps confirmed details');
  await flow.process();
  assert(sent[0].url === `/api/v1/payments/${paymentId}/process` && sent[0].method === 'POST' && sent[0].body === undefined && !('Idempotency-Key' in sent[0].headers), 'process request no body or invented key');
  assert(state.updated.status === 'SUCCESS' && state.processMessage.includes('SUCCESS'), 'processing SUCCESS');
  for (const status of ['SUCCESS','FAILED','PROCESSING']) {
    flow.observeLookup(returned()); flow.reviewProcess(returned()); window.fetch = async () => json(returned(status)); await flow.process();
    assert(state.updated.status === status && state.processMessage.includes(status), `${status} actual status feedback`);
    const container = document.querySelector('#render-test'); renderPayment(container, state.updated);
    assert(container.textContent.includes(status), `${status} rendered accessibly as text`);
    assert(!flow.eligible(returned(status)), `${status} not reprocessable`);
  }
  flow.observeLookup(returned()); flow.reviewProcess(returned());
  window.fetch = () => new Promise(done => { resolve = done; });
  const processing = flow.process(); await flow.process();
  assert(state.processBusy && !flow.reviewProcess(returned()), 'duplicate processing blocked');
  resolve(json({}, 503)); await processing;
  assert(state.processMessage.includes('does not mean payment failure') && state.processMessage.includes('Look up'), 'uncertain gateway outcome lookup guidance');
  assert(!flow.eligible(returned()) && !state.processReview, 'uncertain processing blocked until fresh lookup');
  flow.observeLookup(returned()); assert(flow.eligible(returned()), 'fresh authorized CREATED lookup required before reconsideration');
  flow.reviewProcess(returned()); window.fetch = async () => json({}, 409); await flow.process();
  assert(state.processMessage.includes('conflict') && !flow.eligible(returned()), '409 processing requires lookup');
  flow.observeLookup(returned()); flow.reviewProcess(returned()); window.fetch = async () => json(returned('SUCCESS', { amount: '1.00' })); await flow.process();
  assert(state.processMessage.includes('uncertain'), 'mismatched process response uncertain');
  for (const [code, fragment] of [[400,'rejected'],[403,'Access denied'],[404,'not accessible'],[413,'size limit'],[502,'uncertain'],[504,'uncertain']]) {
    flow.observeLookup(returned()); flow.reviewProcess(returned()); window.fetch = async () => json({}, code); await flow.process();
    assert(state.processMessage.includes(fragment) && !flow.eligible(returned()), `process ${code} safe feedback and lookup requirement`);
  }
  flow.newIntent(true); flow.review(input()); window.fetch = async () => json({}, 401); await flow.submit();
  assert(!getSession() && !state.intent && !state.created, 'creation 401 clears intent and session');
  setSession(tokenResponse()); flow.review(input());
  window.fetch = async () => { throw new DOMException('timeout', 'AbortError'); }; await flow.submit();
  assert(state.creation === 'uncertain' && state.intent, 'creation timeout retains exact intent');
  const container = document.querySelector('#render-test'); renderPayment(container, returned('CREATED', { customerId: '<img src=x onerror=alert(1)>' }));
  assert(container.textContent.includes('<img') && !container.querySelector('img'), 'safe payment DOM rendering');
  clearSession(); assert(!state.intent && !state.created && !state.updated && !state.processReview, 'logout clears all private payment state');
  setSession(tokenResponse()); flow.review(input()); window.fetch = () => new Promise(done => { resolve = done; });
  const stale = flow.submit(); setSession(tokenResponse(['ADMIN']), 'replacement'); resolve(json(returned(), 201)); await stale;
  assert(!state.intent && !state.created && getSession().identity === 'replacement', 'late creation cannot populate replacement session');
  flow.observeLookup(returned()); flow.reviewProcess(returned()); window.fetch = () => new Promise(done => { resolve = done; });
  const staleProcess = flow.process(); clearSession(); setSession(tokenResponse(), 'next'); resolve(json({}, 401)); await staleProcess;
  assert(getSession().identity === 'next' && !state.updated && !state.processReview, 'late process 401 cannot clear replacement session');
  flow.review(input()); Date.now = () => clock() + 901000; checkExpiry(); Date.now = clock;
  assert(!state.intent && !state.created && !state.updated && !state.processReview, 'expiry clears private intents and results');
  document.querySelector('#result').textContent = `PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch (error) { document.querySelector('#result').textContent = `FAIL: ${error.message}`; }
finally { Date.now = clock; window.fetch = original; clearSession(); flow.dispose(); }
