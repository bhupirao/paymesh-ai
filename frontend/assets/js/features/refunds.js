import { request } from '../api/client.js';
import { decimal, refundDecimal, minorUnits, formatMinor, serializeRefund } from '../api/decimal.js';
import { isUUID, checkExpiry, getSession, getVersion, subscribe } from '../auth/session.js';
import { validatePayment } from './workspace.js';
const same = (a, b) => typeof a === 'string' && typeof b === 'string' && a.toLowerCase() === b.toLowerCase();
const instant = value => typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0,19) === value.slice(0,19);
const requireValid = condition => { if (!condition) throw new Error('Invalid or inconsistent history'); };
export function validateGatewayHistory(rows, paymentId) {
  requireValid(Array.isArray(rows));
  const seen = new Set();
  return Object.freeze(rows.map(row => {
    requireValid(row && isUUID(row.id) && same(row.paymentId, paymentId) && !seen.has(row.id.toLowerCase()) &&
      typeof row.gatewayName === 'string' && row.gatewayName.trim() && ['INITIATED','SUCCESS','FAILED','TIMEOUT','UNKNOWN'].includes(row.status) &&
      (row.gatewayTransactionId === null || isUUID(row.gatewayTransactionId)) &&
      (row.errorCode === null || typeof row.errorCode === 'string') && (row.errorMessage === null || typeof row.errorMessage === 'string') &&
      instant(row.createdAt) && instant(row.updatedAt) && Date.parse(row.updatedAt) >= Date.parse(row.createdAt));
    seen.add(row.id.toLowerCase()); return Object.freeze({ ...row });
  }));
}
export function validateRefund(row, paymentId) {
  requireValid(row && isUUID(row.refundId) && isUUID(row.paymentId) && same(row.paymentId, paymentId) && row.status === 'SUCCESS' && instant(row.createdAt));
  refundDecimal(row.amount); // Require preserved decimal string, never a rounded Number.
  return Object.freeze({ ...row, amount: refundDecimal(row.amount) });
}
export function refundSummary(payment, rows) {
  validatePayment(payment, payment.paymentId);
  requireValid(typeof payment.amount === 'string' && Array.isArray(rows));
  const original = minorUnits(payment.amount), seen = new Set();
  let successful = 0n;
  const records = rows.map(row => {
    const validated = validateRefund(row, payment.paymentId);
    requireValid(!seen.has(row.refundId.toLowerCase()) && Date.parse(row.createdAt) >= Date.parse(payment.createdAt));
    seen.add(row.refundId.toLowerCase()); successful += minorUnits(validated.amount, true); return validated;
  });
  requireValid(successful <= original);
  const remaining = original - successful;
  if (payment.status === 'REFUNDED') requireValid(remaining === 0n);
  else if (payment.status === 'SUCCESS') requireValid(remaining > 0n);
  else requireValid(successful === 0n);
  return Object.freeze({ original: formatMinor(original), successful: formatMinor(successful), remaining: formatMinor(remaining),
    eligible: payment.status === 'SUCCESS' && remaining > 0n, records: Object.freeze(records) });
}
export function refundFeedback(error, mutation = false) {
  const fixed = { 400: 'Request rejected. Check the refund values.', 401: 'Session expired. Please sign in again.',
    403: 'Access denied. Java did not authorize this operation.', 404: 'Payment not found or not accessible.',
    409: 'Refund conflict. Refresh authorized details and investigate before starting another intent.', 413: 'Request exceeds the size limit.',
    415: 'Unsupported request format.', 422: 'The service cannot accept this request or evidence.', 429: 'Too many requests. Wait before trying again.' };
  return fixed[error.status] || (mutation ? 'Refund outcome uncertain. Keep this intent and retry only the exact request with the same key. Do not create another refund.' : 'Details unavailable or inconsistent. Refresh authorized state; new refunds are blocked.');
}
export function createRefundWorkspace(onChange, { onPayment = () => {}, otherBusy = () => false, mutationBlocked = otherBusy, now = () => Date.now() } = {}) {
  const fresh = () => ({ selected: null, payment: null, gateways: null, gatewayState: 'idle', gatewayMessage: '',
    history: null, summary: null, loadedAt: 0, loading: false, message: '', intent: null, phase: 'idle', accessDenied:false, authorizationRead:0, confirmed: null, confirmedStatus: null });
  let state = fresh(), selection = 0, refreshSequence = 0, gatewaySequence = 0, busy = false;
  const knownRefunds = new Map();
  let knownPayment = null,authorizationRead=0;
  const emit = () => onChange({ ...state });
  const active = () => { checkExpiry(); return Boolean(getSession()); };
  const locked = () => Boolean(state.intent && !['done'].includes(state.phase));
  const eligible = () => active() && !mutationBlocked() && !state.loading && !state.intent && state.summary?.eligible && now() - state.loadedAt < 30000;
  const current = (version, selected, seq) => { checkExpiry(); return getVersion() === version && selected === selection && seq === refreshSequence; };
  const unsubscribe = subscribe(() => { selection++; refreshSequence++; gatewaySequence++; busy = false; knownRefunds.clear(); knownPayment = null; state = fresh(); emit(); });
  async function refresh() {
    if (!active() || !state.selected || state.loading || busy || otherBusy()) return false;
    const id = state.selected, version = getVersion(), selected = selection, seq = ++refreshSequence;
    const previous = [...knownRefunds.values()], expected = state.confirmed;
    state.loading = true; state.summary = null; state.history = null; state.loadedAt = 0;
    state.message = expected ? 'Refund record confirmed. Refreshing persisted payment and complete history…' : 'Loading authorized payment and complete refund history…'; emit();
    try {
      const first = validatePayment(await request(`/payments/${id}`, { exactPayment: true }), id);
      if (!current(version, selected, seq)) return false;
      // Authorized overview is independent of refund-history eligibility; totals stay blocked.
      state.payment = Object.freeze({ ...first }); state.accessDenied=false;state.authorizationRead=++authorizationRead;emit();
      const rows = await request(`/payments/${id}/refunds`, { exactPayment: true });
      if (!current(version, selected, seq)) return false;
      const payment = validatePayment(await request(`/payments/${id}`, { exactPayment: true }), id);
      if (!current(version, selected, seq)) return false;
      requireValid(['paymentId','merchantId','currency','customerId','paymentMethod','status','createdAt','amount'].every(key => first[key] === payment[key]));
      if (knownPayment) requireValid(['paymentId','merchantId','currency','customerId','paymentMethod','createdAt','amount'].every(key => knownPayment[key] === payment[key]));
      const summary = refundSummary(payment, rows);
      if (previous) requireValid(previous.every(old => summary.records.some(row => row.refundId === old.refundId && row.amount === old.amount && row.status === old.status && row.createdAt === old.createdAt)));
      if (expected) requireValid(summary.records.some(row => row.refundId === expected.refundId && row.amount === expected.amount && row.status === expected.status && row.createdAt === expected.createdAt));
      for (const row of summary.records) knownRefunds.set(row.refundId, row);
      state.payment = Object.freeze({ ...payment }); knownPayment = state.payment; state.history = summary.records; state.summary = summary; state.loadedAt = now();
      state.message = expected ? 'Confirmed refund record and authoritative payment/history refreshed. Bank refund arrival is unverified.' : 'Authorized details refreshed. Totals use the complete successful refund history.';
      onPayment(state.payment);
      return true;
    } catch (error) {
      if (current(version, selected, seq)) {if([401,403,404].includes(error.status))state.accessDenied=true;state.message = state.confirmed ? 'Refund record is confirmed, but payment totals/status are stale or unavailable. New refunds are blocked until refresh succeeds.' : refundFeedback(error);}
      return false;
    } finally { if (current(version, selected, seq)) { state.loading = false; emit(); } }
  }
  async function loadGateways() {
    if (!active() || !state.selected || state.gatewayState === 'loading') return false;
    const id = state.selected, selected = selection, version = getVersion(), seq = ++gatewaySequence;
    state.gateways = null; state.gatewayState = 'loading'; state.gatewayMessage = 'Loading actual gateway transactions…'; emit();
    try {
      const rows = validateGatewayHistory(await request(`/payments/${id}/gateway-transactions`), id);
      checkExpiry(); if (version !== getVersion() || selected !== selection || seq !== gatewaySequence) return false;
      state.gateways = rows; state.gatewayState = 'ready'; state.gatewayMessage = rows.length ? 'Actual persisted gateway records.' : 'No gateway transactions recorded for this payment.'; return true;
    } catch (error) {
      if (version === getVersion() && selected === selection && seq === gatewaySequence) { if([401,403,404].includes(error.status))state.accessDenied=true;state.gatewayState = 'error'; state.gatewayMessage = refundFeedback(error); }
      return false;
    } finally { if (version === getVersion() && selected === selection && seq === gatewaySequence) emit(); }
  }
  return {
    start: emit, dispose: unsubscribe, locked, eligible, refresh, loadGateways,
    selected: () => state.selected,
    clear() {
      if (locked() || busy) return false;
      selection++; refreshSequence++; gatewaySequence++; knownRefunds.clear(); knownPayment = null; state = fresh(); emit(); return true;
    },
    async select(id) {
      if (!active() || locked() || busy || otherBusy() || !isUUID(id)) return false;
      if (state.selected === id.toLowerCase()) { const results = await Promise.allSettled([refresh(), loadGateways()]); return results.every(result => result.status === 'fulfilled' && result.value); }
      selection++; refreshSequence++; gatewaySequence++; knownRefunds.clear(); knownPayment = null; state = { ...fresh(), selected: id.toLowerCase() }; emit();
      const results = await Promise.allSettled([refresh(), loadGateways()]);
      return results.every(result => result.status === 'fulfilled' && result.value);
    },
    async review(amount) {
      if (!eligible()) { state.message = 'Fresh valid payment and complete refund history are required before a new refund.'; emit(); return false; }
      let normalized;
      try { normalized = refundDecimal(amount); requireValid(minorUnits(normalized, true) <= minorUnits(state.summary.remaining, true)); }
      catch { state.message = 'Enter a positive refund amount with at most 17 integer and 2 decimal digits, no greater than the remaining balance.'; emit(); return false; }
      // Re-read before freezing the review, instead of trusting an old displayed balance.
      const selected = selection, version = getVersion();
      if (!await refresh() || selection !== selected || version !== getVersion() || !eligible()) return false;
      if (minorUnits(normalized, true) > minorUnits(state.summary.remaining, true)) { state.message = 'Remaining amount changed. Review the current totals.'; emit(); return false; }
      const body = Object.freeze({ amount: normalized });
      state.intent = Object.freeze({ paymentId: state.selected, body, bytes: serializeRefund(body), key: crypto.randomUUID(),
        merchantId: state.payment.merchantId, currency: state.payment.currency, successful: state.summary.successful,
        remainingAfter: formatMinor(minorUnits(state.summary.remaining, true) - minorUnits(normalized, true)), reviewedAt: now() });
      state.confirmed = null; state.confirmedStatus = null; state.phase = 'review'; state.message = 'Review the simulated refund before explicit confirmation.'; emit(); return true;
    },
    cancelReview() {
      if (state.phase !== 'review' || busy) return false;
      state.intent = null; state.phase = 'idle'; emit(); return true;
    },
    async submit() {
      if (!active() || mutationBlocked() || busy || state.loading || !state.intent || !['review','uncertain'].includes(state.phase)) return false;
      const intent = state.intent, selected = selection, version = getVersion();
      if (state.phase === 'review' && (now() - intent.reviewedAt >= 30000 || !state.summary?.eligible || state.summary.successful !== intent.successful || now() - state.loadedAt >= 30000)) { state.message = 'Review expired. Cancel this review and refresh before reviewing again.'; emit(); return false; }
      busy = true; state.phase = 'pending'; state.summary = null; state.loadedAt = 0; state.message = 'Submitting the exact confirmed simulated refund…'; emit();
      try {
        const { data, status } = await request(`/payments/${intent.paymentId}/refund`, { method: 'POST', body: intent.body, exactPayment: true, withStatus: true, idempotencyKey: intent.key });
        checkExpiry(); if (version !== getVersion() || selected !== selection) return false;
        requireValid([200,201].includes(status));
        const record = validateRefund(data, intent.paymentId); requireValid(record.amount === intent.body.amount);
        state.confirmed = record; state.confirmedStatus = status; state.phase = 'done'; state.intent = null;
        state.message = `Refund record confirmed (${status}). Refreshing authoritative state; bank arrival is unverified.`;
      } catch (error) {
        if (version !== getVersion() || selected !== selection) return false;
        state.phase = [400,403,404,409,413,415,422,429].includes(error.status) ? 'rejected' : 'uncertain';
        state.message = refundFeedback(error, true);
      } finally { if (version === getVersion() && selected === selection) { busy = false; emit(); } }
      if (version === getVersion() && selected === selection && state.phase === 'done') await refresh();
      return state.phase === 'done';
    },
    async releaseRejected() {
      if (state.phase !== 'rejected' || busy || !active()) return false;
      if (!await refresh()) return false;
      state.intent = null; state.phase = 'idle'; state.message = 'Rejected intent cleared after fresh authorized history. Review any new refund separately.'; emit(); return true;
    }
  };
}
