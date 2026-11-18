import { request } from './api/client.js';
import { setSession, getToken, clearSession } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
import { checkExpiry } from './auth/session.js';
const original = window.fetch;
const results = [];
function assert(value, label) { if (!value) throw new Error(label); results.push(label); }
async function rejects(fn, status) { try { await fn(); } catch (e) { assert(e.status === status, `rejected with status ${status}`); return; } throw new Error('Expected rejection'); }
try {
  let calls = 0;
  window.fetch = async (url, options) => { calls++; assert(url === '/api/v1/payments/health', 'same-origin URL'); assert(options.redirect === 'error', 'redirects denied'); return new Response('{"status":"RUNNING"}'); };
  assert((await request('/payments/health')).status === 'RUNNING', 'JSON response');
  await rejects(() => request('https://evil.example'), 0);
  assert(calls === 1, 'unsupported path never fetched');
  setSession(tokenResponse());
  window.fetch = async () => new Response('{"message":"Authentication failed"}', { status: 401 });
  await rejects(() => request('/payments/health'), 401);
  assert(getToken() === null, '401 clears session');
  setSession(tokenResponse());
  const clock = Date.now; Date.now = () => clock() + 901000; checkExpiry(); Date.now = clock;
  assert(getToken() === null, 'expired session discarded');
  let finish;
  window.fetch = () => new Promise(resolve => { finish = resolve; });
  const pending = request('/payments/health');
  await rejects(() => request('/payments/health'), 0);
  finish(new Response('{}')); await pending;
  window.fetch = async () => new Response('invalid');
  await rejects(() => request('/payments/health'), 200);
  document.querySelector('#result').textContent = `PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch (error) { document.querySelector('#result').textContent = `FAIL: ${error.message}`; }
finally { window.fetch = original; clearSession(); }
