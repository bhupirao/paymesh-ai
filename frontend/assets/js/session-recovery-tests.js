import { request } from './api/client.js';
import { createRecovery } from './auth/recovery.js';
import { installPersistence,refreshSession,signOut } from './auth/persistence.js';
import { setSession,getSession,getVersion,clearSession,renewSession } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
import { createWorkspace } from './features/workspace.js';
import { resolveRoute } from './portals/router.js';
const original=window.fetch,clock=Date.now,results=[];let tokenSequence=0;let manager;const originalBroadcast=globalThis.BroadcastChannel;let testChannel;
const assert=(value,label)=>{if(!value)throw new Error(label);results.push(label);};
function sessionToken(role='MERCHANT',sid='12345678-1234-1234-1234-123456789abc'){
 const token=tokenResponse([role]);const parts=token.accessToken.split('.');const claims=JSON.parse(atob(parts[1].replace(/-/g,'+').replace(/_/g,'/')));claims.sid=sid;claims.jti=String(++tokenSequence);parts[1]=btoa(JSON.stringify(claims)).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');token.accessToken=parts.join('.');return token;
}
try{
 clearSession();let calls=0,finish,started;
 globalThis.BroadcastChannel=class {constructor(){testChannel=this;}postMessage(){}close(){}};
 const loginWorkspace=createWorkspace(()=>{});
 for(const [role,remember] of [['MERCHANT',true],['ADMIN',false]]){
  window.fetch=async(url,opts)=>{assert(url==='/api/v1/auth/login','shared portal login endpoint');assert(JSON.parse(opts.body).rememberMe===remember,'Remember Me value for '+role);return new Response(JSON.stringify(tokenResponse([role])));};
  await loginWorkspace.login('synthetic-account','synthetic-test-password',role,remember);assert(getSession()?.roles.includes(role),'remember login accepted only actual '+role);
 }
 loginWorkspace.dispose();clearSession();
 assert(resolveRoute('/merchant/forgot-password',null).role==='MERCHANT','Merchant forgot route');assert(resolveRoute('/admin/forgot-password',null).role==='ADMIN','Admin forgot route');
 manager=installPersistence();
 window.fetch=async(url,opts)=>{calls++;assert(url==='/api/v1/auth/refresh','exact refresh route');assert(opts.credentials==='same-origin','refresh cookie credentials');assert(opts.headers['X-PayMesh-CSRF']==='1','CSRF header');assert(!opts.body&&!opts.headers.Authorization,'no bearer/body for refresh');return new Response(JSON.stringify(sessionToken()));};
 assert(await manager.restore(),'startup restores session');assert(getSession()?.sessionId,'restored session has identifier');
 const sameFamilyVersion=getVersion();testChannel.onmessage({data:{type:'replace',sessionId:getSession().sessionId}});assert(getVersion()===sameFamilyVersion,'same-family tab restoration preserves private operations');
 testChannel.onmessage({data:{type:'replace',sessionId:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}});assert(!getSession(),'other-family tab replacement clears private session');setSession(sessionToken());
 const version=getVersion();renewSession(sessionToken());assert(getVersion()===version,'rotation preserves private operation version');
 const begun=new Promise(r=>started=r);window.fetch=()=>{calls++;started();return new Promise(r=>finish=r);};const a=refreshSession(),b=refreshSession();await begun;const previous=calls;finish(new Response(JSON.stringify(sessionToken())));assert(await a&&await b,'single flight callers share success');assert(calls===previous,'single flight uses one request');
 const originalToken=getSession();let rejected=false;try{renewSession(sessionToken('ADMIN'));}catch{rejected=true;}assert(rejected&&getSession().subject===originalToken.subject,'replacement claims rejected on renewal');
 window.fetch=()=>new Promise(r=>finish=r);const oldRequest=request('/payments/health');renewSession(sessionToken());finish(new Response('{}',{status:401}));try{await oldRequest;}catch(error){assert(error.status===401,'old access request denied');}assert(getSession(),'late old-token 401 does not clear renewed same-family session');
 window.fetch=async()=>new Response('{}',{status:401});assert(!(await refreshSession()),'refresh failure');assert(!getSession(),'failed refresh clears session');
 setSession(sessionToken());window.fetch=async(url)=>{assert(url==='/api/v1/auth/logout-all','logout all endpoint');return new Response('{}');};assert(await signOut(true),'logout all completes');assert(!getSession(),'logout all clears local state');
 manager.dispose();manager=installPersistence();const restoring=new Promise(r=>started=r);window.fetch=()=>{started();return new Promise(r=>finish=r);};const late=manager.restore();await restoring;clearSession();finish(new Response(JSON.stringify(sessionToken())));assert(!(await late)&&!getSession(),'late restore cannot replace cleared session');manager.dispose();manager=null;
 let state,now=Date.now(),recoveryCalls=0;const id='12345678-1234-1234-1234-123456789abc';let enabled=true;
 const recovery=createRecovery(s=>state=s,{now:()=>now,fetcher:async(url,opts)=>{recoveryCalls++;if(url.endsWith('capabilities'))return new Response(JSON.stringify({localDemoEnabled:enabled}));assert(opts.credentials==='omit','recovery never sends auth cookie');assert(opts.headers['X-PayMesh-CSRF']==='1','recovery CSRF');const body=JSON.parse(opts.body);assert(body.portal==='MERCHANT'||body.portal==='ADMIN','explicit portal binding');if(url.endsWith('forgot'))return new Response(JSON.stringify({challengeId:id,otp:'712345',expiresAt:new Date(now+300000).toISOString(),resendAfterSeconds:60}));if(url.endsWith('verify-otp')){assert(body.otp==='712345','manually entered runtime code sent');return new Response(JSON.stringify({resetAuthorization:'z'.repeat(43),expiresIn:300}));}assert(body.password===body.confirmPassword,'confirmation request');return new Response(JSON.stringify({message:'Password reset successful.'}));}});
 enabled=false;await recovery.open('MERCHANT');assert(state.step==='disabled'&&!state.otp,'disabled recovery has no OTP UI state');enabled=true;
 await recovery.open('MERCHANT');assert(state.step==='identify','enabled identify state');const before=recoveryCalls;assert(!state.otp&&recoveryCalls===before,'opening does not generate OTP');
 await recovery.generate('demo@example.test');assert(state.step==='otp'&&state.otp==='712345','runtime OTP displayed');assert(!state.authorization,'OTP not auto verified');
 const beforeResend=recoveryCalls;await recovery.resend();assert(recoveryCalls===beforeResend,'resend cooldown');
 await recovery.verify('');assert(state.step==='otp'&&state.message.includes('manually'),'manual entry required');
 now+=61000;await recovery.resend();assert(state.step==='otp','resend after cooldown');
 await recovery.verify('712345');assert(state.step==='password'&&!state.otp&&state.authorization,'verification consumes visible OTP state');
 const beforeInvalid=recoveryCalls;await recovery.reset('short','short');assert(recoveryCalls===beforeInvalid,'weak password blocked');await recovery.reset('valid-test-password','different-password');assert(recoveryCalls===beforeInvalid,'mismatch blocked');
 await recovery.reset('valid-test-password','valid-test-password');assert(state.step==='success'&&!state.authorization&&!state.challengeId&&!state.otp,'success clears secrets');assert(!getSession(),'reset never signs in automatically');
 await recovery.open('ADMIN');await recovery.generate('demo-admin');assert(state.portal==='ADMIN','Admin recovery flow');now+=300001;recovery.tick();assert(state.step==='identify'&&!state.otp&&!state.challengeId,'countdown expiry clears sensitive state');
 await recovery.generate('demo-admin');recovery.clear();assert(!state.otp&&!state.challengeId&&!state.authorization,'navigation clears state');
 const bad=createRecovery(s=>state=s,{fetcher:async(url)=>url.endsWith('capabilities')?new Response('{"localDemoEnabled":true}'):new Response('{}',{status:400})});await bad.open('MERCHANT');await bad.generate('anything');assert(state.step==='identify'&&!state.challengeId,'invalid recovery safe terminal state');
 const invalidOtp=createRecovery(s=>state=s,{now:()=>now,fetcher:async(url)=>url.endsWith('capabilities')?new Response('{"localDemoEnabled":true}'):url.endsWith('forgot')?new Response(JSON.stringify({challengeId:id,otp:'712345',expiresAt:new Date(now+300000).toISOString(),resendAfterSeconds:60})):new Response('{}',{status:400})});await invalidOtp.open('MERCHANT');await invalidOtp.generate('synthetic@example.test');await invalidOtp.verify('111111');assert(state.step==='identify'&&!state.otp&&!state.challengeId,'invalid or expired server OTP clears challenge and displayed code');
 let resolve;const stale=createRecovery(s=>state=s,{fetcher:()=>new Promise(r=>resolve=r)});const opening=stale.open('MERCHANT');stale.clear();resolve(new Response('{"localDemoEnabled":true}'));await opening;assert(state.step==='disabled','late recovery response ignored');
 document.querySelector('#result').textContent=`PASS: ${results.length} assertions\n${results.join('\n')}`;
}catch(e){document.querySelector('#result').textContent=`FAIL: ${e.message}`;}
finally{manager?.dispose();globalThis.BroadcastChannel=originalBroadcast;window.fetch=original;Date.now=clock;clearSession();}
