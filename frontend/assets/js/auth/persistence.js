import { API, validateRoute } from '../api/config.js';
import { clearSession, getSession, getVersion, setSession, renewSession, subscribe } from './session.js';
let active=false, flight=null, epoch=0, timer, stopped=false, channel=null;
export function authLock(work) {
  return active && globalThis.navigator?.locks ? navigator.locks.request('paymesh-auth-cookie',work) : work();
}
export async function authPost(path) {
  if(!['/refresh','/logout','/logout-all'].includes(path)||!validateRoute('POST','/auth'+path))throw new Error('Unsupported authentication route');
  const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),API.timeoutMs);
  try {
    const response=await fetch(API.base+'/auth'+path,{method:'POST',headers:{Accept:'application/json','X-PayMesh-CSRF':'1'},credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal});
    let body;try{body=await response.json();}catch{throw new Error('Authentication response unavailable');}
    if(!response.ok)throw new Error('Authentication unavailable');return body;
  } finally {clearTimeout(timeout);}
}
export async function discardStaleLogin(){if(active)try{await authPost('/logout');}catch{/* No credentials or raw errors are rendered. */}}
export async function rejectPortalLogin(){if(active)await authLock(discardStaleLogin);}
export function refreshSession({restore=false}={}) {
  if(flight)return flight;if(!active||stopped||(globalThis.navigator&&!navigator.locks))return Promise.resolve(false);
  const current=epoch,version=getVersion(),before=getSession();
  flight=authLock(async()=>{
    if(current!==epoch||version!==getVersion()||stopped)return false;
    try{
      const data=await authPost('/refresh');
      if(current!==epoch||version!==getVersion()||stopped)return false;
      if(before)renewSession(data);else if(restore)setSession(data,'Restored session');else return false;
      schedule();return true;
    }catch{
      if(current===epoch&&version===getVersion())clearSession('refresh-failed');return false;
    }
  }).finally(()=>{flight=null;});return flight;
}
function schedule(){clearTimeout(timer);const session=getSession();if(active&&session?.sessionId&&!stopped)timer=setTimeout(()=>void refreshSession(),Math.max(1000,session.expires-Date.now()-60000));}
export async function signOut(all=false) {
  if(!active){clearSession();return true;}
  stopped=true;epoch++;clearTimeout(timer);clearSession('logout');channel?.postMessage({type:'logout'});
  try{await authLock(()=>authPost(all?'/logout-all':'/logout'));return true;}catch{return false;}
}
export function installPersistence(target=window) {
  active=true;stopped=false;
  if(typeof BroadcastChannel!=='undefined'){channel=new BroadcastChannel('paymesh-auth-lifecycle');channel.onmessage=event=>{const data=event.data;if(data?.type==='replace'&&data.sessionId&&data.sessionId===getSession()?.sessionId)return;if(['logout','replace'].includes(data?.type)){stopped=true;epoch++;clearTimeout(timer);clearSession('session-replaced');}};}
  const unsubscribe=subscribe((session,reason)=>{
    if(reason==='login'){stopped=false;epoch++;schedule();channel?.postMessage({type:'replace',sessionId:session?.sessionId});}
    else if(!session){epoch++;clearTimeout(timer);if(['logout','unauthorized','refresh-failed','password-reset','session-replaced'].includes(reason))stopped=true;}
  });
  const focus=()=>{const session=getSession();if(session&&session.expires-Date.now()<90000)void refreshSession();else if(!session&&!stopped)void refreshSession({restore:true});};
  target.addEventListener('focus',focus);
  return {restore:()=>refreshSession({restore:true}),dispose(){channel?.close();channel=null;active=false;epoch++;clearTimeout(timer);unsubscribe();target.removeEventListener('focus',focus);}};
}
