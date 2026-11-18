import { conversationRoute } from '../conversations/routes.js';
import { authLock, discardStaleLogin } from '../auth/persistence.js';
import { parsePaymentJSON, serializeCreation, serializeRefund, serializeLink } from './decimal.js';
import { API, validateRoute } from './config.js';
import { getToken, getSession, clearSession, getVersion } from '../auth/session.js';
export class ApiError extends Error {
  constructor(message, status = 0, fieldErrors = {}, retryAfter = null, reason = 'http', code = null) {
    super(message); this.status = status; this.fieldErrors = fieldErrors; this.retryAfter = retryAfter; this.reason = reason; this.code = code;
  }
}
const pending = new Set();
async function perform(path, { method = 'GET', body, idempotencyKey, exactPayment = false, withStatus = false, signal: externalSignal } = {}) {
  if (!['GET', 'POST'].includes(method) || !validateRoute(method, path)) throw new ApiError('Unsupported API route');
  const token = getToken();
  if (getSession() && getSession().accountStatus !== 'ACTIVE' && path.startsWith('/payments') && path !== '/payments/health') throw new ApiError('Account awaiting approval', 403);
  if(path.startsWith('/admin/') && (!getSession()?.roles.includes('ADMIN') || getSession()?.accountStatus!=='ACTIVE'))throw new ApiError('Admin authorization required',403);
  if(path.startsWith('/merchant/') && (!getSession()?.roles.includes('MERCHANT') || getSession()?.accountStatus!=='ACTIVE'))throw new ApiError('Active Merchant authorization required',403);
  const version = getVersion();
  const key = `${version} ${method} ${path}`;
  if (pending.has(key)) throw new ApiError('Request already in progress');
  pending.add(key);
  const controller = new AbortController();
  const saved=conversationRoute(method,path);
  const chat = (saved&&method==='POST'&&path.endsWith('/messages'))||['/merchant/ai/chat','/admin/ai/chat'].includes(path)||/^\/payments\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/ai\/chat$/i.test(path);
  const abort = () => controller.abort();
  externalSignal?.addEventListener('abort',abort,{once:true});
  if(externalSignal?.aborted)controller.abort();
  const timer = setTimeout(abort, chat ? API.chatTimeoutMs : path.endsWith('/investigate') ? API.investigationTimeoutMs : API.timeoutMs);
  try {
    const headers = { Accept: 'application/json' };
    if(path.startsWith('/auth/'))headers['X-PayMesh-CSRF']='1';
    if (token && !path.startsWith('/auth/')) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
    if(saved&&body!==undefined&&new TextEncoder().encode(JSON.stringify(body)).length>8192)throw new ApiError('Conversation request exceeds UTF-8 limit',413);
    if(chat&&new TextEncoder().encode(JSON.stringify(body)).length>32768)throw new ApiError('Chat request exceeds UTF-8 limit',413);
    const response = await fetch(API.base + path, { method, headers,
      body: body === undefined ? undefined : (exactPayment && path==='/merchant/payment-links' && method==='POST' ? serializeLink(body) : exactPayment && path === '/payments' && method === 'POST' ? serializeCreation(body) : exactPayment && method === 'POST' && /^\/payments\/[0-9a-f-]+\/refund$/i.test(path) ? serializeRefund(body) : JSON.stringify(body)), signal: controller.signal,
      credentials: ['/auth/login','/auth/refresh','/auth/logout','/auth/logout-all'].includes(path) ? 'same-origin' : 'omit', cache: 'no-store', redirect: 'error' });
    if (version !== getVersion()) { if(path==='/auth/login')await discardStaleLogin(); throw new ApiError('Session changed; response ignored'); }
    if (response.status === 401 && token === getToken() && !['/auth/login', '/auth/register'].includes(path)) clearSession('unauthorized');
    let data;
    try { data = exactPayment ? parsePaymentJSON(await response.text()) : await response.json(); } catch { throw new ApiError('Invalid service response', response.status, {}, null, 'invalid_json'); }
    if (response.status !== 401 && version !== getVersion()) throw new ApiError('Session changed; response ignored');
    if (!response.ok) {
      const code=(chat||saved)&&['CONVERSATION_UNAVAILABLE','CONVERSATION_CONFLICT','CONVERSATION_GONE','CONVERSATION_LIMIT','REQUEST_RETRY_LIMIT','REQUEST_FAILED','AI_UNAVAILABLE','AI_CAPACITY','EVIDENCE_UNAVAILABLE','INVALID_AI_RESPONSE','AI_TIMEOUT','UNSUPPORTED_EVIDENCE','EVIDENCE_TOO_LARGE','SENSITIVE_TEXT','INVALID_INPUT','ACCESS_DENIED','CONTEXT_UNAVAILABLE','AUTHENTICATION_REQUIRED'].includes(data?.code)?data.code:null;
      throw new ApiError('Request failed', response.status, data?.fieldErrors || {}, response.headers.get('Retry-After'),'http',code);
    }
    return withStatus ? { data, status: response.status } : data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if(chat)throw new ApiError(externalSignal?.aborted?'Chat request cancelled locally':error.name==='AbortError'?'Chat request timed out; server analysis may still finish':'AI chat connection unavailable',0,{},null,externalSignal?.aborted?'cancelled':error.name==='AbortError'?'timeout':'network');
    throw new ApiError(error.name === 'AbortError' ? 'Request timed out. Verify payment state before retrying.' : 'Unable to reach payment service', 0, {}, null, error.name === 'AbortError' ? 'timeout' : 'network');
  } finally { clearTimeout(timer); externalSignal?.removeEventListener('abort',abort); pending.delete(key); }
}

export function request(path,options={}) {return ['/auth/login','/auth/refresh','/auth/logout','/auth/logout-all'].includes(path)?authLock(()=>perform(path,options)):perform(path,options);}
