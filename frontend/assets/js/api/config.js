import { conversationRoute } from '../conversations/routes.js';
import { merchantRoute } from '../merchant/routes.js';
import { adminRoute } from '../admin/routes.js';
export const API = Object.freeze({ base: '/api/v1', timeoutMs: 20000, investigationTimeoutMs: 65000, chatTimeoutMs: 45000 });
export function validateRoute(method, path) {
  const id = '[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}';
  return conversationRoute(method,path) || (method==='POST'&&new RegExp(`^/payments/${id}/ai/chat$`).test(path)) || merchantRoute(method,path) || adminRoute(method,path) || (method === 'POST' && ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout', '/auth/logout-all', '/auth/password/forgot', '/auth/password/verify-otp', '/auth/password/reset', '/payments'].includes(path)) ||
    (method === 'GET' && ['/payments/health','/auth/password/capabilities'].includes(path)) ||
    new RegExp(`^/payments/${id}${method === 'GET' ? '(/(gateway-transactions|refund|refunds))?' : '/(process|refund|investigate)'}$`).test(path);
}
