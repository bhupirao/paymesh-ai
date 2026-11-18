import { request } from '../api/client.js';
import { decimal, serializeCreation } from '../api/decimal.js';
import { checkExpiry, getSession, getVersion, subscribe, isUUID } from '../auth/session.js';
import { validatePayment } from './workspace.js';
export function validateIntent(input) {
  const body = {};
  for (const field of ['merchantId', 'customerId', 'paymentMethod']) {
    if (typeof input[field] !== 'string' || !input[field].trim()) throw new Error('Merchant ID, customer ID and payment method are required.');
    body[field] = input[field].trim();
  }
  if (!['INR', 'USD'].includes(input.currency)) throw new Error('Choose INR or USD.');
  body.currency = input.currency; body.amount = decimal(input.amount);
  if (new TextEncoder().encode(serializeCreation(body)).length > 16384) throw new Error('Request exceeds the local 16 KiB limit. Shorten the text fields.');
  return Object.freeze(body);
}
export const canProcess = payment => Boolean(payment && isUUID(payment.paymentId) && payment.status === 'CREATED');
export function mutationFeedback(error, processing = false) {
  if (error.status === 400) return 'Request rejected. Check the reviewed values; no automatic retry was made.';
  if (error.status === 401) return 'Session expired. Sign in again and check payment state.';
  if (error.status === 403) return 'Access denied. Java did not authorize this operation.';
  if (error.status === 404) return 'Merchant or payment not found or not accessible.';
  if (error.status === 409) return processing ? 'Processing conflict. Look up the current payment state before considering another action.' : 'Idempotency conflict. Do not change this request or assume creation succeeded. Investigate before starting another intent.';
  if (error.status === 413) return 'Request exceeds the size limit. No automatic retry was made.';
  return processing ? 'Outcome uncertain. A network or service error does not mean payment failure. Look up the current payment state before considering another action.' : 'Creation outcome uncertain. Retain this intent and deliberately retry the exact request with the same key. Do not start a duplicate payment.';
}
export function createPaymentWorkflow(onChange) {
  const fresh = () => ({ intent: null, creation: 'draft', created: null, message: '', processReview: null, processBusy: false, processMessage: '', processUncertain: false, updated: null });
  let state = fresh(), sequence = 0;
  const blocked = new Set();
  const emit = () => onChange({ ...state });
  const active = () => { checkExpiry(); return Boolean(getSession()); };
  const unsubscribe = subscribe(() => { sequence++; blocked.clear(); state = fresh(); emit(); });
  return {
    start: emit, dispose: unsubscribe,
    review(input) {
      if (!active() || state.intent) return false;
      try {
        const body = validateIntent(input);
        // Generated once per reviewed intent, retained unchanged through confirmation/retry.
        const key = crypto.randomUUID();
        state.intent = Object.freeze({ body, key }); state.creation = 'review'; state.message = 'Review the exact values before confirming this simulated payment.';
        emit(); return true;
      } catch (error) { state.message = error.message; emit(); return false; }
    },
    newIntent(acknowledgeUncertain = false) {
      if (!active() || state.creation === 'pending' || state.processBusy) return false;
      if (['uncertain', 'conflict'].includes(state.creation) && !acknowledgeUncertain) { state.message = 'An unresolved intent exists. Starting again may create a duplicate payment. Acknowledge this risk explicitly first.'; emit(); return false; }
      sequence++; state.intent = null; state.creation = 'draft'; state.created = null; state.message = ''; state.processReview = null; emit(); return true;
    },
    async submit() {
      if (!active() || !state.intent || !['review', 'uncertain', 'rejected'].includes(state.creation)) return;
      const current = sequence, version = getVersion(), intent = state.intent;
      state.creation = 'pending'; state.message = 'Submitting the confirmed payment…'; emit();
      try {
        const { data, status } = await request('/payments', { method: 'POST', body: intent.body, idempotencyKey: intent.key, exactPayment: true, withStatus: true });
        checkExpiry(); if (current !== sequence || version !== getVersion()) return;
        if (![200, 201].includes(status)) throw new Error();
        validatePayment(data, data.paymentId);
        for (const field of ['merchantId', 'currency', 'customerId', 'paymentMethod']) if (data[field] !== intent.body[field]) throw new Error();
        if (decimal(data.amount) !== intent.body.amount || (status === 201 && data.status !== 'CREATED')) throw new Error();
        state.created = data; state.creation = 'done';
        state.message = status === 201 ? 'Payment created (201). It has not been automatically processed.' : 'Exact intent replay recovered (200). The returned status is the current backend state.';
      } catch (error) {
        if (current !== sequence || version !== getVersion()) return;
        state.creation = error.status === 409 ? 'conflict' : [400, 403, 404, 413].includes(error.status) ? 'rejected' : 'uncertain';
        state.message = mutationFeedback(error);
      }
      if (current === sequence && version === getVersion()) emit();
    },
    observeLookup(payment) {
      if (!active() || state.processBusy) return;
      blocked.delete(payment.paymentId); state.processUncertain = false; state.updated = payment; state.processReview = null;
      if (state.created?.paymentId === payment.paymentId) state.created = payment;
      state.processMessage = ''; emit();
    },
    eligible(payment) { return canProcess(payment) && !blocked.has(payment.paymentId) && !state.processBusy; },
    reviewProcess(payment) {
      if (!active() || !canProcess(payment) || blocked.has(payment.paymentId) || state.processBusy) return false;
      state.processReview = Object.freeze({ ...payment }); state.processMessage = 'Confirm the payment UUID, merchant, amount and currency before processing.'; emit(); return true;
    },
    cancelProcess() { if (!state.processBusy) { state.processReview = null; state.processMessage = ''; emit(); } },
    async process() {
      if (!active() || !state.processReview || state.processBusy) return;
      const payment = state.processReview, current = sequence, version = getVersion();
      if (!canProcess(payment) || blocked.has(payment.paymentId)) return;
      blocked.add(payment.paymentId); state.processUncertain = false; state.processBusy = true; state.processMessage = 'Processing simulated payment…'; emit();
      try {
        const data = await request(`/payments/${payment.paymentId}/process`, { method: 'POST', exactPayment: true });
        checkExpiry(); if (current !== sequence || version !== getVersion()) return;
        validatePayment(data, payment.paymentId);
        if (['merchantId', 'currency', 'customerId', 'paymentMethod'].some(field => payment[field] !== data[field]) || decimal(String(payment.amount)) !== decimal(data.amount) || data.status === 'CREATED') throw new Error();
        state.updated = data;
        if (state.created?.paymentId === data.paymentId) state.created = data;
        state.processMessage = data.status === 'PROCESSING' ? 'Payment remains PROCESSING. Outcome is unresolved. Look up its state later; do not process it again.' : `Backend payment status: ${data.status}. Simulated outcome only; bank debit and settlement are unverified.`;
      } catch (error) {
        if (current !== sequence || version !== getVersion()) return;
        state.processUncertain = true; state.processMessage = mutationFeedback(error, true);
      }
      if (current === sequence && version === getVersion()) { state.processBusy = false; state.processReview = null; emit(); }
    }
  };
}
