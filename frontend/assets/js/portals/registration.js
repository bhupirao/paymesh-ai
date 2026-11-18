import { request } from '../api/client.js';
import { getVersion } from '../auth/session.js';
import { validateSignup } from './signup.js';
export const REGISTRATION_SUCCESS = 'Your account has been created successfully. You can now sign in using your email and password.';
export function createRegistration(render) {
  let busy = false, sequence = 0;
  function reset() { sequence++; render({ busy, message: '', success: false }); }
  return { reset, async submit(input) {
    if (busy) return;
    const errors = validateSignup(input);
    if (Object.keys(errors).length) { render({ busy: false, errors, message: 'Check the highlighted fields.' }); return; }
    const operation = ++sequence, version = getVersion(); busy = true;
    render({ busy: true, message: 'Creating your merchant account…', success: false });
    try {
      const body = { ...input, email: input.email.trim().toLowerCase() };
      const { data, status } = await request('/auth/register', { method: 'POST', body, withStatus: true });
      if (operation !== sequence || version !== getVersion()) return;
      if (status !== 201 || data?.accountStatus !== 'PENDING_APPROVAL' || data.message !== REGISTRATION_SUCCESS) throw new Error('invalid');
      render({ busy: true, message: REGISTRATION_SUCCESS, success: true });
    } catch (error) {
      if (operation !== sequence || version !== getVersion()) return;
      const messages = { 400: 'Check the form and password requirements.', 409: 'Registration could not be completed. Try signing in or use different details.', 429: 'Too many attempts. Wait before trying again.', 413: 'Registration request is too large.', 503: 'Registration is temporarily unavailable.' };
      render({ busy: true, success: false, message: messages[error.status] || 'Registration could not be confirmed. Try signing in before submitting again. No automatic retry was made.' });
    } finally {
      input.password = input.confirmPassword = ''; busy = false;
      render({ busy: false });
    }
  } };
}
