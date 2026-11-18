import { mountAdminAI } from '../admin-ai/view.js';
import { mountMerchant } from '../merchant/view.js';
import { MERCHANT_PAGES } from '../merchant/routes.js';
import { mountAdmin } from '../admin/view.js';
import { ADMIN_PAGES } from '../admin/routes.js';
import { mountRecovery } from '../auth/recovery-view.js';
import { createRegistration } from './registration.js';
import { getSession, subscribe } from '../auth/session.js';
import { createRouter } from './router.js';
import { validateSignup } from './signup.js';
import { setText } from '../components/dom.js';
const SIGNUP_FIELDS = ['firstName','lastName','businessName','email','mobile','businessType','country','password','confirmPassword','terms'];
const PLACEHOLDERS = Object.freeze({
  'AI Chatbot': 'The conversational assistant is planned. Use the existing explicit payment investigation for supported analysis.',
  'Profile and Settings': 'Profile editing is planned. Remember Me, session restoration and logout are implemented; password recovery is an explicitly gated local demo. No profile endpoint is assumed.',
  'Merchant Management': 'Merchant discovery and management are planned. No merchant listing or administrative mutation is available.',
  'Pending Approvals': 'Merchant verification and approval are planned for future phases. No approval records or actions are fabricated.',
  'Audit and Settings': 'An audit browsing/settings interface is planned. Settlement tokens and signing operations are not exposed in this portal.'
});
export function mountPortals({ workspace, payments, details, clearLogin, onChatBusy=()=>{}, onPaymentContextLeave=()=>{}, onPaymentContextEnter=()=>{} }) {
  const $ = id => document.getElementById(id);
  const recoveryUI=mountRecovery();
  const adminUI=mountAdmin({navigate:path=>router.navigate(path),openPayment:id=>{router.navigate('/admin/dashboard');showPanel('operations');payments.openLookup();void workspace.lookup(id);},financialLocked:()=>payments.investigationBlocked()||details.financialLocked()});
  const merchantUI=mountMerchant({onChatBusy,navigate:path=>router.navigate(path),openPayment:id=>{router.navigate('/merchant/dashboard');showPanel('operations');payments.openLookup();void workspace.lookup(id);},financialLocked:()=>payments.investigationBlocked()||details.financialLocked()});
  let adminChat;const adminAI=()=>adminChat??=mountAdminAI($('admin-ai-workspace'),{onBusy:onChatBusy,locked:()=>adminUI.pending()||payments.investigationBlocked()||details.financialLocked(),openPayment:id=>{router.navigate('/admin/dashboard');showPanel('operations');payments.openLookup();void workspace.lookup(id);}});
  let current, navRole = null, panel = 'overview';
  const registration = createRegistration(state => {
    $('signup-form').setAttribute('aria-busy', String(state.busy));
    $('signup-check').disabled = state.busy;
    for (const key of SIGNUP_FIELDS) $(`signup-${key}`).disabled = state.busy;
    $('signup-toggle').disabled = state.busy;
    if (state.message !== undefined) setText($('signup-feedback'), state.message);
    if (state.success !== undefined) $('signup-success-link').hidden = !state.success;
  });
  subscribe(resetSignup);
  const navButtons = new Map();
  const operationLinks = { 'Known payment operations': $('nav-lookup'), 'Create payment': $('nav-create'), 'AI Investigation Reports': $('nav-investigation') };
  function resetSignup() {
    registration.reset(); $('signup-form').reset();
    for (const key of SIGNUP_FIELDS) { setText($(`signup-error-${key}`), ''); $(`signup-${key}`).removeAttribute('aria-invalid'); }
    $('signup-password').type = $('signup-confirmPassword').type = 'password';
    $('signup-toggle').setAttribute('aria-pressed', 'false'); setText($('signup-toggle'), 'Show passwords'); setText($('signup-feedback'), '');
  }
  function dashboardPending(route) { return route.page === 'dashboard' && getSession()?.accountStatus !== 'ACTIVE'; }
  function showPanel(next) {
    if(next!=='operations')onPaymentContextLeave();
    if((merchantUI.chatBusy()||adminChat?.busy())&&next==='operations')return;
    adminUI.hide();adminChat?.hide();merchantUI.hide();
    if (getSession()?.accountStatus !== 'ACTIVE') { $('portal-overview').hidden = true; $('portal-placeholder').hidden = true; $('workspace-operations').hidden = true; return; }
    panel = next;
    for (const [name, button] of navButtons) {
      const selected = (next === 'overview' && ['Overview','Dashboard overview'].includes(name)) || next === name;
      button.className = `portal-nav-button ${selected ? 'nav-current' : 'nav-link'}`;
      if (selected) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    }
    if (next !== 'operations') for (const id of ['nav-lookup','nav-create','nav-investigation']) { $(id).removeAttribute('aria-current'); $(id).className = 'nav-link'; }
    $('portal-overview').hidden = next !== 'overview';
    $('portal-placeholder').hidden = !Object.hasOwn(PLACEHOLDERS, next);
    $('workspace-operations').hidden = next === 'overview' || Object.hasOwn(PLACEHOLDERS, next);
    if(next==='operations')onPaymentContextEnter();
    if (Object.hasOwn(PLACEHOLDERS, next)) { setText($('placeholder-title'), next); setText($('placeholder-copy'), PLACEHOLDERS[next]); $('placeholder-title').focus(); }
  }
  function openOperations(section) {
    showPanel('operations'); payments.openLookup();
    if (section === 'refund' && details.selected()) $('refund-title').focus();
    else if (section === 'investigation' && details.selected()) $('investigation-title').focus();
    else { $('payment-id').focus(); if (section) setText($('lookup-feedback'), 'Look up a known authorized payment to view its refunds or current investigation report.'); }
  }
  function buildNav(role) {
    if (navRole === role) return; navRole = role;
    $('portal-nav-extra').replaceChildren(); navButtons.clear();
    const entries = role === 'ADMIN' ? ['Overview','Merchant Management','Pending Approvals','Payment Monitoring','Refund Monitoring','Audit History','Admin Accounts','Admin Profile','Known payment operations','Create payment','AI Investigation Reports','AI Assistant'] : ['Dashboard','Payments','Refunds','Business Profile','Account Security','Known payment operations','Create payment','Payment Links','AI Investigation Reports','AI Assistant'];
    for (const name of entries) {
      if (operationLinks[name]) { $('portal-nav-extra').append(operationLinks[name]); continue; }
      const button = document.createElement('button'); button.type = 'button'; button.className = 'portal-nav-button nav-link'; button.textContent = name;
      button.addEventListener('click', () => { const target=role==='ADMIN'?Object.entries(ADMIN_PAGES).find(([,label])=>label===name||name==='Overview'&&label==='Dashboard')?.[0]:Object.entries(MERCHANT_PAGES).find(([,label])=>label===name)?.[0];if(target){panel='overview';router.navigate(target);return;} if (name === 'Overview' || name === 'Dashboard overview') { showPanel('overview'); $('portal-overview-title').focus(); } else if (name === 'Refunds' || name === 'Refund Monitoring') openOperations('refund'); else showPanel(name); });
      navButtons.set(name, button); $('portal-nav-extra').append(button);
    }
  }
  const router = createRouter(route => {
    current = route;
    const pending = dashboardPending(route);
    const publicPage = ['landing','signup','forgot','not-found'].includes(route.page), dashboard = route.page === 'dashboard';
    const title = route.role === 'ADMIN' ? 'Admin' : 'Merchant';
    $('public-shell').hidden = !publicPage; $('portal-shell').hidden = publicPage;
    $('recovery-page').hidden = route.page !== 'forgot'; recoveryUI.observe(route);
    $('landing-page').hidden = route.page !== 'landing'; $('signup-page').hidden = route.page !== 'signup'; $('not-found-page').hidden = route.page !== 'not-found';
    $('login-view').hidden = route.page !== 'login'; $('private-view').hidden = !dashboard;
    $('workspace-nav').hidden = !dashboard || pending;
    $('pending-onboarding').hidden = !pending; $('login-portal-nav').hidden = dashboard;
    $('skip-link').href = publicPage ? '#public-main' : '#main';
    document.title = `PayMesh AI · ${route.page === 'landing' ? 'Payment orchestration & AI investigation' : route.page === 'forgot' ? `${title} password recovery` : route.page === 'signup' ? 'Merchant registration' : route.page === 'not-found' ? 'Page unavailable' : `${title} ${dashboard ? 'dashboard' : 'sign in'}`}`;
    if (route.page === 'login') {
      $('forgot-link').href=route.role==='ADMIN'?'/admin/forgot-password':'/merchant/forgot-password';
      setText($('login-portal-name'), `${title.toUpperCase()} PORTAL`); setText($('login-title'), `${title} sign in`);
      setText($('portal-header'), `${title} secure access`); $('merchant-signup-link').hidden = route.role !== 'MERCHANT';
      setText($('login-role-feedback'), route.denied ? `This portal requires the ${route.role} role. Your current session is not granted access here. Signing in replaces that session and clears private recovery intents; return to your existing portal if recovery is pending.` : 'Access is checked by Java. Session restoration uses an HttpOnly cookie.');
    }
    if (dashboard) {
      buildNav(route.role); setText($('workspace-title'), `${title} dashboard`); setText($('portal-header'), `${title} operations portal`);
      setText($('nav-lookup'), 'Known payment operations'); setText($('nav-investigation'), 'AI Investigation Reports');
      setText($('nav-scope'), route.role === 'ADMIN' ? 'Admin · authorized cross-merchant operations' : 'Merchant · authorized memberships only');
      setText($('scope'), route.role === 'ADMIN' ? 'Operate on known payment UUIDs across authorized merchant contexts. Java verifies every request.' : 'Manage payments for merchant memberships authorized by Java. Merchant ID is never inferred from your login.');
      setText($('portal-overview-title'), `${title} overview`);
      setText($('portal-overview-copy'), route.role === 'ADMIN' ? 'Payment and refund monitoring use known authorized UUIDs. Merchant management, approvals and audit browsing are available. AI Assistant uses authorized Java chat when separately enabled and cannot perform administrative or financial actions.' : 'Use Payments to create or look up a known payment, then inspect gateway history, manage refunds and request AI investigation. Payment Links and Business Profile are available. AI Assistant uses authorized Java chat when separately enabled; conversational answers cannot execute financial actions.');
      showPanel(panel);
      if(route.role==='ADMIN'&&panel!=='operations'){ $('portal-overview').hidden=true;$('portal-placeholder').hidden=true;$('workspace-operations').hidden=true;if(route.adminView==='/admin/ai')adminAI().show();else adminUI.show(route.adminView||'/admin/dashboard');for(const [name,button] of navButtons){const selected=(name==='Overview'&&route.adminView==='/admin/dashboard')||name===ADMIN_PAGES[route.adminView];button.className='portal-nav-button '+(selected?'nav-current':'nav-link');if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');} }
      if(route.role==='MERCHANT'&&!pending&&panel!=='operations'&&!Object.hasOwn(PLACEHOLDERS,panel)){ $('portal-overview').hidden=true;$('portal-placeholder').hidden=true;$('workspace-operations').hidden=true;merchantUI.show(route.merchantView||'/merchant/dashboard');for(const [name,button] of navButtons){const selected=name===MERCHANT_PAGES[route.merchantView||'/merchant/dashboard'];button.className='portal-nav-button '+(selected?'nav-current':'nav-link');if(selected)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');} }
      if(pending){const status=getSession()?.accountStatus;setText($('pending-title'),status==='PENDING_APPROVAL'?'Awaiting admin approval':status==='SUSPENDED'?'Merchant access suspended':'Registration rejected');setText($('pending-onboarding').querySelector('[role="status"]'),status==='PENDING_APPROVAL'?'Your account is awaiting admin approval. You will be able to accept payments once your account is approved.':'Financial access is unavailable. Contact an authorized administrator.');}
      if (pending) { $('portal-overview').hidden = true; $('portal-placeholder').hidden = true; $('workspace-operations').hidden = true; setText($('workspace-title'), 'Merchant onboarding'); setText($('scope'), 'Your account is awaiting admin approval. Financial operations are unavailable.'); setText($('nav-scope'), 'Merchant · pending approval'); }
    }
  }, { canLeave(previous,next){return !getSession()||previous?.path===next.path||!(adminUI.pending()||Boolean(adminChat?.busy())||merchantUI.pending()||payments.investigationBlocked()||details.financialLocked());},onLeave(previous, next) {
    adminUI.hide();adminChat?.hide();adminChat?.clear();merchantUI.hide();merchantUI.clearChat();
    onPaymentContextLeave();workspace.cancelLogin(); clearLogin();
    if (previous?.page === 'signup') resetSignup();
    if (previous?.path !== next.path) panel = 'overview';
    const target = next.page === 'landing' ? 'public-main' : next.page === 'forgot' ? 'recovery-title' : next.page === 'signup' ? 'signup-title' : next.page === 'not-found' ? 'not-found-title' : next.page === 'login' ? 'login-title' : next.merchantView==='/merchant/ai'?'merchant-ai-title':next.adminView==='/admin/ai'?'admin-ai-title':'workspace-title';
    // Focus after visibility and headings have been updated by the route callback.
    queueMicrotask(() => $(target).focus());
  } });
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const anchor = event.target.closest?.('a'); if (!anchor || anchor.target === '_blank' || anchor.hasAttribute('download')) return;
    const url = new URL(anchor.href, window.location.href);
    const publicAnchor = url.pathname === '/' && ['#features','#how-it-works'].includes(url.hash);
    if (url.origin !== window.location.origin || (!anchor.hasAttribute('data-route') && !publicAnchor)) return;
    event.preventDefault(); router.navigate(url.pathname);
    if (publicAnchor) { const heading = $(url.hash === '#features' ? 'features-title' : 'how-title'); heading.setAttribute('tabindex','-1'); heading.focus(); }
  });
  $('nav-lookup').addEventListener('click', () => showPanel('operations'));
  $('nav-create').addEventListener('click', () => showPanel('operations'));
  $('nav-investigation').addEventListener('click', () => openOperations('investigation'));
  $('signup-toggle').addEventListener('click', () => {
    const show = $('signup-password').type === 'password';
    $('signup-password').type = $('signup-confirmPassword').type = show ? 'text' : 'password';
    $('signup-toggle').setAttribute('aria-pressed', String(show)); setText($('signup-toggle'), show ? 'Hide passwords' : 'Show passwords');
  });
  async function checkSignup(event) {
    event?.preventDefault();
    const input = Object.fromEntries(SIGNUP_FIELDS.map(key => [key, key === 'terms' ? $(`signup-${key}`).checked : $(`signup-${key}`).value]));
    const errors = validateSignup(input);
    for (const key of SIGNUP_FIELDS) { setText($(`signup-error-${key}`), errors[key] || ''); $(`signup-${key}`).setAttribute('aria-invalid', String(Boolean(errors[key]))); }
    const first = Object.keys(errors)[0];
    if (first) { setText($('signup-feedback'), 'Check the highlighted fields.'); $(`signup-${first}`).focus(); return; }
    const pending = registration.submit(input);
    $('signup-password').value = $('signup-confirmPassword').value = '';
    await pending;
  }
  $('signup-check').addEventListener('click', checkSignup); $('signup-form').addEventListener('submit', checkSignup);
  router.start();
  return { refresh: router.refresh, current: router.current, navigate: router.navigate,
    chatBusy:()=>Boolean(merchantUI.chatBusy()||adminChat?.busy()),
    switchBlocked(){return adminUI.pending()||Boolean(adminChat?.busy())||merchantUI.pending()||payments.investigationBlocked()||details.financialLocked();},
    loginRole() { const route = router.current(); return route?.page === 'login' ? route.role : null; },
    logout() { const role = current?.role || 'MERCHANT'; workspace.logout(); router.navigate(`${role === 'ADMIN' ? '/admin' : '/merchant'}/login`, { replace: true }); }
  };
}
