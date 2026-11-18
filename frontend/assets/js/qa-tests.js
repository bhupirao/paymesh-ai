import { request } from './api/client.js';
import { setSession, clearSession, getToken } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
import { envelope, selectedPayment, fixturePaymentId } from './investigation/fixtures.js';
import { renderInvestigation } from './investigation/render.js';
import { mountRefunds } from './features/refunds-view.js';
const original = window.fetch, results = [];
const assert = (value, label) => { if (!value) throw new Error(label); results.push(label); };
try {
  for (const status of [403,503,401]) {
    setSession(tokenResponse(), 'synthetic-qa');
    window.fetch = async () => new Response('null', { status });
    let failure;
    try { await request(`/payments/${fixturePaymentId}`); } catch (error) { failure = error; }
    assert(failure?.status === status, `null JSON error preserves HTTP ${status}`);
    assert(failure?.message === 'Request failed', 'error remains fixed safe text');
    assert(status === 401 ? getToken() === null : Boolean(getToken()), '401 clears session while non-401 retains it');
  }
  const container = document.querySelector('#render-test'), response = envelope();
  renderInvestigation(container, response);
  assert(container.textContent.includes(response.investigation.generatedAt), 'actual generatedAt timestamp preserved');
  assert(container.textContent.includes('Analysis prepared at (generatedAt)'), 'timestamp labeled as deterministic analysis preparation');
  assert(container.textContent.includes('before retrieval and LLM generation') && container.textContent.includes('not inference duration'), 'timing semantics explicitly distinguish model duration');
  // Mount the actual details view with minimal native DOM fixture, not a duplicate renderer.
  const fixture = document.querySelector('#qa-fixture');
  const outer = document.createElement('section'); outer.id = 'details-workspace'; fixture.append(outer);
  const form = document.createElement('form'); form.id = 'refund-form'; outer.append(form);
  const fields = document.createElement('fieldset'); fields.id = 'refund-fields'; form.append(fields);
  const amount = document.createElement('input'); amount.id = 'refund-amount'; fields.append(amount);
  for (const id of ['details-id','details-overview-result','details-feedback','gateway-feedback','gateway-history','refund-history','refund-summary','refund-availability','refund-review','refund-review-details','confirmed-refund','confirmed-refund-title','confirmed-refund-record']) {
    const node = document.createElement('div'); node.id = id; outer.append(node);
  }
  for (const id of ['refresh-details','refresh-gateways','use-remaining','confirm-refund','cancel-refund-review','release-rejected-refund']) {
    const button = document.createElement('button'); button.id = id; button.type = 'button'; outer.append(button);
  }
  const $ = id => document.getElementById(id);
  setSession(tokenResponse(), 'synthetic-qa');
  let release;
  window.fetch = async url => url.endsWith('/gateway-transactions') || url.endsWith('/refunds') ? new Response('[]') : new Promise(resolve => { release = resolve; });
  const ui = mountRefunds();
  const loading = ui.select(fixturePaymentId);
  assert($('details-workspace').getAttribute('aria-busy') !== 'true', 'live status is outside busy details container');
  assert($('details-overview-result').getAttribute('aria-busy') === 'true', 'overview content marks loading');
  assert($('refund-history').getAttribute('aria-busy') === 'true', 'refund content marks loading');
  // First payment GET was deferred; subsequent bracketing GET returns immediately.
  window.fetch = async url => new Response(JSON.stringify(url.endsWith('/gateway-transactions') || url.endsWith('/refunds') ? [] : selectedPayment()));
  release(new Response(JSON.stringify(selectedPayment()))); await loading;
  assert($('details-overview-result').getAttribute('aria-busy') === 'false' && $('refund-history').getAttribute('aria-busy') === 'false', 'content busy flags clear after read-only load');
  assert(!$('refund-fields').disabled, 'fresh eligible history preserves refund controls');
  clearSession();
  assert($('details-workspace').hidden && !$('details-overview-result').textContent && !$('refund-history').textContent, 'logout clears mounted private details');
  document.querySelector('#result').textContent = `PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch (error) { document.querySelector('#result').textContent = `FAIL: ${error.message}`; }
finally { window.fetch = original; clearSession(); }
