import { createRecovery } from './recovery.js';
import { subscribe, getSession, clearSession } from './session.js';
export function mountRecovery(){
 const $=id=>document.getElementById(id);let current=null,previousStep=null,completing=false;
 const model=createRecovery(state=>{
  if(state.step==='success'&&getSession())queueMicrotask(()=>{completing=true;clearSession('password-reset');completing=false;});
  $('recovery-restart').hidden=state.step==='disabled';$('recovery-restart').disabled=state.busy;
  $('recovery-form').setAttribute('aria-busy',String(state.busy));
  for(const id of ['recovery-generate','recovery-verify','recovery-reset','recovery-identity','recovery-otp','recovery-password','recovery-confirm','recovery-toggle'])$(id).disabled=state.busy;
  for(const step of ['disabled','identify','otp','password','success'])$('recovery-'+step+'-panel').hidden=state.step!==step;
  $('recovery-code').textContent=state.otp||'';$('recovery-feedback').textContent=state.message||'';
  $('recovery-countdown').textContent=state.expires?`${Math.max(0,Math.ceil((state.expires-Date.now())/1000))} seconds remaining`:'';
  $('recovery-resend').disabled=state.busy||Date.now()<(state.resendAt||Infinity);
  $('recovery-resend').textContent=Date.now()<(state.resendAt||0)?`Resend in ${Math.max(0,Math.ceil((state.resendAt-Date.now())/1000))}s`:'Resend OTP';
  if(!['otp','password'].includes(state.step)){for(const id of ['recovery-otp','recovery-password','recovery-confirm'])$(id).value='';}
  if(state.step!==previousStep){previousStep=state.step;const focus={identify:'recovery-identity',otp:'recovery-otp',password:'recovery-password',success:'recovery-login'}[state.step];if(focus)queueMicrotask(()=>$(focus).focus());}
  if(state.step!=='identify'&&state.step!=='otp')$('recovery-identity').value='';
 });
 function clear(){model.clear();$('recovery-form').reset();for(const id of ['recovery-identity','recovery-otp','recovery-password','recovery-confirm'])$(id).value='';$('recovery-password').type=$('recovery-confirm').type='password';$('recovery-toggle').setAttribute('aria-pressed','false');$('recovery-toggle').textContent='Show passwords';}
 subscribe(()=>{if(!completing)clear();});
 $('recovery-restart').addEventListener('click',()=>{const portal=model.state().portal;clear();if(portal)void model.open(portal);});
 $('recovery-form').addEventListener('submit',e=>e.preventDefault());
 $('recovery-generate').addEventListener('click',()=>{const value=$('recovery-identity').value.trim();if(value)void model.generate(value);else $('recovery-identity').focus();});
 $('recovery-verify').addEventListener('click',()=>{void model.verify($('recovery-otp').value);$('recovery-otp').value='';});
 $('recovery-resend').addEventListener('click',()=>{void model.resend();$('recovery-otp').value='';});
 $('recovery-reset').addEventListener('click',()=>{void model.reset($('recovery-password').value,$('recovery-confirm').value);$('recovery-password').value=$('recovery-confirm').value='';});
 $('recovery-toggle').addEventListener('click',()=>{const show=$('recovery-password').type==='password';$('recovery-password').type=$('recovery-confirm').type=show?'text':'password';$('recovery-toggle').setAttribute('aria-pressed',String(show));$('recovery-toggle').textContent=show?'Hide passwords':'Show passwords';});
 setInterval(()=>model.tick(),1000);
 return {observe(route){const path=route.page==='forgot'?route.path:null;if(path===current)return;clear();current=path;if(path){const portal=route.role;$('recovery-title').textContent=portal==='ADMIN'?'Admin password recovery':'Merchant password recovery';$('recovery-identity-label').textContent=portal==='ADMIN'?'Admin username':'Registered email';$('recovery-login').href=portal==='ADMIN'?'/admin/login':'/merchant/login';void model.open(portal);}}};
}
