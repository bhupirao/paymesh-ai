import { createPaymentWorkflow } from './payments.js';
import { renderPayment, renderIntent } from '../components/payment.js';
import { setText } from '../components/dom.js';
import { getSession, getVersion, subscribe } from '../auth/session.js';
export function mountPayments(details) {
  const $ = id => document.getElementById(id);
  let state, lookupPayment = null, observed = null, view = 'lookup', lookupBusy = false;
  const flow = createPaymentWorkflow(next => { const wasBusy = state?.processBusy; state = next; render(); details?.render(); if (wasBusy !== undefined && wasBusy !== next.processBusy) { if (wasBusy && details?.selected()) void details.select(details.selected()); } });
  function displayLookup() {
    const payment = lookupPayment && state.updated?.paymentId === lookupPayment.paymentId ? state.updated : lookupPayment;
    renderPayment($('payment-result'), payment);
    $('lookup-process').hidden = !flow.eligible(payment) || lookupBusy;
    $('lookup-process').disabled = Boolean(details?.financialLocked?.() ?? details?.locked());
    $('lookup-details').hidden = !payment;
    $('lookup-details').disabled = Boolean(details?.locked()) || state.processBusy || lookupBusy;
    return payment;
  }
  function render() {
    const intent = state.intent;
    $('create-fields').disabled = Boolean(intent);
    $('create-form').setAttribute('aria-busy', String(state.creation === 'pending'));
    $('creation-review').hidden = !intent;
    // Render immutable intent with safe text. No inferred merchant or financial calculations.
    renderIntent($('intent-details'), intent?.body);
    $('confirm-create').hidden = !['review', 'uncertain', 'rejected', 'pending'].includes(state.creation);
    $('confirm-create').disabled = state.creation === 'pending';
    setText($('confirm-create'), state.creation === 'pending' ? 'Creating…' : state.creation === 'review' ? 'Confirm simulated creation' : 'Retry exact intent with same key');
    setText($('creation-feedback'), state.message);
    renderPayment($('created-result'), state.created);
    $('copy-payment').hidden = !state.created;
    $('created-details').hidden = !state.created;
    $('created-details').disabled = Boolean(details?.locked()) || state.processBusy || lookupBusy;
    $('created-process').hidden = !flow.eligible(state.created) || lookupBusy;
    $('new-intent-panel').hidden = !intent;
    $('new-intent').disabled = state.creation === 'pending' || state.processBusy;
    $('uncertain-ack-label').hidden = !['uncertain', 'conflict'].includes(state.creation);
    $('process-panel').hidden = !state.processReview;
    renderPayment($('process-details'), state.processReview);
    $('confirm-process').disabled = state.processBusy; $('cancel-process').disabled = state.processBusy;
    setText($('confirm-process'), state.processBusy ? 'Processing…' : 'Confirm simulated processing');
    setText($('process-feedback'), state.processMessage);
    $('lookup-submit').disabled = state.processBusy || lookupBusy;
    $('payment-id').disabled = state.processBusy || lookupBusy;
    const locked = Boolean(details?.financialLocked?.() ?? details?.locked());
    $('review-create').disabled = locked; $('created-process').disabled = locked;
    for (const id of ['review-create','confirm-create','new-intent','created-process','confirm-process']) $(id).disabled ||= locked;
    $('create-fields').disabled ||= locked;
    $('lookup-submit').disabled ||= Boolean(details?.locked()); $('payment-id').disabled ||= Boolean(details?.locked());
    displayLookup();
  }
  function navigate(next, focus = true) {
    if (details?.locked()) return;
    if (next === 'create') details?.clear();
    view = next;
    $('lookup').hidden = next !== 'lookup'; $('create-payment').hidden = next !== 'create';
    for (const [id, selected] of [['nav-lookup', next === 'lookup'], ['nav-create', next === 'create']]) {
      $(id).className = selected ? 'nav-current' : 'nav-link';
      if (selected) $(id).setAttribute('aria-current', 'page'); else $(id).removeAttribute('aria-current');
    }
    if (focus && getSession()) $(next === 'lookup' ? 'payment-id' : 'create-title').focus();
  }
  $('nav-lookup').addEventListener('click', event => { event.preventDefault(); navigate('lookup'); });
  $('nav-create').addEventListener('click', event => { event.preventDefault(); navigate('create'); });
  const routing = () => setText($('routing-guidance'), `Expected routing: ${$('create-currency').value === 'INR' ? 'INR → MOCK_RAZORPAY' : 'USD → MOCK_STRIPE'}. Guidance only; no gateway transaction has been asserted.`);
  $('create-currency').addEventListener('change', routing);
  $('create-form').addEventListener('submit', event => {
    event.preventDefault(); if ((details?.financialLocked?.() ?? details?.locked()) || !$('create-form').reportValidity()) return;
    if (flow.review({ merchantId: $('merchant-id').value, amount: $('create-amount').value, currency: $('create-currency').value, customerId: $('customer-id').value, paymentMethod: $('payment-method').value })) $('creation-review').focus();
  });
  $('confirm-create').addEventListener('click', () => { if (!(details?.financialLocked?.() ?? details?.locked())) void flow.submit(); });
  $('new-intent').addEventListener('click', () => {
    if (!(details?.financialLocked?.() ?? details?.locked()) && flow.newIntent($('uncertain-ack').checked)) { $('create-form').reset(); $('uncertain-ack').checked = false; setText($('copy-feedback'), ''); routing(); $('merchant-id').focus(); }
  });
  $('lookup-process').addEventListener('click', () => { if (!(details?.financialLocked?.() ?? details?.locked()) && !lookupBusy && flow.reviewProcess(displayLookup())) $('process-title').focus(); });
  $('created-process').addEventListener('click', () => { if (!(details?.financialLocked?.() ?? details?.locked()) && !lookupBusy && flow.reviewProcess(state.created)) $('process-title').focus(); });
  $('confirm-process').addEventListener('click', () => { if (!(details?.financialLocked?.() ?? details?.locked())) void flow.process(); });
  $('cancel-process').addEventListener('click', () => flow.cancelProcess());
  $('copy-payment').addEventListener('click', async () => {
    const version = getVersion(), id = state.created?.paymentId;
    if (!id) return;
    try { await navigator.clipboard.writeText(id); if (version === getVersion() && state.created?.paymentId === id) setText($('copy-feedback'), 'Payment UUID copied.'); }
    catch { if (version === getVersion()) setText($('copy-feedback'), 'Copy unavailable. Select the payment UUID above and copy it manually.'); }
  });
  subscribe(() => { lookupPayment = null; observed = null; $('create-form').reset(); $('uncertain-ack').checked = false; setText($('copy-feedback'), ''); routing(); navigate('lookup', false); });
  $('lookup-details').addEventListener('click', () => { const payment = displayLookup(); if (payment && !details?.locked()) void details.select(payment.paymentId); });
  $('created-details').addEventListener('click', () => { if (state.created && !details?.locked() && !state.processBusy && !lookupBusy) { navigate('lookup'); void details.select(state.created.paymentId); document.getElementById('details-title').focus(); } });
  flow.start(); routing(); navigate(view, false);
  return {
    openLookup: () => navigate('lookup', false),
    lookupAllowed: () => !state.processBusy && !details?.locked(),
    investigationBlocked: () => Boolean(lookupBusy || state?.processBusy || state?.processReview || state?.processUncertain || (state?.intent && state.creation !== 'done')),
    mutationBusy: () => Boolean(state?.processBusy || state?.creation === 'pending' || lookupBusy),
    refreshLocks: render,
    clearOverview() { lookupPayment = null; flow.cancelProcess(); displayLookup(); },
    acceptDetails(payment) { lookupPayment = payment; flow.observeLookup(payment); },
    observeLookup(payment, busy = false) {
      lookupBusy = busy; lookupPayment = payment;
      if (payment && payment !== observed) { observed = payment; flow.observeLookup(payment); if (!details?.locked()) void details?.select(payment.paymentId); } else { displayLookup(); if (!payment && busy) details?.clear(); }
    }
  };
}
