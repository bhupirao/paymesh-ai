import { request } from '../api/client.js';
import { checkExpiry, getSession, getVersion, subscribe } from '../auth/session.js';
import { validatePayment } from '../features/workspace.js';
import { validateInvestigation } from './schema.js';
const READY = 'Ready for an explicit investigation. Results are historical evidence snapshots, not continuously updated payment state.';
export function investigationError(error) {
  const messages = {
    400: 'The investigation request was rejected. Refresh the authorized payment before trying again.',
    401: 'Authentication is required. Please sign in again.',
    403: 'Access denied. Java did not authorize this investigation.',
    404: 'Payment not found or not accessible to this account.',
    422: 'The available evidence is unsupported, excessive or inconsistent. No investigation result is available.',
    429: 'Request limit reached. Wait before deliberately trying again.',
    502: 'The investigation service response was unavailable or invalid. No partial result is shown.',
    503: 'Investigation is unavailable or busy. Wait before explicitly retrying.',
    504: 'The proxy timed out. The investigation may still be completing on the server. Wait before explicitly retrying.'
  };
  if (error.reason === 'invalid_json' || error.reason === 'schema') return 'The investigation response was invalid or mismatched. No partial result is shown.';
  if (error.reason === 'timeout') return 'The browser timed out. The investigation may still be completing on the server; client timeout does not stop backend work. Wait before explicitly retrying.';
  return messages[error.status] || 'Unable to complete the investigation. The request may still be completing on the server. Check the connection and retry only by deliberate action.';
}
export function createInvestigation(onChange,{blocked=()=>false}={}) {
  let context = null, fingerprint = null, sequence = 0, pending = null;
  let state = { payment: null, phase: 'ready', message: 'Select an authorized payment to investigate.', result: null, startedAt: null };
  function active() { checkExpiry(); return Boolean(getSession()); }
  function snapshot() { return { ...state, busy: Boolean(pending), available: Boolean(context?.available && !context?.blocked && !blocked() && !pending) }; }
  const emit = () => onChange(snapshot());
  const reset = () => { sequence++; pending = null; context = null; fingerprint = null; state = { payment: null, phase: 'ready', message: 'Select an authorized payment to investigate.', result: null, startedAt: null }; emit(); };
  const unsubscribe = subscribe(reset);
  return {
    start: emit, dispose: unsubscribe,
    busy: () => Boolean(pending),
    observe(details, financialBlocked = false) {
      if (!active()) { if (context || state.result) reset(); return; }
      let payment = null;
      try { if (!details.accessDenied && details.payment && details.selected === details.payment.paymentId.toLowerCase()) payment = validatePayment(details.payment, details.selected); } catch { /* No authorized valid selection. */ }
      const next = {
        selected: details.selected, payment,
        available: Boolean(payment && !details.loading && details.gatewayState !== 'loading'),
        blocked: Boolean(financialBlocked || details.intent)
      };
      // Any refresh/evidence availability change is conservative invalidation, even if later values match.
      const signature = JSON.stringify([next.selected, payment, details.history, details.gateways, Boolean(details.loading), details.gatewayState, next.blocked]);
      if (signature !== fingerprint) {
        const hadResult = Boolean(state.result);
        sequence++; fingerprint = signature; context = next;
        state = { payment, phase: 'ready', result: null, startedAt: null,
          message: pending ? 'Selection or evidence changed. The previous request may still be completing; its response will be ignored.' : hadResult ? 'Previous investigation cleared after a selection, evidence or financial-operation change. Investigate again only by explicit action.' : READY };
      } else context = next;
      if (!payment) state.message = 'Select an authorized payment to investigate.';
      else if (next.blocked && !pending) state.message = 'Resolve or cancel the current financial intent before investigating. No request was sent.';
      else if (!next.available && !pending) state.message = 'Wait for authorized payment details to finish loading before investigating.';
      emit();
    },
    async run() {
      if (!active() || !context?.available || context.blocked || blocked() || pending) return false;
      const selected = context.selected, version = getVersion(), current = sequence;
      const handle = {}; pending = handle;
      state = { ...state, phase: 'loading', message: 'Collecting authorized evidence and performing local analysis may take several seconds (often 10–45 seconds). No automatic retries.', result: null, startedAt: Date.now() }; emit();
      try {
        const { data, status } = await request(`/payments/${selected}/investigate`, { method: 'POST', withStatus: true });
        checkExpiry(); if (version !== getVersion() || current !== sequence) return false;
        let result;
        try { if (status !== 200) throw new Error(); result = validateInvestigation(data, selected); }
        catch { throw { reason: 'schema' }; }
        state.result = result;
        state.phase = result.investigation.investigationStatus === 'COMPLETED' ? 'completed' : 'inconclusive';
        state.message = state.phase === 'completed' ? 'Investigation completed. Read the returned certainty, provenance and limitations.' : 'Investigation is INCONCLUSIVE. This is an analysis result, not a network failure.';
        return true;
      } catch (error) {
        if (version !== getVersion() || current !== sequence) return false;
        state.phase = 'failed'; state.result = null; state.message = investigationError(error); return false;
      } finally {
        if (pending === handle) {
          pending = null;
          if (current !== sequence && version === getVersion()) state.message = context?.payment ? READY : 'Select an authorized payment to investigate.';
          emit();
        }
      }
    }
  };
}
