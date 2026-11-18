import { createMerchantChat,chatFeedback } from './merchant-ai/model.js';
import { boundedHistory,makeRequest,validateChat,validateQuestion,generationLabel } from './merchant-ai/schema.js';
import { mountMerchantAI,renderAnswer } from './merchant-ai/view.js';
import { MERCHANT_PAGES,merchantRoute } from './merchant/routes.js';
import { resolveRoute } from './portals/router.js';
import { request } from './api/client.js';
import { API } from './api/config.js';
import { getSession,setSession,clearSession } from './auth/session.js';
import { tokenResponse,paymentId } from './test-fixtures.js';
import { publicChatFixture,knownChatReference } from './merchant-ai-test-fixtures.js';
const results=[],assert=(v,s)=>{if(!v)throw new Error(s);results.push(s);};
const clone=v=>structuredClone(v),response=()=>clone(publicChatFixture),selected={paymentId,amount:'100.00',currency:'INR',status:'SUCCESS'};
const profile={merchantId:'SYNTHETIC_MERCHANT',accountStatus:'ACTIVE',businessStatus:'ACTIVE',merchantVerified:true,merchantActive:true,membershipActive:true,registrationAvailable:false};
const page={items:[{...selected,createdAt:'2026-11-15T00:00:00Z',customerId:'synthetic'}],page:0,size:5,total:6};
const deferred=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve:v=>resolve(v)};};
let state,calls=[],pending=null,failure=null,locked=false,busyEvents=[];
const api=async(path,options)=>{calls.push({path,options});if(path==='/merchant/profile')return clone(profile);if(path.startsWith('/merchant/payments'))return clone(page);if(failure)throw failure;if(pending)return pending.promise;return response();};
const originalFetch=window.fetch,clock=Date.now;let model,ui;
const fail=fn=>{try{fn();return false;}catch{return true;}};
try{
 assert(MERCHANT_PAGES['/merchant/ai']==='AI Assistant','dedicated Merchant AI navigation');
 assert(resolveRoute('/merchant/ai',null).path==='/merchant/login','unauthenticated AI route');
 assert(resolveRoute('/merchant/ai',{roles:['ADMIN']}).path==='/merchant/login','Admin cannot enter Merchant AI');
 assert(resolveRoute('/merchant/ai',{roles:['MERCHANT']}).merchantView==='/merchant/ai','Merchant direct route');
 assert(merchantRoute('POST','/merchant/ai/chat')&&!merchantRoute('GET','/merchant/ai/chat')&&!merchantRoute('POST','/merchant/ai/chat?role=ADMIN'),'exact client route');
 assert(API.chatTimeoutMs===45000&&API.investigationTimeoutMs===65000,'independent documented timeout budgets');
 for(const q of ['','   ','a '.repeat(501),'bad\0text','\ud800','password=secret','owner@example.test',paymentId])assert(fail(()=>validateQuestion(q)),'invalid question rejected '+results.length);
 assert(validateQuestion('😀'.repeat(1000)).length===2000,'Unicode code-point boundary accepted');
 assert(fail(()=>validateQuestion('😀'.repeat(1001))),'Unicode oversized boundary');
 const completed={question:'What is the current payment status?',status:'completed',result:response()};
 let history=boundedHistory(Array.from({length:10},()=>clone(completed)));assert(history.length===8,'maximum eight messages');assert(history.every(m=>['user','assistant'].includes(m.role)),'history roles exact');
 const largeTurn={question:'q '.repeat(499),status:'completed',result:{answer:'a '.repeat(499)}};
 history=boundedHistory(Array.from({length:10},()=>clone(largeTurn)));assert(history.length===6&&history.reduce((n,m)=>n+[...m.content].length,0)<=6000,'6000-character history boundary');
 assert(boundedHistory([{...completed,status:'failed'}]).length===0,'failed turns excluded');
 assert(boundedHistory([{...completed,status:'sending'}]).length===0,'pending turns excluded');
 assert(boundedHistory([{...completed,result:{answer:'words '.repeat(200)}}]).length===0,'long answer omitted whole');
 const body=makeRequest('What is idempotency?',[],null);assert(JSON.stringify(body.context)==='{"statistics":{}}','overview supplies supported statistics selector');assert(!('callerRole'in body)&&!('evidence'in body)&&!('merchantId'in body),'no role identity evidence spoofing');
 assert(makeRequest('Why?',[],selected).context.paymentId===paymentId,'payment selector contract');
 assert(validateChat(response(),selected).answer===publicChatFixture.answer,'actual Phase692 synthetic fixture accepted');
 assert(fail(()=>validateChat(response(),null)),'unselected payment reference rejected');
 for(const mutate of [r=>r.correlationId='bad',r=>r.evidenceProvenance.scope='ADMIN_AUTHORIZED',r=>r.moneyFacts=[{kind:'ORIGINAL_PAYMENT',amount:100,currency:'INR',count:null}],r=>r.evidenceReferences[0].resourceId='https://evil.invalid',r=>r.generationStatus='SUCCEEDED']){const r=response();mutate(r);assert(fail(()=>validateChat(r,selected)),'invalid structured response rejected '+results.length);}
 setSession(tokenResponse(),'synthetic-merchant');model=createMerchantChat(s=>state=s,{api,locked:()=>locked,onBusy:b=>busyEvents.push(b)});
 assert(!await model.send('Why?'),'cannot send before eligibility');await model.activate();assert(state.eligible&&calls.length===1&&calls[0].path==='/merchant/profile','opening checks profile without automatic chat');
 await model.loadPayments('synthetic',0);assert(calls.at(-1).path.includes('size=5')&&calls.at(-1).path.includes('search=synthetic'),'bounded authorized payment search');
 assert(!model.select('00000000-0000-4000-8000-000000000001',true),'cannot select unknown payment');assert(model.select(paymentId),'explicit owned selection');
 assert(await model.send('What is the current payment status?'),'valid send');assert(calls.at(-1).path==='/merchant/ai/chat'&&calls.at(-1).options.method==='POST','actual Java chat route');assert(calls.at(-1).options.body.context.paymentId===paymentId,'no payment-specific Ask AI endpoint used');assert(state.turns[0].status==='completed','completed turn recorded');
 assert(await model.send('Why?'),'follow-up send');assert(calls.at(-1).options.body.history.length===2,'completed prior pair sent');
 assert(!model.select(null),'context replacement requires confirmation');assert(model.select(null,true)&&state.turns.length===0,'confirmed context replacement clears turns');
 // Overview replies contain no selected-payment reference.
 const originalRefs=publicChatFixture.evidenceReferences;publicChatFixture.evidenceReferences=[];
 pending=deferred();const work=model.send('Summarize payment statistics');assert(state.busy&&state.phase==='sending'&&state.startedAt!==null,'loading lifecycle and elapsed start');const n=calls.length;assert(!await model.send('duplicate')&&calls.length===n,'duplicate submission prevented');
 model.restart();assert(!state.busy&&!state.turns.length&&!state.selected&&calls.at(-1).options.signal.aborted,'New Chat aborts and clears context');pending.resolve(response());await work;pending=null;assert(!state.turns.length,'late result after New Chat ignored');
 locked=true;assert(!await model.send('Why?'),'unresolved financial or investigation lock prevents send');locked=false;
 for(const error of [{status:503,code:'AI_UNAVAILABLE'},{status:503,code:'AI_CAPACITY'},{status:504},{reason:'timeout'},{reason:'network'},{status:502}]){failure=error;const before=calls.length;await model.send('Why?');assert(state.failedQuestion==='Why?'&&!state.busy,'failed question retained '+results.length);assert(calls.length===before+1,'no automatic retry '+results.length);assert(state.message===chatFeedback(error),'safe specific failure feedback '+results.length);}
 failure=null;const retryCount=calls.length;assert(await model.retry()&&calls.length===retryCount+1,'explicit retry only');
 model.restart();pending=deferred();const old=model.send('Why?');setSession(tokenResponse(),'replacement');pending.resolve(response());await old;pending=null;assert(!state.turns.length&&!state.eligible&&!state.merchantId,'replacement session cannot receive prior data');
 await model.activate();pending=deferred();const logout=model.send('Why?');clearSession('other-tab');pending.resolve(response());await logout;pending=null;assert(!state.turns.length&&!state.page&&!state.selected,'cross-tab session invalidation clears private state');
 setSession(tokenResponse(),'synthetic');await model.activate();failure={status:403};await model.send('Why?');failure=null;assert(!state.eligible&&!state.turns.length&&!state.failedQuestion,'authorization loss clears questions and answers');
 const wrong=tokenResponse(['MERCHANT']);const parts=wrong.accessToken.split('.');const claims=JSON.parse(atob(parts[1].replace(/-/g,'+').replace(/_/g,'/')));claims.account_status='PENDING_APPROVAL';parts[1]=btoa(JSON.stringify(claims)).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');wrong.accessToken=parts.join('.');setSession(wrong,'pending');const noCalls=calls.length;assert(!await model.activate()&&calls.length===noCalls,'pending Merchant cannot activate UI');
 setSession(tokenResponse(['ADMIN']),'admin');assert(!await model.activate(),'wrong role model denial');
 setSession(tokenResponse(),'merchant');await model.activate();failure=null;
 publicChatFixture.evidenceReferences=originalRefs;
 const rag=response();rag.analysisMode='RAG_LLM';rag.generationStatus='SUCCEEDED';rag.knowledgeReferences=[clone(knownChatReference)];assert(generationLabel(validateChat(rag,selected)).includes('succeeded'),'LLM success label');rag.analysisMode='RAG_ASSISTED';rag.generationStatus='TIMEOUT';assert(generationLabel(validateChat(rag,selected)).includes('no successful LLM'),'honest RAG timeout fallback');assert(generationLabel(response()).startsWith('Deterministic'),'honest deterministic label');
 const host=document.createElement('div');document.getElementById('fixture').append(host);const malicious=response();malicious.answer='<script>alert(1)</script>';malicious.knowledgeReferences=[{...knownChatReference,title:'<img src=x onerror=alert(1)>',sources:['https://evil.invalid/<script>']}];malicious.moneyFacts=[{kind:'ORIGINAL_PAYMENT',amount:'999999999999.99',currency:'INR',count:null},{kind:'REFUND_AGGREGATE',amount:'0.01',currency:'USD',count:1}];let copied='',asked='',opened='';renderAnswer(host,malicious,{copy:async text=>copied=text,ask:q=>asked=q,openPayment:id=>opened=id});
 assert(host.textContent.includes('<script>')&&!host.querySelector('script')&&!host.querySelector('img'),'answer and knowledge strings rendered as safe text');assert(!host.querySelector('a'),'untrusted sources never external links');assert(!host.textContent.includes('999999999999.99 INR')&&host.textContent.includes('0.01 USD'),'exact refund amounts stay separate without repeating selected payment');assert(host.querySelector('details')&&host.querySelector('summary'),'expandable accessible evidence');
 const buttons=[...host.querySelectorAll('button')];buttons.find(b=>b.textContent==='Copy answer').click();await Promise.resolve();assert(copied===malicious.answer,'safe Copy Answer');buttons.find(b=>b.textContent.startsWith('Ask:')).click();assert(asked===malicious.suggestedFollowUps[0],'follow-up requires explicit click');buttons.find(b=>b.textContent==='Open payment').click();assert(opened===paymentId,'authorized detail callback only');
 const emptySources=response();emptySources.knowledgeReferences=[{...knownChatReference,title:'   '}];assert(fail(()=>validateChat(emptySources,selected)),'blank knowledge heading rejected');
 const noFacts=response();noFacts.evidenceReferences=[];noFacts.knowledgeReferences=[];noFacts.limitations=['','   '];noFacts.evidenceProvenance.limitations=[];
 const blankHost=document.createElement('section');renderAnswer(blankHost,noFacts);assert(!blankHost.querySelector('li'),'empty limitations do not create empty bullets');
 assert(blankHost.textContent.includes('No transaction records were cited.')&&blankHost.textContent.includes('No guidance documents were cited.'),'empty reference groups use explicit unavailable text');
 assert(generationLabel({...rag,analysisMode:'RAG_LLM'}).includes('not independent proof'),'model completion is not presented as factual certification');
 const uiRoot=document.createElement('section');document.getElementById('fixture').append(uiRoot);let uiCalls=[];ui=mountMerchantAI(uiRoot,{api:async(path,options)=>{uiCalls.push({path,options});return path==='/merchant/profile'?clone(profile):response();},openPayment:()=>{},confirm:()=>true});ui.show();await Promise.resolve();await Promise.resolve();assert(uiCalls.length===1&&uiCalls[0].path==='/merchant/profile','view opens without AI request');assert(uiRoot.textContent.includes('New Chat')&&uiRoot.querySelector('textarea'),'composer and reset accessible');assert([...uiRoot.querySelectorAll('p')].some(n=>n.getAttribute('role')==='status')&&[...uiRoot.querySelectorAll('div')].some(n=>n.getAttribute('role')==='region'),'accessible status and conversation region');
 ui.model.select(null,true);ui.clear();assert(uiRoot.querySelector('textarea').value===''&&!uiRoot.textContent.includes('<script>'),'private view cleanup');ui.dispose();ui=null;
 // A model never treats an insufficient-evidence answer as a transport error.
 const insuff=response();insuff.intent='INSUFFICIENT_EVIDENCE';insuff.evidenceReferences=[];
 const clarification=createMerchantChat(()=>{}, {api:async path=>path==='/merchant/profile'?clone(profile):insuff});await clarification.activate();assert(await clarification.send('What about it?')&&clarification.state().phase==='insufficient','insufficient evidence is a successful explanatory state');clarification.dispose();
 // Expiry clears both history and selectors through the existing lifecycle.
 await model.loadPayments('',0);model.select(paymentId,true);Date.now=()=>clock()+901000;assert(!await model.send('Why?')&&!model.state().turns.length&&!model.state().selected,'expiry clears private conversation and selection');Date.now=clock;setSession(tokenResponse(),'restored-for-tests');
 // View keyboard actions remain explicit; Shift+Enter never sends.
 const keyboardRoot=document.createElement('section');document.getElementById('fixture').append(keyboardRoot);let keyboardCalls=[],keyboardPending=deferred(),keyboardConfirm=true;
 const keyboardUI=mountMerchantAI(keyboardRoot,{api:async(path,options)=>{keyboardCalls.push({path,options});return path==='/merchant/profile'?clone(profile):keyboardPending.promise;},openPayment:()=>{},confirm:()=>keyboardConfirm});keyboardUI.show();await Promise.resolve();await Promise.resolve();
 const textarea=keyboardRoot.querySelector('textarea');textarea.value='<script>question</script>';const shift=new Event('keydown');Object.defineProperties(shift,{key:{value:'Enter'},shiftKey:{value:true}});textarea.dispatchEvent(shift);assert(keyboardCalls.length===1,'Shift+Enter preserves newline without sending');
 const enter=new Event('keydown');Object.defineProperties(enter,{key:{value:'Enter'},shiftKey:{value:false}});textarea.dispatchEvent(enter);assert(keyboardCalls.length===2&&keyboardUI.busy(),'Enter explicitly sends one question');assert(keyboardRoot.textContent.includes('<script>question</script>')&&!keyboardRoot.querySelector('script'),'user bubble is safe literal text');assert(keyboardRoot.textContent.includes('Elapsed'),'elapsed loading indicator displayed');assert(keyboardRoot.querySelector('textarea').disabled,'composer disabled while sending');
 keyboardConfirm=false;[...keyboardRoot.querySelectorAll('button')].find(b=>b.textContent==='New Chat').click();assert(keyboardUI.busy()&&keyboardUI.model.state().turns.length===1,'cancelling New Chat confirmation preserves pending conversation');keyboardConfirm=true;[...keyboardRoot.querySelectorAll('button')].find(b=>b.textContent==='New Chat').click();assert(!keyboardUI.busy()&&!keyboardUI.model.state().turns.length,'New Chat during request invalidates UI safely');const oldReply=response();oldReply.evidenceReferences=[];keyboardPending.resolve(oldReply);await Promise.resolve();await Promise.resolve();assert(!keyboardUI.model.state().turns.length,'view ignores completed cancelled response');keyboardUI.dispose();
 // Memory is bounded without preventing retry of a failed final turn.
 let capCalls=0;const capReply=response();capReply.evidenceReferences=[];
 const capped=createMerchantChat(()=>{}, {api:async path=>{if(path==='/merchant/profile')return clone(profile);if(++capCalls===20)throw {status:503};return clone(capReply);}});await capped.activate();for(let i=0;i<20;i++)await capped.send('Why?');assert(capped.state().turns.length===20&&capped.state().failedQuestion==='Why?','twenty-turn memory bound retains final failure');assert(await capped.retry()&&capped.state().turns.length===20,'failed final turn can be retried at memory limit');assert(!await capped.send('A new question'),'new question blocked at memory limit');capped.restart();assert(await capped.send('Why?'),'New Chat restores composer capacity');capped.dispose();
 // Real central client integration, all fetch responses synthetic.
 let transportCalls=[],capturedSignal;window.fetch=async(url,options)=>{transportCalls.push({url,options});capturedSignal=options.signal;return {ok:false,status:503,json:async()=>({code:'AI_CAPACITY',message:'RAW_UNTRUSTED_EXCEPTION'}),headers:new Headers()};};
 let apiError;try{await request('/merchant/ai/chat',{method:'POST',body:makeRequest('Why?',[],null)});}catch(e){apiError=e;}assert(apiError.code==='AI_CAPACITY'&&!apiError.message.includes('RAW'),'allowlisted error code only');assert(transportCalls[0].url==='/api/v1/merchant/ai/chat'&&transportCalls[0].options.credentials==='omit'&&transportCalls[0].options.headers.Authorization,'same-origin bearer and no cookie authority');
 const transportCount=transportCalls.length;try{await request('/merchant/ai/chat',{method:'POST',body:{question:'😀'.repeat(10000)}});}catch(e){apiError=e;}assert(apiError.status===413&&transportCalls.length===transportCount,'exact UTF-8 request byte limit before fetch');
 const abort=new AbortController();window.fetch=async(url,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('cancelled'),{name:'AbortError'}))));const cancelled=request('/merchant/ai/chat',{method:'POST',body:{question:'Why?'},signal:abort.signal});abort.abort();try{await cancelled;}catch(e){apiError=e;}assert(apiError.reason==='cancelled','external abort distinguished from timeout');
 let finish401;window.fetch=()=>new Promise(resolve=>finish401=resolve);const late401=request('/merchant/ai/chat',{method:'POST',body:{question:'Why?'}});setSession(tokenResponse(),'newer-account');finish401(new Response('{}',{status:401}));try{await late401;}catch{}assert(getSession()?.identity==='newer-account','late chat401 cannot clear a replacement session');
 assert(busyEvents.includes(true)&&busyEvents.includes(false),'shared AI busy lock released');
 document.getElementById('summary').textContent=`PASS: ${results.length} assertions`;for(const s of results){const li=document.createElement('li');li.textContent=s;document.getElementById('results').append(li);}
}catch(error){document.getElementById('summary').textContent='FAIL: '+error.message;throw error;}
finally{Date.now=clock;window.fetch=originalFetch;ui?.dispose();model?.dispose();clearSession('test-cleanup');}
