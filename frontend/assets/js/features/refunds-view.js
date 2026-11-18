import { createRefundWorkspace } from './refunds.js';
import { renderPayment } from '../components/payment.js';
import { renderHistory, renderPairs } from '../components/history.js';
import { setText } from '../components/dom.js';
import { subscribe } from '../auth/session.js';
export function mountRefunds({ onLock = () => {}, onPayment = () => {}, onSelection = () => {}, onState = () => {}, readBusy = () => false, otherBusy = () => false } = {}) {
  const $ = id => document.getElementById(id);
  let state, selected = null, timer;
  const model = createRefundWorkspace(next => { state = next; render(); }, { onPayment, otherBusy, mutationBlocked: () => otherBusy() || readBusy() });
  function render() {
    clearTimeout(timer);
    $('details-workspace').hidden = !state.selected;
    const selectionChanged = selected !== state.selected;
    if (selectionChanged) { $('refund-form').reset(); selected = state.selected; }
    setText($('details-id'), state.selected);
    renderPayment($('details-overview-result'), state.payment);
    setText($('details-feedback'), state.message);
    setText($('gateway-feedback'), state.gatewayMessage);
    renderHistory($('gateway-history'), state.gateways, 'gateway');
    renderHistory($('refund-history'), state.history, 'refund');
    // Keep live status messages outside busy regions so loading can be announced.
    for (const id of ['details-overview-result','refund-history','refund-summary']) $(id).setAttribute('aria-busy', String(state.loading));
    $('gateway-history').setAttribute('aria-busy', String(state.gatewayState === 'loading'));
    $('refresh-details').disabled = state.loading || state.phase === 'pending' || otherBusy();
    $('refresh-gateways').disabled = state.gatewayState === 'loading';
    const summary = state.summary, eligible = Boolean(model.eligible());
    $('refund-fields').disabled = !eligible;
    renderPairs($('refund-summary'), summary ? [['Original amount', `${summary.original} ${state.payment.currency}`], ['Total successful refunds', `${summary.successful} ${state.payment.currency}`], ['Remaining refundable amount', `${summary.remaining} ${state.payment.currency}`]] : [['Refund totals', 'Unavailable. Do not assume zero refunds.']]);
    setText($('refund-availability'), eligible ? 'Fresh authorized snapshot. Java remains authoritative for eligibility.' : 'New refunds blocked: refresh valid history, resolve the current intent, or check payment eligibility. Snapshots expire after 30 seconds.');
    $('refund-review').hidden = !state.intent;
    renderPairs($('refund-review-details'), state.intent ? [['Payment UUID', state.intent.paymentId], ['Merchant ID', state.intent.merchantId], ['Refund amount', state.intent.body.amount], ['Currency', state.intent.currency], ['Current successful refunds at review', state.intent.successful], ['Expected remaining after this refund (estimate)', state.intent.remainingAfter]] : []);
    $('confirm-refund').hidden = !['review','pending','uncertain'].includes(state.phase);
    $('confirm-refund').disabled = state.phase === 'pending' || state.loading || otherBusy() || readBusy();
    setText($('confirm-refund'), state.phase === 'uncertain' ? 'Retry exact refund with same key' : state.phase === 'pending' ? 'Refund request pending…' : 'Confirm simulated refund');
    $('cancel-refund-review').hidden = state.phase !== 'review';
    $('release-rejected-refund').hidden = state.phase !== 'rejected';
    $('release-rejected-refund').disabled = state.loading;
    $('confirmed-refund').hidden = !state.confirmed;
    setText($('confirmed-refund-title'), state.confirmed ? `Confirmed refund record · HTTP ${state.confirmedStatus}${state.confirmedStatus === 200 ? ' (idempotent replay)' : ' (new record)'}` : 'Confirmed refund record');
    renderHistory($('confirmed-refund-record'), state.confirmed ? [state.confirmed] : null, 'refund');
    if (summary && state.loadedAt + 30000 > Date.now()) timer = setTimeout(render, state.loadedAt + 30000 - Date.now() + 1);
    if (selectionChanged) onSelection(selected);
    onState(state);
    onLock();
  }
  $('refresh-details').addEventListener('click', () => { void model.refresh(); });
  $('refresh-gateways').addEventListener('click', () => { void model.loadGateways(); });
  $('use-remaining').addEventListener('click', () => { if (model.eligible()) $('refund-amount').value = state.summary.remaining; });
  $('refund-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!$('refund-form').reportValidity()) return;
    if (await model.review($('refund-amount').value)) $('refund-review').focus();
  });
  $('confirm-refund').addEventListener('click', () => { void model.submit(); });
  $('cancel-refund-review').addEventListener('click', () => { if (model.cancelReview()) $('refund-amount').focus(); });
  $('release-rejected-refund').addEventListener('click', () => { void model.releaseRejected(); });
  subscribe(() => { $('refund-form').reset(); });
  window.addEventListener('focus', render);
  document.addEventListener('visibilitychange', render);
  model.start();
  return { select: model.select, clear: model.clear, locked: model.locked, financialLocked: () => model.locked() || readBusy(), selected: model.selected, render };
}
