import { mountPaymentAI } from './payment-ai/view.js';
import { createAccountSwitcher } from './auth/account-switch.js';
import { request } from './api/client.js';
import { subscribe,getVersion } from './auth/session.js';
import { installPersistence, signOut } from './auth/persistence.js';
import { mountPortals } from './portals/view.js';
import { clearSession, getSession } from './auth/session.js';
import { mountInvestigation } from './investigation/view.js';
import { mountRefunds } from './features/refunds-view.js';
import { mountPayments } from './features/payments-view.js';
import { createWorkspace, rolePresentation } from './features/workspace.js';
import { installLifecycle } from './auth/session.js';
import { setText } from './components/dom.js';
import { renderPayment } from './components/payment.js';
// Restore the validated memory-only session before constructing the router or
// conversation stores. Early routing erases protected history entries; early
// stores treat hydration as an account change and clear the tab bookmark.
const persistence=installPersistence();
await persistence.restore().catch(()=>{clearSession('refresh-failed');});
const $ = id => document.getElementById(id);
let previousSession = null;let accountSwitcher;let switchState={busy:false,uncertain:false};
let paymentsUI;
let investigationUI;
let portalUI;let paymentChatUI;
function hidePassword() {
  $('password').type = 'password'; $('toggle-password').setAttribute('aria-pressed', 'false');
  setText($('toggle-password'), 'Show password');
}
const workspace = createWorkspace(state => {
  const authenticated = Boolean(state.session);
  $('login-view').hidden = authenticated; $('private-view').hidden = !authenticated;
  $('workspace-nav').hidden = !authenticated;
  $('login-form').setAttribute('aria-busy', String(state.loginBusy));
  $('lookup-form').setAttribute('aria-busy', String(state.lookupBusy));
  $('login-submit').disabled = state.loginBusy||switchState.busy||switchState.uncertain;
  $('login').disabled = state.loginBusy||switchState.busy||switchState.uncertain; $('password').disabled = state.loginBusy||switchState.busy||switchState.uncertain;
  $('toggle-password').disabled = state.loginBusy; $('remember-me').disabled=state.loginBusy;
  $('lookup-submit').disabled = state.lookupBusy; $('payment-id').disabled = state.lookupBusy;
  setText($('login-submit'), state.loginBusy ? 'Signing in…' : 'Sign in');
  setText($('lookup-submit'), state.lookupBusy ? 'Loading…' : 'Look up payment');
  setText($('login-feedback'), authenticated ? '' : state.message);
  setText($('lookup-feedback'), authenticated ? state.message : '');
  renderPayment($('payment-result'), state.payment);
  paymentsUI?.observeLookup(state.payment, state.lookupBusy);
  const session = state.session;
  setText($('identity'), session?.identity); setText($('subject'), session?.subject);
  setText($('roles'), session?.roles.join(' + '));
  setText($('expiry'), session ? `Access expires at ${new Date(session.expires).toLocaleString()}. Server refresh uses an HttpOnly cookie.` : '');
  const presentation = session ? rolePresentation(session.roles) : null;
  setText($('workspace-title'), presentation?.title); setText($('scope'), presentation?.scope);
  setText($('nav-scope'), session?.roles.includes('ADMIN') ? 'Admin · cross-merchant lookup' : 'Merchant · authorized payment lookup');
  if (session !== previousSession && (!session || !previousSession || session.subject !== previousSession.subject || session.expires !== previousSession.expires)) {
    $('password').value = ''; hidePassword(); $('payment-id').value = '';
    if (!session) $('login').value = '';
    (session ? $('workspace-title') : $('login')).focus();
  }
  previousSession = session;
  portalUI?.refresh();
});
$('toggle-password').addEventListener('click', () => {
  const show = $('password').type === 'password'; $('password').type = show ? 'text' : 'password';
  $('toggle-password').setAttribute('aria-pressed', String(show));
  setText($('toggle-password'), show ? 'Hide password' : 'Show password');
});
$('login-form').addEventListener('submit', event => {
  event.preventDefault();
  if(switchState.busy||switchState.uncertain)return;
  if (!$('login').value.trim()) { $('login').setCustomValidity('Enter your username.'); $('login').reportValidity(); return; }
  if (!$('login-form').reportValidity()) return;
  const role = portalUI?.loginRole();
  if (!role) return;
  const login = $('login').value.trim(), rememberMe=$('remember-me').checked;
  let password = $('password').value;
  if (getSession()) clearSession('portal-login');
  $('password').value = ''; hidePassword();
  void workspace.login(login, password, role, rememberMe); password = '';
});
$('login').addEventListener('input', () => $('login').setCustomValidity(''));
$('lookup-form').addEventListener('submit', event => { event.preventDefault(); if (paymentsUI.lookupAllowed() && $('lookup-form').reportValidity()) void workspace.lookup($('payment-id').value); });
$('logout').addEventListener('click', async () => { $('login').value='';portalUI.logout(); const ok=await signOut();$('logout-feedback').textContent=ok?'Signed out.':'Local session cleared. Server logout could not be confirmed; retry logout before leaving this shared browser.';$('finish-logout').hidden=ok; });
$('logout-all').addEventListener('click',async()=>{portalUI.logout();const ok=await signOut(true);$('logout-feedback').textContent=ok?'Signed out on all devices.':'Local session cleared. Server-wide logout could not be confirmed. Finish local-browser logout and sign in privately to verify other-device revocation.';$('finish-logout').hidden=ok;});
$('finish-logout').addEventListener('click',async()=>{if(accountSwitcher?.state().uncertain){await accountSwitcher.retry();return;}const ok=await signOut();$('finish-logout').hidden=ok;$('logout-feedback').textContent=ok?'Current browser signed out.':'Server logout is still unconfirmed. Do not leave this browser shared.';});
const detailsUI = mountRefunds({ onState: state => {investigationUI?.observe(state, paymentsUI?.investigationBlocked() ?? false);paymentChatUI?.observe(state);}, readBusy: () => Boolean(investigationUI?.busy()||portalUI?.chatBusy()||paymentChatUI?.busy()), onLock: () => paymentsUI?.refreshLocks(), onSelection: () => paymentsUI?.clearOverview(), onPayment: payment => paymentsUI?.acceptDetails(payment), otherBusy: () => paymentsUI?.mutationBusy() ?? false });
investigationUI = mountInvestigation({ blocked:()=>Boolean(portalUI?.chatBusy()||paymentChatUI?.busy()), onBusy: () => { detailsUI.render(); paymentsUI?.refreshLocks(); } });
paymentsUI = mountPayments(detailsUI);
paymentChatUI=mountPaymentAI({onBusy:()=>{detailsUI.render();paymentsUI?.refreshLocks();},locked:()=>Boolean(detailsUI.locked()||paymentsUI?.investigationBlocked()||investigationUI?.busy()||portalUI?.chatBusy())});
detailsUI.render();
portalUI = mountPortals({ onPaymentContextEnter:()=>{paymentChatUI.enter();detailsUI.render();}, onPaymentContextLeave:()=>paymentChatUI.leave(), onChatBusy:()=>{detailsUI.render();paymentsUI?.refreshLocks();}, workspace, payments: paymentsUI, details: detailsUI, clearLogin: () => { $('login-form').reset(); $('login').setCustomValidity(''); hidePassword(); } });
accountSwitcher=createAccountSwitcher({locked:()=>Boolean(portalUI.switchBlocked()||investigationUI?.busy()),navigate:path=>{portalUI.navigate(path);$('login').focus();},onChange:state=>{
  switchState=state;$('account-switch').disabled=state.busy;
  $('login-submit').disabled=state.busy||state.uncertain;$('login').disabled=state.busy||state.uncertain;$('password').disabled=state.busy||state.uncertain;
  $('logout-feedback').textContent=state.message;$('finish-logout').hidden=!state.uncertain;if(state.uncertain)$('finish-logout').focus();
}});
$('account-switch').addEventListener('click',()=>void accountSwitcher.switchAccount());
$('account-signout').addEventListener('click',()=>$('logout').click());
$('account-menu').addEventListener('keydown',event=>{if(event.key==='Escape'){$('account-menu').open=false;$('account-menu').querySelector('summary').focus();}});
$('account-profile').addEventListener('click',()=>{const role=getSession()?.roles.includes('ADMIN')?'admin':'merchant';$('account-menu').open=false;portalUI.navigate('/'+role+'/profile');});
$('account-security').addEventListener('click',()=>{const role=getSession()?.roles.includes('ADMIN')?'admin':'merchant';$('account-menu').open=false;portalUI.navigate('/'+role+(role==='admin'?'/profile':'/security'));});
subscribe(session=>{
  $('account-menu').hidden=!session;$('account-menu').open=false;
  $('account-menu-identity').textContent=session?`${session.identity==='Restored session'?'Restored account (open menu to load login)':session.identity} · ${session.roles.join(' + ')}`:'';
  $('account-profile').textContent=session?.roles.includes('ADMIN')?'Admin Profile':'Business Profile';
  $('account-profile').disabled=$('account-security').disabled=session?.accountStatus!=='ACTIVE';
});
$('account-menu').addEventListener('toggle',async()=>{
  if(!$('account-menu').open||!getSession())return;const version=getVersion(),session=getSession();
  if(session.accountStatus!=='ACTIVE'||session.identity!=='Restored session')return;
  try{const own=await request(session.roles.includes('ADMIN')?'/admin/profile':'/merchant/profile');if(version===getVersion()&&getSession()&&typeof own.login==='string')$('account-menu-identity').textContent=own.login+' · '+getSession().roles.join(' + ');}catch{if(version===getVersion()&&getSession())$('account-menu-identity').textContent='Login unavailable; open your authorized profile · '+getSession().roles.join(' + ');}
});
installLifecycle();
workspace.start();
setInterval(()=>{const session=getSession();if(session)$('expiry').textContent=`Access expires at ${new Date(session.expires).toLocaleString()}. Server session refresh uses an HttpOnly cookie.`;},30000);
