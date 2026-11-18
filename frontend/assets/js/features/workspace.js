import { rejectPortalLogin } from '../auth/persistence.js';
import { decimal } from '../api/decimal.js';
import { request } from '../api/client.js';
import { clearSession, getSession, getVersion, isUUID, setSession, subscribe, checkExpiry, validateLogin } from '../auth/session.js';
export function rolePresentation(roles) {
  return roles.includes('ADMIN') ? { title: 'Admin workspace', scope: 'Look up known payments across merchants. Java verifies every request.' } :
    { title: 'Merchant workspace', scope: 'Look up known payments belonging to your authorized merchant memberships.' };
}
export function feedback(error, login = false) {
  if (error.status === 401) return login ? 'Unable to sign in. Check your username and password.' : 'Your session is no longer valid. Please sign in again.';
  if (error.status === 403) return 'Access denied. Your session remains active, but this operation is not permitted.';
  if (error.status === 404) return 'Payment not found or not accessible to this account.';
  if (error.status === 429) {
    const seconds = /^\d+$/.test(error.retryAfter || '') ? Number(error.retryAfter) : Math.ceil((Date.parse(error.retryAfter) - Date.now()) / 1000);
    return Number.isFinite(seconds) && seconds > 0 && seconds <= 86400 ? `Too many attempts. Wait ${seconds} seconds before trying again.` : 'Too many attempts. Please wait before trying again.';
  }
  if (error.status >= 500) return 'The service is temporarily unavailable. Please try again later.';
  if (error.status === 400) return 'Check the entered values and try again.';
  return 'Unable to complete the request. Check your connection and try again.';
}
export function validatePayment(payment, id) {
  const fields = ['paymentId', 'merchantId', 'currency', 'customerId', 'paymentMethod', 'status', 'createdAt'];
  if (!payment || fields.some(key => typeof payment[key] !== 'string') || payment.paymentId.toLowerCase() !== id.toLowerCase() ||
      !(typeof payment.amount === 'string' || Number.isFinite(payment.amount)) || !Number.isFinite(Date.parse(payment.createdAt))) throw new Error('Invalid payment response');
  decimal(String(payment.amount));
  if (!isUUID(payment.paymentId) || !['CREATED', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED'].includes(payment.status)) throw new Error('Invalid payment response');
  return payment;
}
export function createWorkspace(onChange) {
  let state = { session: getSession(), loginBusy: false, lookupBusy: false, message: '', payment: null };
  let attempt = 0, lookup = 0, loginPending = null;
  const emit = () => onChange({ ...state });
  const unsubscribe = subscribe((session, reason) => {
    attempt++; lookup++; loginPending = null;
    state = { session, loginBusy: false, lookupBusy: false, payment: null,
      message: reason === 'expired' ? 'Your session expired. Please sign in again.' : reason === 'unauthorized' ? 'Your session is no longer valid. Please sign in again.' : reason === 'logout' ? 'Signed out. Your local session has been cleared.' : '' };
    emit();
  });
  return {
    start: emit,
    dispose: unsubscribe,
    logout: () => clearSession(),
    cancelLogin() {
      if (!loginPending) return;
      attempt++; state.message = 'Previous sign-in request is still pending; its response will be ignored.'; emit();
    },
    async login(login, password, requiredRole, rememberMe) {
      if (state.loginBusy) return;
      const current = ++attempt, version = getVersion(), handle = {};
      loginPending = handle;
      state.loginBusy = true; state.message = 'Signing in securely…'; emit();
      try {
        const response = await request('/auth/login', { method: 'POST', body: { login, password, ...(rememberMe === undefined ? {} : {rememberMe:Boolean(rememberMe)}) } });
        if (current !== attempt || version !== getVersion()) { await rejectPortalLogin(); return; }
        const claims = validateLogin(response);
        if (requiredRole !== undefined && (!['MERCHANT','ADMIN'].includes(requiredRole) || !claims.roles.includes(requiredRole))) {
          await rejectPortalLogin();
          state.message = `This portal requires the ${requiredRole === 'ADMIN' ? 'ADMIN' : 'MERCHANT'} role. Use the correct portal for your account.`; return;
        }
        setSession(response, login);
      } catch (error) {
        if (current !== attempt || version !== getVersion()) return;
        state.message = error.status === undefined ? 'Invalid authentication response. Please sign in again.' : feedback(error, true);
      } finally {
        password = '';
        if (loginPending === handle) {
          loginPending = null; state.loginBusy = false;
          if (current !== attempt) state.message = 'Previous sign-in response ignored. Sign in to the selected portal.';
          emit();
        }
      }
    },
    async lookup(id) {
      checkExpiry();
      if (!getSession() || state.lookupBusy) return;
      state.payment = null;
      if (!isUUID(id)) { state.message = 'Enter a canonical payment UUID, including hyphens.'; emit(); return; }
      const current = ++lookup, version = getVersion();
      state.lookupBusy = true; state.message = 'Loading authorized payment…'; emit();
      try {
        const payment = await request(`/payments/${id}`, { exactPayment: true });
        checkExpiry();
        if (current !== lookup || version !== getVersion()) return;
        state.payment = validatePayment(payment, id); state.message = 'Payment loaded. Read-only view.';
      } catch (error) {
        if (current !== lookup || version !== getVersion()) return;
        state.message = error.status === undefined ? 'The service returned an invalid payment response.' : feedback(error);
      } finally {
        if (current === lookup) { state.lookupBusy = false; emit(); }
      }
    }
  };
}
