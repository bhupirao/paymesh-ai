import { validateLogin, setSession, getSession, getToken, clearSession, checkExpiry, installLifecycle } from './auth/session.js';
import { request, ApiError } from './api/client.js';
import { createWorkspace, rolePresentation } from './features/workspace.js';
import { renderPayment } from './components/payment.js';
import { tokenResponse, payment, paymentId } from './test-fixtures.js';
const original = window.fetch, clock = Date.now;
const results = [];
const assert = (value, label) => { if (!value) throw new Error(label); results.push(label); };
const json = (data, status = 200, headers = {}) => new Response(JSON.stringify(data), { status, headers });
let state;
const workspace = createWorkspace(value => { state = value; });
workspace.start();
try {
  assert(validateLogin(tokenResponse()).roles[0] === 'MERCHANT', 'valid login contract');
  for (const response of [null, {}, { ...tokenResponse(), accessToken: 'invalid' }, { ...tokenResponse(), expiresIn: 1 }, tokenResponse(['UNKNOWN']), { ...tokenResponse(), expiresAt: new Date(0).toISOString() }]) {
    let rejected = false; try { validateLogin(response); } catch { rejected = true; }
    assert(rejected, 'malformed login rejected');
  }
  assert(rolePresentation(['MERCHANT']).title === 'Merchant workspace', 'merchant presentation');
  assert(rolePresentation(['ADMIN', 'MERCHANT']).title === 'Admin workspace', 'admin presentation');
  let calls = 0, resolveLogin;
  window.fetch = () => { calls++; return new Promise(resolve => { resolveLogin = resolve; }); };
  const login = workspace.login('test-operator', 'synthetic-password');
  assert(state.loginBusy, 'login loading state');
  await workspace.login('test-operator', 'synthetic-password');
  assert(calls === 1, 'duplicate login prevented');
  resolveLogin(json(tokenResponse())); await login;
  assert(state.session.identity === 'test-operator' && !state.loginBusy, 'login accepts validated session');
  workspace.logout(); assert(!state.session && !state.payment && !getToken(), 'logout clears private state');
  window.fetch = async () => json({}, 401);
  await workspace.login('test', 'synthetic');
  assert(state.message.includes('Check your username') && !state.loginBusy, 'generic invalid credentials');
  window.fetch = async () => json({}, 429, { 'Retry-After': '60' });
  await workspace.login('test', 'synthetic');
  assert(state.message.includes('60 seconds'), 'rate limit feedback');
  window.fetch = async () => json({}, 503); await workspace.login('test', 'synthetic');
  assert(state.message.includes('temporarily unavailable'), 'unavailable feedback');
  window.fetch = async () => { throw new TypeError('network'); }; await workspace.login('test', 'synthetic');
  assert(state.message.includes('connection'), 'network feedback');
  window.fetch = async () => json({ ...tokenResponse(), accessToken: 'malformed' }); await workspace.login('test', 'synthetic');
  assert(!state.session && state.message.includes('Invalid authentication response'), 'malformed token never accepted');
  window.fetch = () => new Promise(resolve => { resolveLogin = resolve; });
  const staleLogin = workspace.login('test', 'synthetic'); workspace.logout(); resolveLogin(json(tokenResponse())); await staleLogin;
  assert(!getSession(), 'logout invalidates pending login');
  setSession(tokenResponse(), 'test');
  calls = 0; window.fetch = async (url, options) => { calls++; assert(url === `/api/v1/payments/${paymentId}`, 'exact lookup route'); assert(options.headers.Authorization.startsWith('Bearer '), 'authorized lookup header'); return json(payment()); };
  for (const id of ['invalid', paymentId.replaceAll('-', ''), ` ${paymentId}`, `${paymentId}?x=1`]) await workspace.lookup(id);
  assert(calls === 0 && state.message.includes('canonical'), 'invalid UUID never fetched');
  await workspace.lookup(paymentId);
  assert(state.payment.paymentId === paymentId && !state.lookupBusy, 'authorized lookup success');
  const container = document.querySelector('#render-test'); renderPayment(container, state.payment);
  assert(container.textContent.includes('<img src=x onerror=alert(1)>') && !container.querySelector('img'), 'untrusted values rendered only as text');
  assert(container.querySelectorAll('dt').length === 8, 'all eight payment fields rendered');
  window.fetch = async () => json({}, 404); await workspace.lookup(paymentId);
  assert(state.message.includes('not found or not accessible') && !state.payment, '404 conceals existence and clears old result');
  window.fetch = async () => json({}, 403); await workspace.lookup(paymentId);
  assert(getSession() && state.message.includes('Access denied'), '403 retains session');
  window.fetch = async () => json({}, 401); await workspace.lookup(paymentId);
  assert(!getSession() && !state.payment && state.message.includes('no longer valid'), '401 clears private UI');
  setSession(tokenResponse(), 'old');
  let resolveLookup;
  window.fetch = () => new Promise(resolve => { resolveLookup = resolve; });
  const staleLookup = workspace.lookup(paymentId); workspace.logout(); setSession(tokenResponse(['ADMIN']), 'replacement');
  resolveLookup(json({}, 401)); await staleLookup;
  assert(getSession().identity === 'replacement' && !state.payment, 'stale 401 cannot clear replacement session');
  window.fetch = () => new Promise(resolve => { resolveLookup = resolve; });
  const staleSuccess = workspace.lookup(paymentId); workspace.logout(); resolveLookup(json(payment())); await staleSuccess;
  assert(!state.session && !state.payment, 'late success after logout ignored');
  setSession(tokenResponse());
  const focusTarget = new EventTarget(), visibilityTarget = new EventTarget();
  const remove = installLifecycle(focusTarget, visibilityTarget);
  Date.now = () => clock() + 901000; focusTarget.dispatchEvent(new Event('focus'));
  assert(!getSession() && state.message.includes('expired'), 'focus detects expiry');
  Date.now = clock; setSession(tokenResponse()); Date.now = () => clock() + 901000;
  visibilityTarget.dispatchEvent(new Event('visibilitychange'));
  assert(!getSession(), 'visibility detects expiry'); remove(); Date.now = clock;
  const originalTimeout = globalThis.setTimeout;
  let expiryCallback, delay;
  try {
    globalThis.setTimeout = (callback, ms) => { expiryCallback = callback; delay = ms; return 0; };
    setSession(tokenResponse());
  } finally { globalThis.setTimeout = originalTimeout; }
  assert(delay > 898000 && delay <= 900000, 'timer follows expiresAt');
  Date.now = () => clock() + 901000; expiryCallback(); Date.now = clock;
  assert(!getSession(), 'automatic expiry callback clears session');
  document.querySelector('#result').textContent = `PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch (error) { document.querySelector('#result').textContent = `FAIL: ${error.message}`; }
finally { Date.now = clock; window.fetch = original; clearSession(); workspace.dispose(); }
