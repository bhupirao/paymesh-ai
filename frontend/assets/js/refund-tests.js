import { createRefundWorkspace, validateGatewayHistory, validateRefund, refundSummary } from './features/refunds.js';
import { refundDecimal, minorUnits, formatMinor, serializeRefund, parsePaymentJSON } from './api/decimal.js';
import { renderHistory, safeGatewayError } from './components/history.js';
import { renderPayment } from './components/payment.js';
import { setSession, clearSession, getSession, checkExpiry } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
const original = window.fetch, clock = Date.now, results = [];
const assert = (value, label) => { if (!value) throw new Error(label); results.push(label); };
const rejects = (fn, label) => { let rejected = false; try { fn(); } catch { rejected = true; } assert(rejected, label); };
const a = '96829409-bb1a-4f82-b113-4bc9694bd2c0', b = '842b460e-2451-4294-abc7-62c5525bc180';
const r1 = '11111111-1111-4111-8111-111111111111', r2 = '22222222-2222-4222-8222-222222222222';
const payment = (id = a, changes = {}) => ({ paymentId: id, merchantId: 'explicit-test-merchant', amount: '500.00', currency: 'INR', customerId: 'test', paymentMethod: 'UPI', status: 'SUCCESS', createdAt: '2026-11-14T00:00:00Z', ...changes });
const refund = (amount = '200.00', id = r1, changes = {}) => ({ refundId: id, paymentId: a, amount, status: 'SUCCESS', createdAt: '2026-11-14T01:00:00Z', ...changes });
const gateway = (changes = {}) => ({ id: r1, paymentId: a, gatewayName: 'MOCK_RAZORPAY', gatewayTransactionId: null, status: 'INITIATED', errorCode: null, errorMessage: null, createdAt: '2026-11-14T00:00:01Z', updatedAt: '2026-11-14T00:00:01Z', ...changes });
const response = (data, status = 200) => new Response(JSON.stringify(data), { status });
let serverPayment = payment(), records = [], gateways = [], sent = [], postBehavior, readFailure = false;
function router(url, options) {
  sent.push({ url, ...options });
  if (options.method === 'POST') return postBehavior(url, options);
  if (readFailure) return Promise.resolve(response({}, 503));
  if (url.endsWith('/gateway-transactions')) return Promise.resolve(response(gateways));
  if (url.endsWith('/refunds')) return Promise.resolve(response(records));
  return Promise.resolve(response(serverPayment));
}
let state, externalBusy = false, updates = 0;
const model = createRefundWorkspace(next => { state = next; }, { otherBusy: () => externalBusy, onPayment: () => { updates++; } });
model.start();
async function reset() {
  clearSession(); setSession(tokenResponse(), 'test'); serverPayment = payment(); records = []; gateways = []; sent = []; readFailure = false; externalBusy = false;
  window.fetch = router; await model.select(a);
}
try {
  assert(refundDecimal('99999999999999999.99') === '99999999999999999.99', '17 integer digit refund limit');
  assert(formatMinor(minorUnits('99999999999999999.99', true)) === '99999999999999999.99', 'maximum refund minor units exact');
  for (const value of ['0','0.00','-1','+1','01','1e2','1.001','100000000000000000','1,000',' 1',1]) rejects(() => refundDecimal(value), 'invalid refund decimal');
  assert(serializeRefund({ amount: '200' }) === '{"amount":200.00}', 'exact refund numeric JSON');
  assert(parsePaymentJSON('{"amount":99999999999999999.99}').amount === '99999999999999999.99', 'refund response lexeme preserved');
  const partial = refundSummary(payment(), [refund()]);
  assert(partial.original === '500.00' && partial.successful === '200.00' && partial.remaining === '300.00' && partial.eligible, 'partial refund exact totals');
  const full = refundSummary(payment(a, { status: 'REFUNDED' }), [refund(), refund('300.00', r2)]);
  assert(full.successful === '500.00' && full.remaining === '0.00' && !full.eligible, 'full refund exact totals');
  assert(refundSummary(payment(a, { amount: '999999999999.99' }), [refund('999999999999.98')]).remaining === '0.01', 'maximum payment arithmetic exact');
  assert(refundSummary(payment(), []).successful === '0.00', 'valid empty history is zero');
  for (const rows of [null, {}, [refund(), refund()], [refund('501.00')], [refund('200.001')], [refund('1.00', r1, { paymentId: b })], [refund('1', 'bad')], [refund('1', r1, { createdAt: '2026-02-30T00:00:00Z' })], [refund('1', r1, { amount: 1 })], [refund('1', r1, { status: 'FAILED' })], [refund('1', r1, { status: 'PENDING' })]]) rejects(() => refundSummary(payment(), rows), 'malformed duplicate mismatched or unresolved history rejected');
  for (const status of ['CREATED','PROCESSING','FAILED','CANCELLED']) {
    assert(!refundSummary(payment(a, { status }), []).eligible, `${status} refund disabled`);
    rejects(() => refundSummary(payment(a, { status }), [refund()]), `${status} incompatible refund history rejected`);
  }
  rejects(() => refundSummary(payment(a, { status: 'REFUNDED' }), []), 'REFUNDED with missing totals rejected');
  rejects(() => refundSummary(payment(), [refund('500.00')]), 'SUCCESS with fully refunded history rejected');
  assert(validateGatewayHistory([], a).length === 0, 'empty gateway history');
  assert(validateGatewayHistory([gateway()], a)[0].gatewayTransactionId === null, 'nullable provider UUID and errors');
  for (const status of ['INITIATED','UNKNOWN','TIMEOUT','SUCCESS','FAILED']) assert(validateGatewayHistory([gateway({ status })], a)[0].status === status, `actual gateway status ${status}`);
  for (const changes of [{ paymentId: b }, { id: 'bad' }, { gatewayTransactionId: 'bad' }, { status: 'RETRIED' }, { updatedAt: '2020-01-01T00:00:00Z' }, { errorCode: {} }]) rejects(() => validateGatewayHistory([gateway(changes)], a), 'malformed gateway row rejected');
  rejects(() => validateGatewayHistory([gateway(), gateway()], a), 'duplicate gateway UUID rejected');
  assert(!safeGatewayError(gateway({ errorCode: 'SECRET', errorMessage: 'password=do-not-render' })).includes('password'), 'stored gateway exception text withheld');
  await reset();
  assert(sent.some(call => call.url === `/api/v1/payments/${a}/gateway-transactions` && call.method === 'GET' && call.headers.Authorization.startsWith('Bearer ')), 'authorized gateway endpoint');
  assert(sent.some(call => call.url === `/api/v1/payments/${a}/refunds` && call.method === 'GET'), 'complete refund endpoint');
  assert(state.gatewayState === 'ready' && state.gateways.length === 0 && state.history.length === 0 && model.eligible(), 'empty history loaded safely');
  assert(updates > 0 && state.payment.status === 'SUCCESS', 'authoritative payment published');
  gateways = [gateway({ gatewayTransactionId: r2, status: 'SUCCESS' })]; await model.loadGateways();
  assert(state.gateways[0].gatewayName === 'MOCK_RAZORPAY' && state.gateways[0].gatewayTransactionId === r2, 'actual gateway fields loaded');
  gateways = [gateway({ paymentId: b })]; await model.loadGateways();
  assert(state.gatewayState === 'error' && !state.gateways, 'mismatched gateway history withheld');
  records = [refund()]; await model.refresh();
  assert(state.summary.remaining === '300.00', 'complete refund history refresh');
  records = []; await model.refresh();
  assert(!state.summary && !model.eligible(), 'previously observed record cannot disappear');
  records = [refund()]; await model.refresh();
  assert(model.eligible(), 'valid complete history restores eligibility');
  readFailure = true; await model.refresh();
  assert(!state.history && !state.summary && !model.eligible(), 'unavailable history never becomes zero');
  await reset();
  for (const amount of ['0.00','501','1.001','invalid']) assert(!await model.review(amount) && !state.intent, 'invalid or excessive amount never reviewed');
  sent = []; assert(await model.review('200') && !sent.some(call => call.method === 'POST'), 'review revalidates and does not submit');
  const intent = state.intent;
  assert(intent.body.amount === '200.00' && intent.remainingAfter === '300.00' && intent.successful === '0.00', 'review exact values');
  assert(!await model.select(b) && state.selected === a && !model.clear(), 'cannot switch or clear during refund intent');
  assert(!await model.review('1'), 'second review cannot replace intent');
  assert(model.cancelReview() && !state.intent && model.eligible(), 'unsubmitted review can cancel');
  await model.review('200.00'); assert(state.intent.key !== intent.key, 'new refund intent gets new key');
  let resolve;
  postBehavior = () => new Promise(done => { resolve = done; });
  sent = []; const pending = model.submit(); await model.submit();
  assert(sent.length === 1 && state.phase === 'pending', 'duplicate pending refund prevented');
  assert(sent[0].url === `/api/v1/payments/${a}/refund` && sent[0].method === 'POST' && sent[0].body === '{"amount":200.00}', 'refund exact URL method and numeric bytes');
  assert(sent[0].headers['Idempotency-Key'] === state.intent.key && sent[0].headers.Authorization.startsWith('Bearer '), 'refund auth and key');
  assert(!await model.select(b), 'pending refund blocks payment switch');
  const bytes = sent[0].body, key = state.intent.key;
  resolve(response({}, 504)); await pending;
  assert(state.phase === 'uncertain' && state.intent.key === key && !model.eligible(), 'uncertain outcome retains intent and blocks new refunds');
  assert(!await model.select(b) && state.selected === a, 'uncertain refund prevents switching payment');
  assert(!await model.releaseRejected() && !model.cancelReview(), 'uncertain intent cannot be discarded as rejected');
  let releaseRefresh;
  window.fetch = (url, options) => {
    if (url === `/api/v1/payments/${a}`) return new Promise(done => { releaseRefresh = done; });
    return router(url, options);
  };
  const simultaneousRefresh = model.refresh();
  const postCountBeforeRefresh = sent.filter(call => call.method === 'POST').length;
  await model.submit();
  assert(sent.filter(call => call.method === 'POST').length === postCountBeforeRefresh && state.phase === 'uncertain', 'uncertain retry blocked during authoritative refresh');
  window.fetch = router; releaseRefresh(response(serverPayment)); await simultaneousRefresh;
  // Server accepted the lost request; retry returns its stored record.
  records = [refund()];
  postBehavior = () => Promise.resolve(response(refund(), 200));
  await model.submit();
  const posts = sent.filter(call => call.method === 'POST');
  assert(posts[1].body === bytes && posts[1].headers['Idempotency-Key'] === key, 'uncertain retry exact key and bytes');
  assert(state.phase === 'done' && state.confirmed.refundId === r1 && state.summary.remaining === '300.00' && state.payment.status === 'SUCCESS', '200 replay then authoritative partial refresh');
  const container = document.querySelector('#render-test'); renderPayment(container, state.payment);
  assert(container.textContent.includes('SUCCESS'), 'actual partial payment status rendered');
  await model.review('300.00');
  postBehavior = () => { records = [refund(), refund('300.00', r2)]; serverPayment = payment(a, { status: 'REFUNDED' }); return Promise.resolve(response(refund('300.00', r2), 201)); };
  await model.submit();
  assert(state.confirmed.refundId === r2 && state.summary.successful === '500.00' && state.summary.remaining === '0.00' && state.payment.status === 'REFUNDED', '201 full refund authoritative totals and status');
  assert(!model.eligible() && !await model.review('0.01'), 'fully refunded payment cannot refund');
  renderPayment(container, state.payment); assert(container.textContent.includes('REFUNDED'), 'actual full payment status rendered');
  await reset(); await model.review('500');
  const fullKey = state.intent.key;
  postBehavior = () => { records = [refund('500.00')]; serverPayment = payment(a, { status: 'REFUNDED' }); return Promise.reject(new TypeError('lost response')); };
  await model.submit(); await model.refresh();
  assert(state.phase === 'uncertain' && !model.eligible() && state.payment.status === 'REFUNDED', 'unresolved full refund stays locked after refreshed REFUNDED state');
  postBehavior = () => Promise.resolve(response(refund('500.00'), 200)); await model.submit();
  assert(state.phase === 'done' && state.confirmedStatus === 200 && state.summary.remaining === '0.00' && sent.filter(call => call.method === 'POST').every(call => call.headers['Idempotency-Key'] === fullKey), 'exact replay recovers full refund despite terminal lifecycle');
  await reset(); await model.review('200');
  postBehavior = () => { readFailure = true; return Promise.resolve(response(refund(), 201)); };
  await model.submit();
  assert(state.confirmed && !state.summary && state.message.includes('record is confirmed') && !model.eligible(), 'confirmed refund plus refresh failure distinct and blocked');
  readFailure = false; records = []; await model.refresh();
  assert(!state.summary && !model.eligible(), 'confirmed record missing from history blocks totals');
  records = [refund()]; await model.refresh(); assert(model.eligible() && state.summary.remaining === '300.00', 'confirmed record refresh recovery');
  for (const code of [400,403,404,409,413,415,422,429,502,503,504]) {
    await reset(); await model.review('1.00'); postBehavior = () => Promise.resolve(response({}, code)); await model.submit();
    assert(state.intent && !state.summary && !model.eligible() && state.phase === (code >= 500 ? 'uncertain' : 'rejected'), `refund ${code} safe blocking`);
    if (code === 409) { sent = []; await model.submit(); assert(!sent.length, '409 not blindly resubmitted'); assert(await model.releaseRejected() && !state.intent, 'rejected intent releases only after authorized refresh'); }
  }
  for (const data of [refund('1.00'), refund('200.00', r1, { paymentId: b }), refund('200', 'bad'), refund('200', r1, { status: 'PENDING' })]) {
    await reset(); await model.review('200'); postBehavior = () => Promise.resolve(response(data, 201)); await model.submit();
    assert(state.phase === 'uncertain' && !state.confirmed && state.intent, 'mismatched refund response uncertain');
  }
  await reset(); await model.review('200'); postBehavior = () => Promise.resolve(new Response('bad', { status: 201 })); await model.submit(); assert(state.phase === 'uncertain', 'malformed refund response uncertain');
  await reset(); await model.review('200'); postBehavior = () => Promise.reject(new TypeError('network')); await model.submit(); assert(state.phase === 'uncertain', 'network refund uncertainty');
  await reset(); await model.review('200'); postBehavior = () => Promise.resolve(response({}, 401)); await model.submit(); assert(!getSession() && !state.intent && !state.payment && !state.gateways && !state.history, 'refund 401 clears all private state');
  await reset(); await model.review('200'); postBehavior = () => new Promise(done => { resolve = done; });
  const stale = model.submit(); clearSession(); setSession(tokenResponse(['ADMIN']), 'replacement'); resolve(response({}, 401)); await stale;
  assert(getSession().identity === 'replacement' && !state.intent && !state.confirmed, 'late refund 401 preserves replacement');
  await reset(); await model.review('200'); Date.now = () => clock() + 901000; checkExpiry(); Date.now = clock;
  assert(!state.selected && !state.intent && !state.confirmed && !state.history, 'expiry clears private refund data');
  await reset(); serverPayment = payment(a, { amount: '600.00' }); await model.refresh();
  assert(!state.summary && !model.eligible(), 'immutable payment amount change blocks refund availability');
  await reset(); await model.review('200'); sent = []; Date.now = () => clock() + 31000; await model.submit(); Date.now = clock;
  assert(!sent.length && state.phase === 'review', 'expired review never submits');
  await reset();
  window.fetch = (url, options) => {
    if (url.endsWith('/refunds')) return Promise.resolve(response([], 503));
    return router(url, options);
  };
  assert(!await model.review('1') && !state.intent && !state.summary, 'review cannot freeze intent when history refresh fails');
  await reset(); let resolveHistory, historyStarted;
  const historyReady = new Promise(done => { historyStarted = done; });
  window.fetch = (url, options) => {
    if (url.includes(a) && url.endsWith('/refunds')) return new Promise(done => { resolveHistory = done; historyStarted(); });
    if (url.includes(b)) return Promise.resolve(response(url.endsWith('/gateway-transactions') || url.endsWith('/refunds') ? [] : payment(b, { currency: 'USD', amount: '25.00', paymentMethod: 'CARD' })));
    return router(url, options);
  };
  const historyPending = model.refresh(); await historyReady; await model.select(b); resolveHistory(response([refund()])); await historyPending;
  assert(state.selected === b && state.payment.paymentId === b && state.history.length === 0 && state.summary.remaining === '25.00', 'late refund history cannot populate another payment');
  await reset(); externalBusy = true; assert(!await model.review('1') && !await model.select(b), 'other financial operation blocks refund navigation'); externalBusy = false;
  Date.now = () => clock() + 31000; assert(!model.eligible() && !await model.review('1'), 'stale snapshot blocks new refunds'); Date.now = clock;
  await reset(); let resolveOld;
  window.fetch = (url, options) => url.includes(a) ? new Promise(done => { if (url.endsWith('gateway-transactions')) resolveOld = done; else done(response(payment())); }) : Promise.resolve(response(url.endsWith('gateway-transactions') || url.endsWith('refunds') ? [] : payment(b, { currency: 'USD', amount: '25.00', paymentMethod: 'CARD' })));
  const oldSelection = model.select(a); await model.select(b); resolveOld(response([gateway()])); await oldSelection;
  assert(state.selected === b && state.payment.paymentId === b && state.gateways.length === 0, 'late gateway cannot expose previous payment');
  renderHistory(container, [gateway({ gatewayName: '<img src=x>', errorMessage: 'secret-private', errorCode: 'UNKNOWN_SECRET' })], 'gateway');
  assert(container.textContent.includes('<img src=x>') && !container.querySelector('img') && !container.textContent.includes('secret-private'), 'safe history DOM and exception suppression');
  renderHistory(container, [refund()], 'refund'); assert(container.textContent.includes(r1) && container.textContent.includes('200.00'), 'actual refund record rendering');
  document.querySelector('#result').textContent = `PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch (error) { document.querySelector('#result').textContent = `FAIL: ${error.message}`; }
finally { Date.now = clock; window.fetch = original; clearSession(); model.dispose(); }
