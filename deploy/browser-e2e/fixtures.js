import fs from 'node:fs';
import path from 'node:path';
import { authBudget, AUTH_PATHS } from './auth-budget.js';
import { test as base, expect } from '@playwright/test';
export const ORIGIN = 'http://127.0.0.1:15500';
export const ACTION_CODES = new Set(['ADMIN_LOGIN_STARTED', 'LOGIN_RESPONSE_RECEIVED', 'ADMIN_DASHBOARD_VISIBLE', 'MERCHANT_SEARCH_STARTED', 'MERCHANT_SEARCH_INPUT', 'MERCHANT_SEARCH_COMPLETED', 'MERCHANT_DETAIL_OPENED', 'APPROVAL_REVIEW_FILLED', 'APPROVAL_DIALOG_OPENED', 'APPROVAL_CANCELLED', 'APPROVAL_SUBMITTED', 'APPROVAL_CONFIRMED', 'ACTIVE_MERCHANT_LOGIN', 'PAYMENT_CREATED', 'PAYMENT_PROCESSED', 'PAYMENT_LIST_OPENED', 'OWNERSHIP_DENIAL', 'INVESTIGATION_SUBMITTED', 'REFUND_SUBMITTED', 'CHECKOUT_LINK_CREATED', 'CHECKOUT_SUBMITTED', 'CHAT_SUBMITTED', 'HISTORY_RENAMED', 'HISTORY_LISTED', 'HISTORY_LOADED', 'HISTORY_REFRESHED', 'HISTORY_DELETED', 'CROSS_TAB_RESTORED', 'LOGOUT_CONFIRMED', 'PORTAL_NAVIGATION', 'SESSION_REFRESH','CHECKOUT_FORM_READY','CHECKOUT_CURRENCY_SELECTED','CHECKOUT_METHOD_SELECTED','CHECKOUT_REVIEW_OPENED','CUSTOMER_CHECKOUT_OPENED','CUSTOMER_PAYMENT_REVIEWED','CHECKOUT_RECEIPT_VISIBLE','CHECKOUT_MERCHANT_STATUS_CONFIRMED','CHECKOUT_PAYMENT_AVAILABLE']);
export const UI_STATES = new Set(['LINK_CREATE_FORM','LINK_REVIEW','LINK_CREATED','PUBLIC_CHECKOUT','PAYMENT_REVIEW','PAID_RECEIPT','MERCHANT_PAID_LINK','CHAT_ANSWER','SAVED_HISTORY','LOGGED_OUT']);
export const ROUTE_CODES = new Set(['MERCHANT_LINK_CREATE','MERCHANT_LINKS','MERCHANT_DASHBOARD','ADMIN_DASHBOARD','MERCHANT_AI','ADMIN_AI','MERCHANT_LOGIN','ADMIN_LOGIN','PUBLIC_CHECKOUT','OTHER_LOCAL_ROUTE','OTHER_ORIGIN','UNAVAILABLE']);
export const HTTP_CODES = new Set(['LINK_CREATE','LINK_READ','CHECKOUT_READ','CHECKOUT_PAY','PAYMENT_READ','PAYMENT_CREATE','PAYMENT_PROCESS','REFUND','INVESTIGATION','CHAT_MESSAGE','HISTORY_READ','HISTORY_RENAME','HISTORY_DELETE','OTHER_REQUEST','AUTH_REFRESH','AUTH_LOGOUT','AUTH_LOGIN']);
const actionScopes=[];
export function routeCategory(raw) {
  try{const url=new URL(raw);if(url.origin!==ORIGIN)return 'OTHER_ORIGIN';
    const routes={'/merchant/payment-links/create':'MERCHANT_LINK_CREATE','/merchant/payment-links':'MERCHANT_LINKS','/merchant/dashboard':'MERCHANT_DASHBOARD','/admin/dashboard':'ADMIN_DASHBOARD','/merchant/ai':'MERCHANT_AI','/admin/ai':'ADMIN_AI','/merchant/login':'MERCHANT_LOGIN','/admin/login':'ADMIN_LOGIN'};
    return routes[url.pathname]||(/^\/checkout\/[A-Za-z0-9_-]{43}$/.test(url.pathname)?'PUBLIC_CHECKOUT':'OTHER_LOCAL_ROUTE');
  }catch{return 'UNAVAILABLE';}
}
export function httpCategory(raw,method) {
  try{const url=new URL(raw);if(url.origin!==ORIGIN)return 'OTHER_REQUEST';const p=url.pathname;
    for(const [endpoint,code] of [['refresh','AUTH_REFRESH'],['logout','AUTH_LOGOUT'],['login','AUTH_LOGIN']])if(p==='/api/v1/auth/'+endpoint&&method==='POST')return code;
    if(p==='/api/v1/merchant/payment-links'&&method==='POST')return 'LINK_CREATE';
    if(/^\/api\/v1\/merchant\/payment-links\/[0-9a-f-]{36}$/.test(p)&&method==='GET')return 'LINK_READ';
    if(/^\/api\/v1\/checkout\/[A-Za-z0-9_-]{43}(?:\/status)?$/.test(p)&&method==='GET')return 'CHECKOUT_READ';
    if(/^\/api\/v1\/checkout\/[A-Za-z0-9_-]{43}\/pay$/.test(p)&&method==='POST')return 'CHECKOUT_PAY';
    if(p==='/api/v1/payments'&&method==='POST')return 'PAYMENT_CREATE';
    if(/^\/api\/v1\/payments\/[0-9a-f-]{36}$/.test(p)&&method==='GET')return 'PAYMENT_READ';
    for(const [suffix,code] of [['process','PAYMENT_PROCESS'],['refund','REFUND'],['investigate','INVESTIGATION']])if(new RegExp('^/api/v1/payments/[0-9a-f-]{36}/'+suffix+'$').test(p)&&method==='POST')return code;
    if(/^\/api\/v1\/(merchant|admin)\/ai\/conversations\/[0-9a-f-]{36}\/messages$/.test(p))return method==='POST'?'CHAT_MESSAGE':method==='GET'?'HISTORY_READ':'OTHER_REQUEST';
    for(const [suffix,code] of [['rename','HISTORY_RENAME'],['delete','HISTORY_DELETE']])if(new RegExp('^/api/v1/(merchant|admin)/ai/conversations/[0-9a-f-]{36}/'+suffix+'$').test(p)&&method==='POST')return code;
  }catch{}
  return 'OTHER_REQUEST';
}
export async function checkpoint(code, action, {page,expectedState=null,expectedHttp=null}={}) {
  requireSafe(ACTION_CODES.has(code), 'FIXED_ACTION_CODE_REQUIRED');
  requireSafe((expectedState===null||UI_STATES.has(expectedState))&&(expectedHttp===null||HTTP_CODES.has(expectedHttp)),'FIXED_ACTION_CODE_REQUIRED');
  const scope={code,expectedState,expectedHttp,status:null};actionScopes.push(scope);
  try{return await test.step(code,action);}catch(error){
    try{test.info().annotations.push({type:'safe-ui-context',description:JSON.stringify({actionCode:code,expectedState,routeCode:routeCategory(page?.url()),httpCode:expectedHttp,httpStatus:scope.status})});}catch{}
    throw error;
  }finally{actionScopes.splice(actionScopes.indexOf(scope),1);}
}
function recordHttpStatus(status, raw, method) {
  const scope=actionScopes.at(-1);if(scope?.expectedHttp&&httpCategory(raw,method)===scope.expectedHttp)scope.status=status;
  if(Number.isInteger(status)&&status>=100&&status<=599){
    try{test.info().annotations.push({type:'safe-http-status',description:String(status)});}catch{/* Test may already be tearing down. No raw diagnostic is retained. */}
  }
}
export function requireSafe(ok, code) { if (!ok) throw new Error(code); }
export function guard(env = process.env) {
  requireSafe(env.GITHUB_ACTIONS === 'true' && env.RUNNER_OS === 'Linux' && env.RUNNER_ENVIRONMENT === 'github-hosted', 'HOSTED_RUNNER_REQUIRED');
  requireSafe(env.GITHUB_REPOSITORY === 'bhupirao/paymesh-ai' && env.GITHUB_REF === 'refs/heads/main' && env.GITHUB_EVENT_NAME === 'workflow_dispatch', 'MANUAL_MAIN_REQUIRED');
  requireSafe(env.E2E_VERIFY_QWEN === 'true' && ['', 'unix:///var/run/docker.sock'].includes(env.DOCKER_HOST || ''), 'FIXED_LOCAL_STACK_REQUIRED');
  requireSafe(/^\d+$/.test(env.GITHUB_RUN_ID || '') && /^\d+$/.test(env.GITHUB_RUN_ATTEMPT || ''), 'RUN_ID_REQUIRED');
  const project = `paymesh-e2e-${env.GITHUB_RUN_ID}-${env.GITHUB_RUN_ATTEMPT}`;
  const folder = path.join(fs.realpathSync(env.RUNNER_TEMP), project);
  requireSafe(env.E2E_PROJECT === project && env.E2E_DIR === folder && env.E2E_ENV === path.join(folder, 'container.env'), 'FIXTURE_SCOPE_REQUIRED');
  const stat = fs.lstatSync(folder);
  requireSafe(stat.isDirectory() && !stat.isSymbolicLink() && !(stat.mode & 0o077) && stat.uid === process.getuid(), 'PRIVATE_FIXTURE_DIRECTORY_REQUIRED');
  return folder;
}
export function privateDirectory(name, env = process.env) {
  requireSafe(name === 'browser-private-output', 'FIXED_OUTPUT_DIRECTORY_REQUIRED');
  const run = guard(env); // Canonical temp parent; private, owned, non-symlink run.
  const folder = path.resolve(run, name);
  requireSafe(fs.realpathSync(run) === run && folder !== run && path.dirname(folder) === run
    && path.relative(run, folder) === name, 'PRIVATE_OUTPUT_REQUIRED');
  let fd;
  try {
    // No recursive creation/chmod: the private run must already exist.
    try { fs.mkdirSync(folder, { mode: 0o700 }); }
    catch (error) { if (error.code !== 'EEXIST') throw error; }
    const before = fs.lstatSync(folder);
    requireSafe(before.isDirectory() && !before.isSymbolicLink() && before.uid === process.getuid()
      && fs.realpathSync(folder) === folder, 'PRIVATE_OUTPUT_REQUIRED');
    fd = fs.openSync(folder, fs.constants.O_RDONLY | fs.constants.O_DIRECTORY | fs.constants.O_NOFOLLOW);
    const opened = fs.fstatSync(fd);
    const current = fs.lstatSync(folder);
    requireSafe(opened.isDirectory() && opened.uid === process.getuid()
      && opened.dev === before.dev && opened.ino === before.ino
      && current.isDirectory() && !current.isSymbolicLink()
      && current.dev === opened.dev && current.ino === opened.ino, 'PRIVATE_OUTPUT_REQUIRED');
    // Playwright can recreate this exact leaf with its default umask. Secure the
    // validated inode through its no-follow descriptor, never a substituted path.
    fs.fchmodSync(fd, 0o700);
    const secured = fs.fstatSync(fd), after = fs.lstatSync(folder);
    requireSafe(secured.isDirectory() && secured.uid === process.getuid() && (secured.mode & 0o7777) === 0o700
      && after.isDirectory() && !after.isSymbolicLink() && after.uid === process.getuid() && (after.mode & 0o7777) === 0o700
      && after.dev === secured.dev && after.ino === secured.ino
      && fs.realpathSync(folder) === folder, 'PRIVATE_OUTPUT_REQUIRED');
    return folder;
  } catch { throw new Error('PRIVATE_OUTPUT_REQUIRED'); }
  finally { if (fd !== undefined) fs.closeSync(fd); }
}
export function credential(name) {
  requireSafe(['admin_password', 'merchant_password'].includes(name), 'FIXED_CREDENTIAL_REQUIRED');
  const folder = path.join(guard(), 'secrets');
  const directory = fs.lstatSync(folder);
  requireSafe(directory.isDirectory() && !directory.isSymbolicLink() && !(directory.mode & 0o077), 'PRIVATE_SECRET_DIRECTORY_REQUIRED');
  const file = path.join(folder, name), stat = fs.lstatSync(file);
  requireSafe(stat.isFile() && !stat.isSymbolicLink() && stat.uid === process.getuid() && !(stat.mode & 0o022) && stat.size >= 20 && stat.size <= 72, 'FIXTURE_CREDENTIAL_INVALID');
  return fs.readFileSync(file, 'utf8');
}
export const accounts = {
  admin: 'ci-admin@e2e.example.test',
  a: 'browser-a@e2e.example.test',
  b: 'browser-b@e2e.example.test'
};
export function recordBrowserReady(browser, title) {
  const allowed=['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'];
  requireSafe(allowed.includes(title) && browser.isConnected() && browser.browserType().name()==='chromium', 'CHROMIUM_WITNESS_REQUIRED');
  fs.writeFileSync(path.join(guard(),'browser-launch-'+title+'.json'), JSON.stringify({testCode:title,chromiumLaunchStatus:'SUCCEEDED'}), {mode:0o600,flag:'wx'});
}
export const test = base.extend({
  browserDiagnostics: [async ({ browser }, use, testInfo) => {
    recordBrowserReady(browser, testInfo.title);
    await use();
    authBudget.assertHealthy();
  }, { auto: true }],
  context: async ({ context }, use) => {
    guard();
    await restrictNetwork(context);
    await use(context);
  }
});
export { expect };
const monitoredContexts=new WeakSet();
export async function restrictNetwork(context) {
  if(!monitoredContexts.has(context)) {
    monitoredContexts.add(context);
    context.on('request',request=>{
      let url;try{url=new URL(request.url());}catch{return;}
      if(url.origin===ORIGIN&&request.method()==='POST'&&AUTH_PATHS.has(url.pathname)){
        try{authBudget.request(request,request.frame().page(),url.pathname);}catch{authBudget.observationFailed=true;}
      }
    });
    context.on('response',response=>authBudget.response(response.request(),response.status()));
    context.on('requestfailed',request=>authBudget.failed(request));
  }
  await context.route('**/*', route => {
    let allowed = false;
    try { allowed = new URL(route.request().url()).origin === ORIGIN; } catch { /* deny */ }
    return allowed ? route.continue() : route.abort('blockedbyclient');
  });
}
export async function newPage(browser) {
  const context = await browser.newContext({ baseURL: ORIGIN, viewport: { width: 1440, height: 1000 }, acceptDownloads: false, serviceWorkers: 'block' });
  context.setDefaultTimeout(15_000);context.setDefaultNavigationTimeout(30_000);
  await restrictNetwork(context);
  return { context, page: await context.newPage() };
}
export function loginRoute(raw) {
  try {
    const url=new URL(raw);
    if(url.origin!==ORIGIN)return {routeCode:'OTHER_ORIGIN',suffixPresent:Boolean(url.search||url.hash)};
    const known={'/merchant/login':'MERCHANT_LOGIN','/merchant/dashboard':'MERCHANT_DASHBOARD','/merchant/signup':'MERCHANT_SIGNUP','/admin/login':'ADMIN_LOGIN','/admin/dashboard':'ADMIN_DASHBOARD'};
    return {routeCode:known[url.pathname]||'OTHER_ROUTE',suffixPresent:Boolean(url.search||url.hash)};
  } catch { return {routeCode:'UNAVAILABLE',suffixPresent:false}; }
}
export function loginFeedback(text) {
  if(/^Too many attempts\. (?:Wait [0-9]{1,5} seconds before trying again\.|Please wait before trying again\.)$/.test(text))return 'RATE_LIMITED';
  const known={
    '':'NO_FEEDBACK',
    'Signing in securely…':'LOGIN_PENDING',
    'Unable to sign in. Check your username and password.':'CREDENTIALS_REJECTED',
    'Invalid authentication response. Please sign in again.':'INVALID_AUTH_RESPONSE',
    'Your session is no longer valid. Please sign in again.':'SESSION_INVALID',
    'Your session expired. Please sign in again.':'SESSION_EXPIRED',
    'Previous sign-in response ignored. Sign in to the selected portal.':'STALE_RESPONSE',
    'This portal requires the MERCHANT role. Use the correct portal for your account.':'ROLE_REJECTED',
    'This portal requires the ADMIN role. Use the correct portal for your account.':'ROLE_REJECTED'
  };
  return Object.hasOwn(known,text)?known[text]:'OTHER_FEEDBACK';
}
export async function login(page, role, account) {
  let httpStatus=null;
  const observe=response=>{
    try {
      const url=new URL(response.url());
      if(url.origin===ORIGIN&&url.pathname==='/api/v1/auth/login'&&response.request().method()==='POST'){
        const code=response.status();if(Number.isInteger(code)&&code>=100&&code<=599)httpStatus=code;
      }
    } catch { /* No raw URL or error is retained. */ }
  };
  page.on('response',observe);
  try {
    await navigate(page,`/${role}/login`);
    await page.locator('#login').fill(accounts[account]);
    await page.locator('#password').fill(credential(account === 'admin' ? 'admin_password' : 'merchant_password'));
    await authAction(page,'/api/v1/auth/login',async()=>{
      const reply=responseFor(page,'POST','/api/v1/auth/login');
      await Promise.all([page.locator('#login-submit').click(), checkpoint('LOGIN_RESPONSE_RECEIVED',async()=>body(await reply))]);
    });
    await expect(page).toHaveURL(`${ORIGIN}/${role}/dashboard`);
    await expect(page.locator('#identity')).toBeVisible();
  } catch(error) {
    // Preserve the original assertion; observe only fixed classifications.
    try {
      const title=test.info().title;
      requireSafe(['COMPLETE_NATIVE_BROWSER_JOURNEY','MOBILE_KEYBOARD_AND_VALIDATION','DESKTOP_KEYBOARD_AND_VALIDATION'].includes(title),'CHROMIUM_WITNESS_REQUIRED');
      let feedbackCode='UNAVAILABLE';
      try {feedbackCode=loginFeedback((await page.locator('#login-feedback').textContent({timeout:1000}))||'');}catch{}
      const state={testCode:title,portalRole:role==='admin'?'ADMIN':'MERCHANT',httpStatus,...loginRoute(page.url()),feedbackCode};
      fs.writeFileSync(path.join(guard(),'browser-login-'+title+'.json'),JSON.stringify(state),{mode:0o600,flag:'wx'});
    } catch { /* Missing diagnostic evidence never replaces the original failure. */ }
    throw error;
  } finally {page.off('response',observe);}
}
export function responseTimeout(pathname,method='POST') {
  const text=String(pathname);
  return method==='POST'&&/investigate|messages/.test(text) ? 70_000 : 25_000;
}
export function responseFor(page, method, pathname) {
  const waiting=page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.origin === ORIGIN && response.request().method() === method && (typeof pathname === 'string' ? url.pathname === pathname : pathname.test(url.pathname));
  }, { timeout: responseTimeout(pathname,method) });
  // Attach rejection handling immediately: a failed click must not leave an
  // unhandled waitForResponse rejection after test teardown. The caller still
  // awaits the original promise and fails on timeout/status mismatch.
  const observed=waiting?.then(response=>{recordHttpStatus(response.status(),response.url(),response.request().method());return response;});
  observed?.catch(()=>{});
  return observed;
}
export async function body(response, statuses = [200]) {
  requireSafe(statuses.includes(response.status()), 'BROWSER_HTTP_STATUS_MISMATCH');
  const text = await response.text();
  requireSafe(Buffer.byteLength(text) <= 524288, 'BROWSER_RESPONSE_TOO_LARGE');
  try { return JSON.parse(text); } catch { throw new Error('BROWSER_RESPONSE_INVALID'); }
}
export function modelSuccess(value) {
  const result = value.turn?.response || value.investigation || value;
  requireSafe(result.analysisMode === 'RAG_LLM' && result.generationStatus === 'SUCCEEDED' && result.knowledgeReferences?.length > 0, 'REAL_MODEL_REQUIRED');
  return result;
}
export async function noOverflow(page) {
  requireSafe(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'HORIZONTAL_OVERFLOW');
}
export async function openHistory(root) {
  const summary = root.locator('details.conversation-history > summary');
  if (!await root.locator('details.conversation-history').evaluate(node => node.open)) await summary.click();
}
export async function safeDialog(page, action, accept = true) {
  const handler = dialog => accept ? dialog.accept() : dialog.dismiss();
  page.on('dialog', handler);
  try { return await action(); } finally { page.off('dialog', handler); }
}

export function exactAmount(value) {
  const match = /^(0|[1-9][0-9]*)(?:[.]([0-9]{1,2}))?$/.exec(String(value));
  requireSafe(Boolean(match), 'EXACT_AMOUNT_REQUIRED');
  return match[1] + '.' + (match[2] || '').padEnd(2, '0');
}
export async function logout(page) {
  return checkpoint('LOGOUT_CONFIRMED',async()=>{
    let reply;
    await authAction(page,'/api/v1/auth/logout',async()=>{reply=responseFor(page,'POST','/api/v1/auth/logout');await page.locator('#logout').click();});
    await body(await reply);
    await expect(page.locator('#login-form')).toBeVisible();
  },{page,expectedState:'LOGGED_OUT',expectedHttp:'AUTH_LOGOUT'});
}

export async function authAction(page,pathname,action) {return authBudget.run(page,pathname,action);}
// Protected routes must use the released SPA controls. A hard deep-link load
// races the in-memory session bootstrap and is redirected to the dashboard.
export const PORTAL_BUTTONS=Object.freeze({
  '/admin/dashboard':'Overview','/admin/merchants':'Merchant Management',
  '/admin/ai':'AI Assistant','/merchant/dashboard':'Dashboard',
  '/merchant/payments':'Payments','/merchant/ai':'AI Assistant',
  '/merchant/payment-links/create':'Payment Links'
});
export function navigationPlan(current,target,privateVisible) {
  const from=new URL(current,ORIGIN),to=new URL(target,ORIGIN);
  requireSafe(to.origin===ORIGIN&&!to.search&&!to.hash,'FIXED_BROWSER_TARGET_REQUIRED');
  const role=to.pathname.split('/')[1];
  const spa=from.origin===ORIGIN&&from.pathname.startsWith('/'+role+'/')&&privateVisible&&PORTAL_BUTTONS[to.pathname];
  return {spa:Boolean(spa),button:spa?PORTAL_BUTTONS[to.pathname]:null,createLink:spa&&to.pathname==='/merchant/payment-links/create'};
}
export async function navigate(page,target) {
  const url=new URL(target,ORIGIN);requireSafe(url.origin===ORIGIN&&!url.search&&!url.hash,'FIXED_BROWSER_TARGET_REQUIRED');
  if(/^\/checkout\/[A-Za-z0-9_-]{43}$/.test(url.pathname))return page.goto(target);
  const plan=navigationPlan(page.url(),target,await page.locator('#private-view').isVisible());
  if(plan.spa)return checkpoint('PORTAL_NAVIGATION',async()=>{
    await page.locator('#portal-nav-extra').getByRole('button',{name:plan.button,exact:true}).click();
    if(plan.createLink)await page.locator('#merchant-links-workspace').getByRole('button',{name:'Create Payment Link',exact:true}).click();
    await expect(page).toHaveURL(ORIGIN+url.pathname);
  });
  return authAction(page,'/api/v1/auth/refresh',async()=>{
    const restored=responseFor(page,'POST','/api/v1/auth/refresh');
    await Promise.all([page.goto(target),restored.then(response=>{
      requireSafe([200,401].includes(response.status()),'SESSION_RESTORE_HTTP_STATUS');
    })]);
  });
}
export async function refreshPage(page) {
  const url=new URL(page.url());requireSafe(url.origin===ORIGIN,'FIXED_BROWSER_TARGET_REQUIRED');
  if(/^\/checkout\/[A-Za-z0-9_-]{43}$/.test(url.pathname))return page.reload();
  return checkpoint('SESSION_REFRESH',()=>authAction(page,'/api/v1/auth/refresh',async()=>{
    const restored=responseFor(page,'POST','/api/v1/auth/refresh');
    await Promise.all([page.reload(),restored.then(response=>requireSafe(response.status()===200,'SESSION_RESTORE_HTTP_STATUS'))]);
  }),{page,expectedState:/_AI$/.test(routeCategory(page.url()))?'SAVED_HISTORY':null,expectedHttp:'AUTH_REFRESH'});
}
