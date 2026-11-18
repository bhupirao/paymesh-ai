// Only this module retains the access token. Decoded claims are presentation hints.
let session = null;
let version = 0;
let timer;
const listeners = new Set();
export const isUUID = value => typeof value === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value);
function decode(part) {
  if (!/^[A-Za-z0-9_-]+$/.test(part)) throw new Error();
  const text = atob(part.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(part.length / 4) * 4, '='));
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(text, c => c.charCodeAt(0))));
}
export function validateLogin(response, now = Date.now()) {
  try {
    if (!response || response.tokenType !== 'Bearer' || response.expiresIn !== 900 ||
        typeof response.accessToken !== 'string' || response.accessToken.length > 16384 ||
        typeof response.expiresAt !== 'string' || !/^\d{4}-\d\d-\d\dT.*Z$/.test(response.expiresAt)) throw new Error();
    if(response.login!==undefined&&(typeof response.login!=='string'||!/^[a-z0-9][a-z0-9._@+\-]{2,254}$/.test(response.login)))throw new Error();
    const parts = response.accessToken.split('.');
    if (parts.length !== 3 || !/^[A-Za-z0-9_-]+$/.test(parts[2])) throw new Error();
    const header = decode(parts[0]), claims = decode(parts[1]);
    const expires = Date.parse(response.expiresAt);
    if (header.alg !== 'RS256' || !isUUID(claims.sub) || !Array.isArray(claims.roles) ||
        !claims.roles.length || claims.roles.some(role => !['ADMIN', 'MERCHANT'].includes(role)) ||
        !Number.isInteger(claims.exp) || !Number.isInteger(claims.iat) ||
        claims.exp - claims.iat !== 900 || expires !== claims.exp * 1000 ||
        expires <= now || expires > now + 901000) throw new Error();
    if (claims.account_status !== undefined && !['ACTIVE','PENDING_APPROVAL','REJECTED','SUSPENDED'].includes(claims.account_status)) throw new Error();
    if (claims.account_status !== undefined && claims.account_status !== 'ACTIVE' && (claims.roles.length !== 1 || claims.roles[0] !== 'MERCHANT')) throw new Error();
    if (claims.sid !== undefined && claims.sid !== null && !isUUID(claims.sid)) throw new Error();
    return { displayLogin:response.login??null,sessionId: claims.sid || null, accountStatus: claims.account_status || 'ACTIVE', expires, subject: claims.sub, roles: [...new Set(claims.roles)] };
  } catch { throw new Error('Invalid authentication response. Please sign in again.'); }
}
function notify(reason) { for (const listener of listeners) listener(getSession(), reason); }
export function setSession(response, identity = '') {
  const details = validateLogin(response);
  clearTimeout(timer);
  session = { ...details, token: response.accessToken, identity:details.displayLogin??identity };
  version++;
  timer = setTimeout(checkExpiry, Math.max(0, details.expires - Date.now()));
  notify('login');
}
// Rotating the same authenticated session must not clear uncertain financial intents.
export function renewSession(response) {
  const details=validateLogin(response);
  if(!session || !details.sessionId || details.sessionId!==session.sessionId || details.subject!==session.subject || details.accountStatus!==session.accountStatus || details.roles.join(',')!==session.roles.join(','))throw new Error('Session changed');
  session={...session,...details,identity:details.displayLogin??session.identity,token:response.accessToken};clearTimeout(timer);timer=setTimeout(checkExpiry,Math.max(0,details.expires-Date.now()));
}
export function clearSession(reason = 'logout') {
  clearTimeout(timer); session = null; version++; notify(reason);
}
export function checkExpiry() {
  if (session && session.expires <= Date.now()) clearSession('expired');
  else if (session) { clearTimeout(timer); timer = setTimeout(checkExpiry, session.expires - Date.now()); }
}
export function getSession() {
  return session ? { sessionId: session.sessionId, accountStatus: session.accountStatus, expires: session.expires, subject: session.subject, roles: [...session.roles], identity: session.identity } : null;
}
export function getVersion() { return version; }
export function getToken() { checkExpiry(); return session?.token ?? null; }
export function subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }
export function installLifecycle(target = window, doc = document) {
  target.addEventListener('focus', checkExpiry);
  doc.addEventListener('visibilitychange', checkExpiry);
  target.addEventListener('pageshow', checkExpiry);
  return () => { target.removeEventListener('focus', checkExpiry); doc.removeEventListener('visibilitychange', checkExpiry); target.removeEventListener('pageshow', checkExpiry); };
}
