import { request } from './api/client.js';
import { createRegistration, REGISTRATION_SUCCESS } from './portals/registration.js';
import { validateSignup } from './portals/signup.js';
import { validateLogin, setSession, getSession, clearSession, checkExpiry } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
import { resolveRoute } from './portals/router.js';
const original=window.fetch, clock=Date.now, results=[];
const assert=(ok,label)=>{if(!ok)throw new Error(label);results.push(label);};
const input=()=>({firstName:'Ada',lastName:'Example',businessName:'Synthetic Business',email:'Merchant@Example.Test',mobile:'+919876543210',businessType:'COMPANY',country:'IN',password:'synthetic-passphrase',confirmPassword:'synthetic-passphrase',terms:true});
function pendingToken() {
 const token=tokenResponse(); const parts=token.accessToken.split('.');
 const claims=JSON.parse(atob(parts[1].replace(/-/g,'+').replace(/_/g,'/')));claims.account_status='PENDING_APPROVAL';
 parts[1]=btoa(JSON.stringify(claims)).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_'); token.accessToken=parts.join('.');return token;
}
try {
 clearSession();let state={},calls=0,finish;
 const model=createRegistration(next=>Object.assign(state,next));
 assert(!Object.keys(validateSignup(input())).length,'valid registration input');
 for(const value of ['short','x'.repeat(73),'é'.repeat(37),'abcdefghijkl\0']) assert(validateSignup({...input(),password:value}).password,'invalid password policy');
 assert(!validateSignup({...input(),password:'é'.repeat(12)}).password,'UTF-8 passphrase accepted');
 window.fetch=async(url,options)=>{
  calls++;assert(url==='/api/v1/auth/register','exact registration endpoint');assert(options.method==='POST','POST registration');
  const body=JSON.parse(options.body);assert(body.email==='merchant@example.test','normalized email');
  assert(body.confirmPassword===body.password,'confirmation supplied');assert(!body.role&&!body.merchantId,'no client privileges');
  assert(!options.headers.Authorization,'public registration no bearer');assert(!options.headers['Idempotency-Key'],'no invented idempotency');
  return new Response(JSON.stringify({accountStatus:'PENDING_APPROVAL',message:REGISTRATION_SUCCESS}),{status:201});
 };
 const first=input();await model.submit(first);
 assert(state.success&&state.message===REGISTRATION_SUCCESS,'exact success and sign-in availability');assert(!first.password&&!first.confirmPassword,'password references cleared');assert(!getSession(),'no automatic sign-in');
 window.fetch=()=>{calls++;return new Promise(resolve=>finish=resolve);};
 const action=model.submit(input());assert(state.busy,'visible pending state');const before=calls;await model.submit(input());assert(calls===before,'duplicate prevented');
 finish(new Response('{}',{status:409}));await action;assert(!state.busy&&state.message.includes('signing in'),'duplicate-email safe feedback');
 for(const status of [400,429,413,503,502,504]) {
  window.fetch=async()=>new Response('{}',{status});await model.submit(input());assert(!state.success&&!state.busy,'safe failure '+status);
 }
 window.fetch=async()=>new Response('{}',{status:201});await model.submit(input());assert(!state.success&&state.message.includes('not be confirmed'),'malformed success uncertain');
 window.fetch=async()=>{throw new TypeError('private backend detail');};await model.submit(input());assert(!state.message.includes('private'),'no raw network detail');
 window.fetch=()=>new Promise(resolve=>finish=resolve);const late=model.submit(input());model.reset();finish(new Response(JSON.stringify({accountStatus:'PENDING_APPROVAL',message:REGISTRATION_SUCCESS}),{status:201}));await late;assert(!state.success,'route cancellation ignores response');
 const token=pendingToken();assert(validateLogin(token).accountStatus==='PENDING_APPROVAL','pending JWT validated');setSession(token,'synthetic@example.test');
 assert(getSession().accountStatus==='PENDING_APPROVAL','pending session retained');
 let financialCalls=0; window.fetch=async()=>{financialCalls++;return new Response('{}');};
 for(const [path,method] of [['/payments','POST'],['/payments/12345678-1234-1234-1234-123456789abc','GET'],['/payments/12345678-1234-1234-1234-123456789abc/investigate','POST']]) { let denied=false; try {await request(path,{method});}catch(error){denied=error.status===403;} assert(denied,'pending client financial guard'); }
 assert(financialCalls===0,'pending operations never fetched');assert(resolveRoute('/merchant/login',getSession()).path==='/merchant/dashboard','pending signs in to onboarding');
 assert(resolveRoute('/admin/dashboard',getSession()).denied,'pending cannot admin');clearSession();assert(!getSession(),'logout clears pending');
 setSession(token);Date.now=()=>clock()+901000;checkExpiry();Date.now=clock;assert(!getSession(),'pending expiry');
 window.fetch=()=>new Promise(resolve=>finish=resolve);const stale=model.submit(input());setSession(tokenResponse());finish(new Response(JSON.stringify({accountStatus:'PENDING_APPROVAL',message:REGISTRATION_SUCCESS}),{status:201}));await stale;assert(!state.success,'replacement session ignores response');
 document.querySelector('#result').textContent=`PASS: ${results.length} assertions\n${results.join('\n')}`;
} catch(error){document.querySelector('#result').textContent=`FAIL: ${error.message}`;}
finally {window.fetch=original;Date.now=clock;clearSession();}
