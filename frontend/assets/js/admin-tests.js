import { ADMIN_PAGES, adminRoute } from './admin/routes.js';
import { createAdminWorkspace,transitions,query,validatePage,adminFeedback } from './admin/model.js';
import { element,pairs } from './admin/view.js';
import { resolveRoute } from './portals/router.js';
import { request } from './api/client.js';
import { setSession,clearSession,getSession } from './auth/session.js';
import { tokenResponse,paymentId } from './test-fixtures.js';
const results=[];const assert=(value,label)=>{if(!value)throw new Error(label);results.push(label);};
const original=window.fetch;let model,state;
const page={items:[],page:0,size:25,total:0};
const merchant={merchantId:'SYNTHETIC_MERCHANT',status:'PENDING_APPROVAL',registrationUserId:paymentId,businessName:'<img src=x onerror=alert(1)>'};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
try{
  for(const path of Object.keys(ADMIN_PAGES)){
    assert(resolveRoute(path,null).path==='/admin/login','unauthenticated route guarded '+path);
    assert(resolveRoute(path,{roles:['MERCHANT']}).path==='/admin/login','Merchant route denied '+path);
    assert(resolveRoute(path,{roles:['ADMIN']}).page==='dashboard','Admin route supported '+path);
  }
  for(const path of ['/admin/dashboard','/admin/merchants?page=0&size=25','/admin/merchant?merchantId=DEMO_MERCHANT_A','/admin/payments/'+paymentId,'/admin/refunds/'+paymentId,'/admin/accounts','/admin/profile','/admin/audit?search=MERCHANT_APPROVE'])assert(adminRoute('GET',path),'exact GET '+path);
  for(const path of ['/admin/profile/password','/admin/accounts','/admin/merchant/approve','/admin/merchant/reject','/admin/merchant/suspend','/admin/merchant/reactivate'])assert(adminRoute('POST',path),'exact POST '+path);
  for(const path of ['/admin/settlement','/admin/merchant?url=http://evil','/admin/payments?sort=sql','/admin/payments?page=1&page=2','/admin/payments?size=101','/admin/payments?merchantId=%0A','/admin/profile?token=bad'])assert(!adminRoute('GET',path),'unsupported route/query denied '+path);
  assert(!adminRoute('POST','/admin/merchant/approve?role=ADMIN'),'mutation query denied');
  assert(query({search:'a+b&c',page:0}).includes('search=a%2Bb%26c'),'search encoded safely');
  let malformed=false;try{validatePage({items:[],page:0,size:101,total:1});}catch{malformed=true;}assert(malformed,'malformed page rejected');
  assert(transitions.REJECTED.length===0&&!transitions.PENDING_APPROVAL.includes('reactivate'),'lifecycle UI matrix guards');
  setSession(tokenResponse(['ADMIN']),'synthetic-admin');
  let calls=[];let pending;
  const api=async(path,options)=>{calls.push({path,options});if(pending)return pending.promise;if(path.startsWith('/admin/merchant?'))return {...merchant};if(options?.method==='POST')return {merchantId:merchant.merchantId,status:'ACTIVE'};return page;};
  model=createAdminWorkspace(s=>state=s,{api});
  await model.load('pending');assert(calls.at(-1).path.includes('status=PENDING_APPROVAL'),'pending filter exact');assert(state.data.items.length===0,'empty list state');
  await model.load('merchant',{merchantId:merchant.merchantId});const count=calls.length;
  assert(!model.review('approve',{ownershipAttested:false,reviewReference:'REVIEW'}),'attestation mandatory');
  assert(!model.review('reject',{reason:' '}),'reason mandatory');
  assert(model.review('approve',{ownershipAttested:true,reviewReference:'ISOLATED-REVIEW'}),'valid explicit review');
  assert(calls.length===count,'review does not submit');assert(Object.isFrozen(state.intent.body),'review body frozen');
  pending=deferred();const first=model.confirm();await Promise.resolve();const currentCalls=calls.length;await model.confirm();assert(calls.length===currentCalls,'duplicate confirmation prevented');
  assert(calls.at(-1).path==='/admin/merchant/approve'&&calls.at(-1).options.method==='POST','exact approval API request');
  pending.resolve({merchantId:merchant.merchantId,status:'ACTIVE'});pending=null;await first;
  assert(!state.data&&!state.intent&&state.message.includes('Refresh'),'success requires explicit refresh');
  await model.load('merchant',{merchantId:merchant.merchantId});
  model.dispose();
  let attempts=0;model=createAdminWorkspace(s=>state=s,{api:async(path,options)=>{if(options){attempts++;throw {status:503};}return {...merchant};}});
  await model.load('merchant',{merchantId:merchant.merchantId});model.review('reject',{reason:'Synthetic review rejection'});await model.confirm();
  assert(state.uncertain&&attempts===1,'uncertain action retained without retry');
  assert(!model.review('reject',{reason:'New attempt'}),'uncertainty blocks another mutation');await model.confirm();assert(attempts===1,'no automatic uncertain retry');
  await model.refresh();assert(!state.uncertain,'fresh same-Merchant detail resolves uncertainty');model.dispose();
  model=createAdminWorkspace(s=>state=s,{api,financialLocked:()=>true});await model.load('merchant',{merchantId:merchant.merchantId});assert(!model.review('approve',{ownershipAttested:true,reviewReference:'REVIEW'}),'financial operation lock preserved');model.dispose();
  pending=deferred();model=createAdminWorkspace(s=>state=s,{api:()=>pending.promise});const late=model.load('merchants');clearSession();pending.resolve(page);pending=null;await late;assert(!state.data&&!state.pending,'logout clears state and late response');model.dispose();
  setSession(tokenResponse(['ADMIN']));pending=deferred();model=createAdminWorkspace(s=>state=s,{api:()=>pending.promise});const replaced=model.load('payments');clearSession();setSession(tokenResponse(['ADMIN']));pending.resolve(page);pending=null;await replaced;assert(!state.data,'replacement session blocks stale response');model.dispose();
  let passwordCalls=0;model=createAdminWorkspace(s=>state=s,{api:async()=>{passwordCalls++;return {message:'changed'};}});
  assert(!await model.changePassword('current-test-password','short','short'),'password policy guards');assert(!await model.changePassword('current-test-password','valid-new-test-password','different-test-password'),'confirmation guards');assert(passwordCalls===0,'invalid password never submitted');
  assert(await model.changePassword('current-test-password','valid-new-test-password','valid-new-test-password'),'password change supported');assert(!getSession(),'password change clears authenticated UI');model.dispose();
  for(const code of [400,401,403,404,409,413,429,502,503,504])assert(typeof adminFeedback({status:code})==='string'&&!adminFeedback({status:code}).includes('undefined'),'safe error '+code);
  const fixture=document.getElementById('fixture');pairs(fixture,{businessName:'<script>bad()</script>'});assert(fixture.textContent.includes('<script>bad()</script>'),'safe text rendering');assert(fixture.querySelectorAll('script').length===0,'no untrusted HTML inserted');
  setSession(tokenResponse(['ADMIN']));window.fetch=async(url,options)=>{assert(url.startsWith('/api/v1/admin/'),'same-origin Admin endpoint');assert(options.headers.Authorization?.startsWith('Bearer '),'JWT forwarded');assert(options.credentials==='omit','Admin requests omit cookies');assert(!options.headers['Idempotency-Key'],'no invented idempotency header');return new Response(JSON.stringify(page));};await request('/admin/payments?page=0&size=25');
  setSession(tokenResponse(['MERCHANT']));let denied=false;try{await request('/admin/merchants');}catch(e){denied=e.status===403;}assert(denied,'client role gate supplements Java');
  setSession(tokenResponse(['ADMIN']));
  const endpoints=[];model=createAdminWorkspace(s=>state=s,{api:async(path)=>{endpoints.push(path);if(path.startsWith('/admin/merchant?'))return {...merchant};if(path==='/admin/profile')return {login:'synthetic-admin',roles:['ADMIN']};if(path.startsWith('/admin/dashboard'))return {totalMerchants:0,pendingRegistrations:0,merchantCounts:[],paymentCounts:[],refundCounts:[],paymentAmounts:[],refundAmounts:[],recentRegistrations:[],recentPayments:[]};return page;}});
  for(const view of ['dashboard','merchants','pending','payments','refunds','audit','accounts','profile']){await model.load(view);assert(state.view===view&&state.data&&!state.busy,'screen loaded '+view);}
  await model.load('payments',{merchantId:'M A',currency:'USD',from:'2026-11-01T00:00:00Z',to:'2026-11-02T00:00:00Z'},1);
  const filterParams=new URLSearchParams(endpoints.at(-1).split('?')[1]);assert(filterParams.get('page')==='1'&&filterParams.get('merchantId')==='M A'&&filterParams.get('currency')==='USD','pagination/filter query preserves exact intent');model.dispose();
  let created=0;model=createAdminWorkspace(s=>state=s,{api:async(path,options)=>{created++;assert(path==='/admin/accounts'&&options.method==='POST','existing Admin creation reused');assert(!('role' in options.body)&&!('actor' in options.body),'no client authority supplied');return {userId:paymentId,login:'new-admin',enabled:true,accountStatus:'ACTIVE',roles:['ADMIN']};}});
  assert(!await model.createAccount('new-admin','valid-test-password','valid-test-password',false)&&created===0,'Admin creation requires confirmation');
  assert(!await model.createAccount('new-admin','valid-test-password','different-password',true)&&created===0,'Admin creation confirms password');
  assert(await model.createAccount('new-admin','valid-test-password','valid-test-password',true)&&created===1,'Admin creation succeeds once');model.dispose();
  for(const status of [400,403,404,409,503]){model=createAdminWorkspace(s=>state=s,{api:async()=>{throw {status};}});await model.load('merchants');assert(!state.data&&!state.busy&&state.message,'list error state '+status);model.dispose();}
  pending=deferred();model=createAdminWorkspace(s=>state=s,{api:()=>pending.promise});const expiring=model.load('audit');clearSession('expired');pending.resolve(page);pending=null;await expiring;assert(!state.data&&!state.view,'expiry clears Admin state and ignores response');model.dispose();
  setSession(tokenResponse(['ADMIN']));window.fetch=async()=>new Response('{}',{status:403});try{await request('/admin/profile');}catch{}assert(Boolean(getSession()),'Admin 403 retains session');
  window.fetch=async()=>new Response('{}',{status:401});try{await request('/admin/profile');}catch{}assert(!getSession(),'Admin 401 clears private session');
  document.getElementById('summary').textContent=`${results.length} Admin assertions passed (mocked fetch).`;
  document.getElementById('results').replaceChildren(...results.map(label=>element('li',label)));
}catch(error){document.getElementById('summary').textContent='FAILED: '+error.message;throw error;}
finally{model?.dispose();clearSession();window.fetch=original;}
