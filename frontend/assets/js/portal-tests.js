import { createRouter, resolveRoute, ROUTES } from './portals/router.js';
import { validateSignup, BUSINESS_TYPES, COUNTRIES } from './portals/signup.js';
import { createWorkspace } from './features/workspace.js';
import { getSession, clearSession, setSession, getToken, checkExpiry } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
const original = window.fetch, clock = Date.now, results = [];
const assert = (value, label) => { if (!value) throw new Error(label); results.push(label); };
const merchant = { roles: ['MERCHANT'] }, admin = { roles: ['ADMIN'] };
class HistoryTarget extends EventTarget {
  constructor(path='/') {
    super(); this.location = { pathname: path }; this.entries = [path]; this.index = 0;
    this.history = { pushState: (state, _, next) => { this.entries.splice(this.index+1); this.entries.push(next); this.index++; this.location.pathname = next; }, replaceState: (state, _, next) => { this.entries[this.index] = next; this.location.pathname = next; } };
  }
  back() { if (this.index > 0) { this.location.pathname = this.entries[--this.index]; this.dispatchEvent(new Event('popstate')); } }
  forward() { if (this.index < this.entries.length-1) { this.location.pathname = this.entries[++this.index]; this.dispatchEvent(new Event('popstate')); } }
}
let state;
const workspace = createWorkspace(next => { state = next; }); workspace.start();
let router;
try {
  assert(Object.keys(ROUTES).length === 24, 'twenty-four explicit frontend routes including Merchant and Admin AI');
  for (const path of ['/','/merchant/signup','/merchant/login','/admin/login']) assert(resolveRoute(path,null).path === path, `public route ${path}`);
  assert(resolveRoute('/index.html',null).path === '/', 'legacy shell alias resolves home');
  for (const path of ['/unknown','/admin/signup','/merchant/dashboard/extra']) assert(resolveRoute(path,merchant).page === 'not-found', 'unknown route never exposes workspace');
  assert(resolveRoute('/merchant/dashboard',null).path === '/merchant/login', 'unauthenticated merchant dashboard redirects sign-in');
  assert(resolveRoute('/admin/dashboard',null).path === '/admin/login', 'unauthenticated admin dashboard redirects sign-in');
  assert(resolveRoute('/merchant/dashboard',merchant).page === 'dashboard', 'merchant enters own portal');
  assert(resolveRoute('/admin/dashboard',admin).page === 'dashboard', 'admin enters own portal');
  assert(resolveRoute('/merchant/dashboard',admin).path === '/merchant/login', 'admin-only role cannot enter merchant dashboard');
  assert(resolveRoute('/admin/dashboard',merchant).path === '/admin/login', 'merchant role cannot enter admin dashboard');
  assert(resolveRoute('/merchant/login',admin).page === 'login' && resolveRoute('/merchant/login',admin).denied, 'wrong-role sign-in does not auto-elevate');
  assert(resolveRoute('/admin/login',merchant).denied, 'merchant warned on admin login');
  assert(resolveRoute('/merchant/dashboard',{roles:['ADMIN','MERCHANT']}).page === 'dashboard', 'dual-role account needs actual merchant role for merchant portal');
  for (const [role,path] of [['MERCHANT','/merchant/dashboard'],['ADMIN','/admin/dashboard']]) {
    clearSession(); window.fetch = async (url, options) => {
      assert(url === '/api/v1/auth/login' && options.method === 'POST', 'existing login endpoint reused');
      assert(Object.keys(JSON.parse(options.body)).sort().join(',') === 'login,password', 'no client role sent to Java');
      return new Response(JSON.stringify(tokenResponse([role])));
    };
    await workspace.login('synthetic-login','synthetic-password',role);
    assert(getSession()?.roles.includes(role), 'correct role accepted only after token validation');
    assert(resolveRoute(path,getSession()).page === 'dashboard', 'correct login routes to matching dashboard');
  }
  for (const [actual,required] of [['ADMIN','MERCHANT'],['MERCHANT','ADMIN']]) {
    clearSession(); window.fetch = async () => new Response(JSON.stringify(tokenResponse([actual])));
    await workspace.login('synthetic','synthetic',required);
    assert(!getToken() && state.message.includes(required), 'wrong-role credentials never install session');
  }
  clearSession(); let release; let calls = 0;
  window.fetch = () => { calls++; return new Promise(resolve => { release=resolve; }); };
  const pending = workspace.login('synthetic','synthetic','MERCHANT');
  workspace.cancelLogin(); await workspace.login('synthetic','synthetic','ADMIN');
  assert(state.loginBusy && calls === 1, 'navigation invalidates login and prevents overlapping submission');
  release(new Response(JSON.stringify(tokenResponse(['MERCHANT'])))); await pending;
  assert(!getSession() && !state.loginBusy && !state.message.includes('still pending'), 'late login after portal navigation ignored and controls restored');
  window.fetch = async () => new Response(JSON.stringify({...tokenResponse(),accessToken:'bad'}));
  await workspace.login('synthetic','synthetic','MERCHANT'); assert(!getSession(), 'malformed token cannot enter portal');
  setSession(tokenResponse(), 'synthetic');
  const target = new HistoryTarget('/merchant/dashboard'); let route;
  router = createRouter(next => { route = next; }, { target }); router.start();
  assert(route.page === 'dashboard', 'direct URL recognizes memory session');
  router.navigate('/'); assert(route.page === 'landing' && getToken(), 'same-document home retains memory token');
  router.navigate('/merchant/signup'); assert(route.page === 'signup' && getToken(), 'public preview navigation does not discard active session');
  target.back(); assert(route.page === 'landing', 'Back returns to prior public page');
  target.back(); assert(route.page === 'dashboard', 'Back restores authorized dashboard');
  target.forward(); assert(route.page === 'landing', 'Forward navigation guarded');
  router.navigate('/merchant/dashboard');
  clearSession(); assert(route.page === 'login' && !getSession(), 'logout immediately removes dashboard access');
  target.back(); target.back(); assert(route.page !== 'dashboard', 'Back cannot restore a logged-out dashboard');
  router.navigate('/unknown'); assert(route.page === 'not-found', 'unknown client route safe');
  router.navigate('https://evil.example'); assert(route.page === 'not-found' && target.location.pathname === '/not-found', 'arbitrary navigation target rejected');
  router.dispose();
  // A fresh document starts without any session, even on a known dashboard URL.
  router = createRouter(next => { route=next; }, { target: new HistoryTarget('/admin/dashboard') }); router.start();
  assert(route.path === '/admin/login', 'refresh requires sign-in rather than restored token');
  router.dispose();
  setSession(tokenResponse()); const expiring = new HistoryTarget('/merchant/dashboard');
  router = createRouter(next => { route=next; }, { target: expiring }); router.start();
  Date.now = () => clock()+901000; checkExpiry(); Date.now = clock;
  assert(route.path === '/merchant/login' && !getSession(), 'expiry clears dashboard route');
  router.dispose();
  const signup = { firstName:'Demo',lastName:'Operator',businessName:'Synthetic business',email:'demo@example.test',mobile:'+919876543210',businessType:'COMPANY',country:'IN',password:'synthetic-only',confirmPassword:'synthetic-only',terms:true };
  assert(Object.keys(validateSignup(signup)).length === 0, 'valid signup preview');
  for (const key of ['firstName','lastName','businessName','email','mobile','businessType','country','password','confirmPassword']) assert(validateSignup({...signup,[key]:''})[key], `signup ${key} required`);
  for (const [key,value] of [['email','not-an-email'],['mobile','123'],['mobile','+1234567890123456'],['country','ZZ'],['businessType','ADMIN'],['password','short'],['confirmPassword','different'],['terms',false]]) assert(validateSignup({...signup,[key]:value})[key], `invalid signup ${key}`);
  for (const country of COUNTRIES) assert(!validateSignup({...signup,country}).country, 'country preview choices validated');
  for (const businessType of BUSINESS_TYPES) assert(!validateSignup({...signup,businessType}).businessType, 'business preview choices validated');
  assert(Object.keys(validateSignup({...signup,firstName:' '})).includes('firstName'), 'whitespace signup name rejected');
  document.querySelector('#result').textContent = `PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch(error) { document.querySelector('#result').textContent = `FAIL: ${error.message}`; }
finally { Date.now=clock; window.fetch=original; clearSession(); router?.dispose(); workspace.dispose(); }
