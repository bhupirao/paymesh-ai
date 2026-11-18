import { signOut } from './persistence.js';
import { getSession,getVersion,subscribe,clearSession } from './session.js';
export const SWITCH_CONFIRMATION='Switch account? This signs out the current account across tabs in this browser profile. Unfinished private recovery state will be cleared. Continue?';
export function createAccountSwitcher({logout=signOut,locked=()=>false,confirm=message=>window.confirm(message),navigate=()=>{},onChange=()=>{}}={}){
  let state={busy:false,uncertain:false,message:''},seq=0,loginPath='/merchant/login';
  const emit=()=>onChange({...state});const off=subscribe((session,reason)=>{if(session||reason==='session-replaced'){seq++;state={busy:false,uncertain:false,message:session?'':'Session changed in another tab; private sign-in state was cleared.'};emit();}});
  async function perform(retry=false){
    if(state.busy)return false;
    if(locked()){state.message='Finish or safely resolve the pending payment, refund or AI operation before switching accounts.';emit();return false;}
    if(!retry&&!confirm(SWITCH_CONFIRMATION))return false;
    if(!retry)loginPath=getSession()?.roles.includes('ADMIN')?'/admin/login':'/merchant/login';const operation=++seq;state={busy:true,uncertain:false,message:'Signing out this browser session across tabs…'};emit();
    // Existing signOut synchronously stops refresh, clears private state and broadcasts logout.
    let work;try{work=logout();}catch{work=Promise.resolve(false);}const version=getVersion();let ok=false;
    try{ok=await work;}catch{ok=false;}
    if(operation!==seq||version!==getVersion())return false;
    if(getSession()){clearSession('logout');ok=false;}
    state={busy:false,uncertain:!ok,message:ok?'Signed out. Choose an account to sign in.':'Local private state was cleared, but server logout and cookie clearing are unconfirmed. Finish sign out before switching accounts. Do not refresh or share this browser until logout is confirmed.'};emit();
    if(ok)navigate(loginPath);return ok;
  }
  return {switchAccount:()=>perform(false),retry:()=>perform(true),state:()=>({...state}),dispose:off};
}
