import { MERCHANT_PAGES } from '../merchant/routes.js';
import { ADMIN_PAGES } from '../admin/routes.js';
import { checkExpiry, getSession, subscribe } from '../auth/session.js';
export const ROUTES = Object.freeze({
  ...Object.fromEntries(Object.keys(MERCHANT_PAGES).map(path=>[path,{page:'dashboard',role:'MERCHANT',merchantView:path}])),
  ...Object.fromEntries(Object.keys(ADMIN_PAGES).map(path=>[path,{page:'dashboard',role:'ADMIN',adminView:path}])),
  '/': { page: 'landing' },
  '/merchant/forgot-password': { page: 'forgot', role: 'MERCHANT' },
  '/admin/forgot-password': { page: 'forgot', role: 'ADMIN' },
  '/merchant/signup': { page: 'signup' },
  '/merchant/login': { page: 'login', role: 'MERCHANT' },
  '/merchant/dashboard': { page: 'dashboard', role: 'MERCHANT',merchantView:'/merchant/dashboard' },
  '/admin/login': { page: 'login', role: 'ADMIN' },
  '/admin/dashboard': { page: 'dashboard', role: 'ADMIN', adminView:'/admin/dashboard' }
});
export const rolePath = role => role === 'ADMIN' ? '/admin' : '/merchant';
export function resolveRoute(path, session) {
  if (path === '/index.html') path = '/';
  const route = Object.hasOwn(ROUTES, path) ? ROUTES[path] : null;
  if (!route) return { path, page: 'not-found' };
  const allowed = Boolean(session?.roles.includes(route.role));
  if (route.page === 'dashboard' && !allowed) return { path: `${rolePath(route.role)}/login`, page: 'login', role: route.role, denied: Boolean(session) };
  if (route.page === 'login' && allowed) return { path: `${rolePath(route.role)}/dashboard`, page: 'dashboard', role: route.role };
  return { path, ...route, denied: route.page === 'login' && Boolean(session) && !allowed };
}
export function createRouter(onChange, { target = window, session = getSession, expiry = checkExpiry, watch = subscribe, onLeave = () => {}, canLeave = () => true } = {}) {
  let current = null;
  function refresh() {
    expiry();
    const next = resolveRoute(target.location.pathname, session());
    if(current&&current.path!==next.path&&!canLeave(current,next)){target.history.replaceState(null,'',current.path);return {...current};}
    if (next.path !== target.location.pathname) target.history.replaceState(null, '', next.path);
    const previous = current; current = next;
    if (previous?.path !== next.path) onLeave(previous, next);
    onChange({ ...next }); return { ...next };
  }
  function navigate(path, { replace = false } = {}) {
    // Route state never includes credentials, token data or arbitrary query targets.
    if (typeof path !== 'string' || !/^\/[A-Za-z0-9/-]*$/.test(path) || path.includes('//') || path.includes('..')) path = '/not-found';
    if (path !== target.location.pathname) target.history[replace ? 'replaceState' : 'pushState'](null, '', path);
    return refresh();
  }
  target.addEventListener('popstate', refresh);
  const unsubscribe = watch(refresh);
  return { start: refresh, refresh, navigate, current: () => current && { ...current }, dispose() { target.removeEventListener('popstate', refresh); unsubscribe(); } };
}
