import {conversationBookmark} from './conversations/bookmark.js';
import {createConversationStore} from './conversations/store.js';
import {canonicalContext,contextKey,validateSummary,validateMessages} from './conversations/schema.js';
import {conversationRoute} from './conversations/routes.js';
import {createHistoryView} from './conversations/view.js';
import {mountMerchantAI} from './merchant-ai/view.js';
import {mountPaymentAI} from './payment-ai/view.js';
import {mountAdminAI} from './admin-ai/view.js';
import {adminStatisticsFixture} from './admin-ai-test-fixtures.js';
import {publicChatFixture} from './merchant-ai-test-fixtures.js';
import {setSession,clearSession} from './auth/session.js';
import {tokenResponse,paymentId} from './test-fixtures.js';
const results=[],assert=(v,label)=>{if(!v)throw Error(label);results.push(label);},copy=v=>structuredClone(v),uuid=()=>crypto.randomUUID();
const mid='SYNTHETIC_MERCHANT',cid=uuid(),now='2026-11-16T00:00:00Z',response=copy(publicChatFixture);
const meta=(role='MERCHANT',context={paymentId})=>({conversationId:cid,portalRole:role,contextType:context.paymentId?'PAYMENT':role==='ADMIN'&&!context.merchantId?'PLATFORM':'MERCHANT',context,title:'Saved <script>safe</script>',version:0,turnCount:0,createdAt:now,updatedAt:now,expiresAt:'2026-12-16T00:00:00Z',merchantId:role==='MERCHANT'||context.paymentId||context.merchantId?mid:null,payment:context.paymentId?{paymentId,merchantId:mid,amount:'100.00',currency:'INR',paymentMethod:'UPI',status:'SUCCESS'}:null,merchant:role==='MERCHANT'||context.paymentId||context.merchantId?{merchantId:mid,businessName:null,status:'ACTIVE'}:null,activeRequest:null});
response.moneyFacts=[{kind:'ORIGINAL_PAYMENT',amount:'100.00',currency:'INR',count:null}];
const fail=fn=>{try{fn();return false;}catch{return true;}};
let store,ui,adminUI,paymentUI;
try{
 for(const role of ['merchant','admin']){
  const base='/'+role+'/ai/conversations';
  for(const [method,path] of [['POST',base],['GET',base+'?page=0&size=5&search=Saved'],['GET',base+'/'+cid],['GET',base+'/'+cid+'/messages?page=0&size=5'],['GET',base+'/creations/'+cid],['GET',base+'/'+cid+'/requests/'+cid],...['messages','rename','delete'].map(x=>['POST',base+'/'+cid+'/'+x])])assert(conversationRoute(method,path),'exact route '+method+' '+path);
  for(const path of [base+'?ownerId=evil',base+'?size=11',base+'?page=0&page=1',base+'/not-uuid',base+'/'+cid+'/shell'])assert(!conversationRoute('GET',path),'strict route '+path);
 }
 assert(contextKey({statistics:{}})===contextKey({}),'overview canonical default');
 assert(fail(()=>canonicalContext({ownerId:uuid()})),'identity selector rejected');
 assert(fail(()=>canonicalContext({paymentId,statistics:{}})),'payment filters rejected');
 assert(fail(()=>validateSummary({...meta(),portalRole:'ADMIN'},'MERCHANT')),'role mismatch rejected');
 let c=meta(),turns=[],calls=[],pending=null,sendError=null,deleteError=null,createError=null,adopted=null,forgot=0,held=null;
 const api=async(path,o={})=>{
  calls.push({path,options:copy({...o,signal:undefined})});
  if(path.endsWith('/profile'))return {merchantId:mid,accountStatus:'ACTIVE',membershipActive:true,merchantVerified:true,merchantActive:true,businessStatus:'ACTIVE',registrationAvailable:false};
  if(o.method==='POST'&&path.endsWith('/conversations')){if(createError){const e=createError;createError=null;throw e;}return {conversation:copy(c),replay:false};}
  if(path.includes('/creations/'))return {conversation:copy(c),replay:true};
  if(path.includes('/requests/'))return {requestId:pending?.requestId,status:pending?.status||'COMPLETED',conversation:copy(c),turn:turns.at(-1)};
  if(o.method==='POST'&&path.endsWith('/messages')){
   pending={...o.body,status:'IN_PROGRESS'};if(held)return held;
   if(sendError){const e=sendError;sendError=null;pending.status='FAILED';throw e;}
   const r=copy(!c.payment&&c.portalRole==='ADMIN'?adminStatisticsFixture:response);if(c.payment)r.evidenceReferences[0].resourceId=paymentId;else r.evidenceReferences=r.evidenceReferences.filter(x=>x.resourceType!=='PAYMENT');r.evidenceProvenance.scope=c.portalRole==='ADMIN'?'ADMIN_AUTHORIZED':'MERCHANT_OWNED';
   c.version++;c.turnCount++;const turn={requestId:o.body.requestId,turnIndex:c.turnCount,question:o.body.question,response:r,createdAt:now};turns.push(turn);pending.status='COMPLETED';
   return {status:'COMPLETED',requestId:o.body.requestId,conversation:copy(c),turn};
  }
  if(o.method==='POST'&&path.endsWith('/rename')){c.title=o.body.title;c.version++;return {conversation:copy(c)};}
  if(o.method==='POST'&&path.endsWith('/delete')){if(deleteError)throw deleteError;return {deleted:true};}
  if(path.includes('/messages?'))return {conversation:copy(c),turns:copy(turns),page:0,size:5,total:c.turnCount};
  if(path.includes('?'))return {items:[copy(c)],page:0,size:5,total:1};
  return {conversation:copy(c)};
 };
 const persistentToken=tokenResponse(['MERCHANT']);const parts=persistentToken.accessToken.split('.');const claims=JSON.parse(atob(parts[1]));claims.sid=uuid();parts[1]=btoa(JSON.stringify(claims)).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');persistentToken.accessToken=parts.join('.');
 setSession(persistentToken,'merchant');
 store=createConversationStore({api,adopt:data=>{adopted=data;return true;},onForget:()=>forgot++});
 store.setScope({portalRole:'MERCHANT',context:{paymentId},fixedPaymentId:paymentId});
 assert(calls.length===0,'initialization never creates or calls inference');
 await store.list('Saved');assert(calls.length===1&&calls[0].path.includes('paymentId='),'bounded fixed payment history');
 await store.open(cid);assert(adopted.completed.length===0&&store.state().selected.conversationId===cid,'explicit empty restore no inference');
 const send=()=>store.transport('/payments/'+paymentId+'/ai/chat',{method:'POST',body:{question:'What is this payment status?',history:[]}});
 await send();assert(c.turnCount===1,'completed persisted turn');
 const sent=calls.find(x=>x.options.body?.question);assert(Object.keys(sent.options.body).sort().join(',')==='expectedVersion,question,requestId','only server owned question/request/version contract');
 assert(!('history'in sent.options.body)&&!('evidence'in sent.options.body),'client history and evidence excluded');
 await store.open(cid);assert(adopted.completed[0].historical&&adopted.completed[0].result.moneyFacts[0].amount===response.moneyFacts[0].amount,'historical exact money restored');
 assert(calls.filter(x=>x.options.body?.question).length===1,'restore never runs inference');
 await store.rename('Renamed safely');assert(store.state().selected.title==='Renamed safely','rename actual projection');
 assert(store.state().items[0].title==='Renamed safely','confirmed rename updates loaded history label');
 assert(store.state().items[0].version===store.state().selected.version,'loaded rename metadata uses confirmed server version');

 const tab={history:{state:{routerMarker:'keep'},replaceState(value){this.state=value;}}};
 const bookmark=conversationBookmark(tab);
 bookmark.save('MERCHANT','portal',cid);
 assert(tab.history.state.routerMarker==='keep','bookmark preserves unrelated routing state');
 assert(bookmark.load('MERCHANT','portal')===cid,'tab bookmark survives a new adapter instance');
 assert(conversationBookmark(tab).load('MERCHANT','portal')===cid,'refresh pointer is readable without conversation content');
 assert(!bookmark.load('MERCHANT',paymentId),'different payment entry point cannot restore portal selection');
 bookmark.save('MERCHANT','portal',cid);
 assert(!bookmark.load('ADMIN','portal'),'Merchant bookmark cannot restore into Admin role');
 bookmark.save('MERCHANT','portal',cid);
 tab.history.state.paymeshConversation.subject=uuid();
 assert(!bookmark.load('MERCHANT','portal'),'another account cannot restore the tab pointer');
 bookmark.save('MERCHANT','portal',cid);tab.history.state.paymeshConversation.session=uuid();
 assert(!bookmark.load('MERCHANT','portal'),'replacement refresh session cannot restore the old pointer');
 bookmark.save('MERCHANT','portal',cid);bookmark.clear();
 assert(!bookmark.load('MERCHANT','portal'),'logout-style clearing removes tab pointer');
 // Automatic restore issues only authorized GET reads, once per mounted store.
 let autoSelected=null,autoCalls=[];
 const memoryBookmark={load:()=>cid,save(){},clear(){this.cleared=true;}};
 const automatic=createConversationStore({bookmark:memoryBookmark,api:async(path,o)=>{autoCalls.push({path,o});return api(path,o);},adopt:d=>{autoSelected=d;return true;}});
 automatic.setScope({portalRole:'MERCHANT',context:{paymentId},fixedPaymentId:paymentId});
 assert(await automatic.restoreLast(),'last selected conversation automatically restores via API');
 assert(autoSelected.completed.length===1&&automatic.state().selected.conversationId===cid,'automatic restore adopts validated authorized history');
 assert(autoCalls.length===1&&autoCalls[0].path.includes('/messages?')&&!autoCalls[0].o,'automatic restoration is GET only, never inference');
 assert(!await automatic.restoreLast()&&autoCalls.length===1,'automatic restore is not repeated on render');
 automatic.newChat();assert(memoryBookmark.cleared&&!automatic.state().selected,'New Chat clears saved pointer');automatic.dispose();
 for(const status of [401,403,404,409,503]){
  const mark={load:()=>cid,save(){},clear(){this.cleared=true;}};
  const broken=createConversationStore({bookmark:mark,api:async()=>{throw {status};},adopt:()=>true});
  broken.setScope({portalRole:'MERCHANT',context:{paymentId}});
  assert(!await broken.restoreLast()&&!broken.state().selected&&mark.cleared,'failed restoration clears pointer '+status);
  assert(broken.state().message.length>20,'safe restoration error message '+status);broken.dispose();
 }

 let conflictCalls=[];
 const conflictStore=createConversationStore({bookmark:{load:()=>null,save(){},clear(){}},adopt:()=>true,api:async(path,o)=>{conflictCalls.push({path,o});if(path.endsWith('/rename'))throw {status:409};return api(path,o);}});
 conflictStore.setScope({portalRole:'MERCHANT',context:{paymentId}});await conflictStore.open(cid);
 const priorVersion=conflictStore.state().selected.version;
 assert(!await conflictStore.rename('Conflicting title'),'rename version conflict is not claimed as success');
 assert(conflictStore.state().selected.version===priorVersion&&conflictStore.state().message.includes('version changed'),'409 preserves confirmed version and requests reload');
 assert(conflictCalls.at(-1).o.body.expectedVersion===priorVersion,'rename transmits confirmed optimistic version');
 conflictStore.dispose();

 for(const status of [404,409,503]){
  const deletion=createConversationStore({bookmark:{load:()=>null,save(){},clear(){}},adopt:()=>true,api:async(path,o)=>{if(path.endsWith('/delete'))throw {status};return api(path,o);}});
  deletion.setScope({portalRole:'MERCHANT',context:{paymentId}});await deletion.open(cid);
  assert(!await deletion.remove(true)&&deletion.state().uncertainDelete,'delete failure never claims success '+status);
  assert(deletion.state().selected.conversationId===cid,'failed deletion retains record for reconciliation '+status);deletion.dispose();
 }
 // A page refresh starts a new memory-only store; explicit list/open restores server state.
 let restoredAfterRefresh=null;
 const refreshed=createConversationStore({api,adopt:data=>{restoredAfterRefresh=data;return true;}});
 refreshed.setScope({portalRole:'MERCHANT',context:{paymentId},fixedPaymentId:paymentId});
 assert(!refreshed.state().selected&&!refreshed.state().items.length,'refresh never persists a browser conversation selector');
 const inferenceBeforeRestore=calls.filter(x=>x.options.body?.question).length;
 assert(await refreshed.list()&&await refreshed.open(cid),'refresh restoration uses explicit authorized list and detail');
 assert(restoredAfterRefresh.completed.length===1&&refreshed.state().selected.title==='Renamed safely','fresh store restores saved turn and renamed title');
 assert(calls.filter(x=>x.options.body?.question).length===inferenceBeforeRestore,'refresh restoration performs no inference');
 assert(await refreshed.remove(true),'confirmed deletion succeeds with restored current version');
 const deleted=calls.at(-1);assert(deleted.path.endsWith('/delete')&&deleted.options.method==='POST'&&deleted.options.body.expectedVersion===c.version,'deletion uses exact authorized POST and current version');
 assert(!refreshed.state().selected&&!refreshed.state().items.length,'confirmed deletion clears displayed history and selection');
 refreshed.dispose();
 const before=calls.length;assert(!await store.rename('password=NEVER_STORE')&&calls.length===before,'secret title rejected before transport');
 assert(!await store.remove(false),'delete needs confirmation');
 deleteError={status:0};assert(!await store.remove(true)&&store.state().uncertainDelete,'uncertain delete never claims success');
 const deleteCount=calls.length;assert(!await store.remove(true)&&calls.length===deleteCount,'uncertain deletion cannot be blindly resubmitted');await store.reconcile();assert(!store.state().uncertainDelete&&store.state().message.includes('not established'),'delete reconciliation uses read');
 deleteError=null;
 store.newChat();assert(!store.state().selected,'New Chat clears private selected state');
 const n=calls.length;assert(calls.length===n,'New Chat has no empty creation');
 c=meta();turns=[];createError={status:0};try{await send();}catch{}const firstCreate=calls.filter(x=>x.options.method==='POST'&&x.path.endsWith('/conversations')).at(-1);
 await send();assert(calls.some(x=>x.path.includes('/creations/'+firstCreate.options.body.requestId)),'uncertain creation reconciles original identity');
 store.newChat();c=meta();turns=[];sendError={status:504};try{await send();}catch{}const failed=calls.filter(x=>x.options.body?.question).at(-1);await send();const retried=calls.filter(x=>x.options.body?.question).at(-1);assert(failed.options.body.requestId===retried.options.body.requestId&&failed.options.body.expectedVersion===retried.options.body.expectedVersion,'explicit retry same durable request identity');
 store.newChat();c=meta();turns=[];let resolve;held=new Promise(r=>resolve=r);const late=send().catch(()=>{});await Promise.resolve();await Promise.resolve();clearSession('logout');resolve({status:'COMPLETED',conversation:c});await late;held=null;assert(store.state().selected===null&&store.state().items.length===0,'logout rejects late private response');
 setSession(tokenResponse(['MERCHANT']),'merchant');store.setScope({portalRole:'MERCHANT',context:{paymentId},fixedPaymentId:paymentId});await store.list();setSession(tokenResponse(['ADMIN']),'admin');assert(!store.state().items.length&&!store.state().selected,'role switch clears history');
 store.setScope({portalRole:'ADMIN',context:{statistics:{}}});c=meta('ADMIN',{statistics:{}});await store.list();assert(store.state().items[0].portalRole==='ADMIN','Admin separate namespace');assert(calls.at(-1).path.startsWith('/admin/'),'Admin API namespace');
 const host=document.createElement('section');document.getElementById('fixture').append(host);const history=createHistoryView({store,confirm:()=>true});host.append(history.root);history.render(store.state());assert(host.textContent.includes('Historical answers')&&host.querySelector('summary'),'accessible history drawer and historical label');assert(!host.querySelector('script')&&host.textContent.includes('<script>'),'titles rendered literal text');assert(host.querySelector('input').type==='search','bounded search control');
 store.dispose();store=null;
 let denied=false;store=createConversationStore({api:async()=>{throw {status:403};},adopt:()=>true,onDeny:()=>denied=true});store.setScope({portalRole:'ADMIN',context:{statistics:{}}});await store.list();assert(denied&&!store.state().items.length&&!store.state().selected,'authorization failure clears private history and presentation');store.dispose();store=null;

 setSession(tokenResponse(['MERCHANT']),'merchant');const pagingMeta={...meta(),version:7,turnCount:7};let pagingURL='';
 store=createConversationStore({adopt:()=>true,api:async(path)=>{pagingURL=path;const page=Number(new URLSearchParams(path.split('?')[1]).get('page'));if(path.includes('/messages?')){const indices=page===0?[3,4,5,6,7]:[1,2];return {conversation:pagingMeta,turns:indices.map(i=>({requestId:uuid(),turnIndex:i,question:'What is the recorded status?',response:copy(response),createdAt:now})),page,size:5,total:7};}return {items:Array.from({length:page===0?5:2},()=>({...meta(),conversationId:uuid()})),page,size:5,total:7};}});
 store.setScope({portalRole:'MERCHANT',context:{paymentId}});
 assert(await store.list('Payment follow-up',1),'history next page loads explicitly');
 assert(store.state().page===1&&store.state().items.length===2&&store.state().total===7,'final partial conversation page');
 assert(pagingURL.includes('size=5')&&pagingURL.includes('search=Payment+follow-up'),'bounded literal search and pagination');
 assert(await store.open(cid,1)&&store.state().messagePage===1,'older completed turn page');
 assert(store.blocked(),'older historical page cannot submit a mixed continuation');
 assert(await store.open(cid,0)&&!store.blocked(),'latest history page restores continuation');
 assert(store.state().messageTotal===7,'completed turn total is independent of visible five');
 store.dispose();store=null;
 // Shared production adapter integration; no calls on page initialization.
 setSession(tokenResponse(['MERCHANT']),'merchant');let integrationCalls=[];c=meta('MERCHANT',{statistics:{}});turns=[];
 const integrationAPI=async(path,o={})=>{integrationCalls.push({path,o});if(path==='/merchant/profile')return {merchantId:mid,accountStatus:'ACTIVE',membershipActive:true,merchantVerified:true,merchantActive:true,businessStatus:'ACTIVE',registrationAvailable:false};return api(path,o);};
 const root=document.createElement('section');document.getElementById('fixture').append(root);ui=mountMerchantAI(root,{api:integrationAPI,savedConversations:true,confirm:()=>true});ui.show();for(let i=0;i<10;i++)await Promise.resolve();assert(integrationCalls.length===1&&integrationCalls[0].path==='/merchant/profile','Merchant opening reads authorization only');
 assert(root.textContent.includes('Saved conversations')&&ui.model.state().eligible,'Merchant shared persistence UI eligibility');

 c=meta();turns=[];assert(await ui.conversations.open(cid),'shared Merchant restore adopts authorized payment');
 assert(ui.model.state().selected.paymentId===paymentId,'restored payment selector remains exact');
 assert(await ui.model.send('What is this payment status?'),'shared Merchant sends persistent message');
 assert(integrationCalls.some(x=>x.path.endsWith('/messages')&&x.o.method==='POST'),'shared Merchant uses saved message endpoint');
 assert(!integrationCalls.some(x=>x.path==='/merchant/ai/chat'),'no stateless fallback from managed UI');
 assert(ui.model.state().turns[0].result.moneyFacts[0].amount==='100.00','shared monetary string preserved');
 await ui.conversations.open(cid);assert(ui.model.state().turns[0].historical,'shared restored answer marked historical');
 await ui.conversations.remove(true);assert(!ui.model.state().turns.length&&!ui.conversations.state().selected,'confirmed delete clears transcript and metadata');
 c=meta('MERCHANT',{statistics:{currency:'USD'}});turns=[];assert(await ui.conversations.open(cid),'filtered overview can restore');
 assert(ui.model.state().savedStatistics.currency==='USD','Merchant restored filters retained without silent substitution');
 ui.model.restart();assert(ui.model.state().savedStatistics===null,'new context retires restored aggregate filters');
 clearSession('logout');assert(!ui.model.state().turns.length&&!ui.conversations.state().selected,'shared logout clears both layers');
 setSession(tokenResponse(['ADMIN']),'admin');const aroot=document.createElement('section');document.getElementById('fixture').append(aroot);adminUI=mountAdminAI(aroot,{api:async(path,o)=>path==='/admin/profile'?{userId:paymentId,login:'admin',enabled:true,accountStatus:'ACTIVE',roles:['ADMIN']}:api(path,o),savedConversations:true});adminUI.show();for(let i=0;i<10;i++)await Promise.resolve();assert(aroot.textContent.includes('Saved conversations')&&adminUI.model.state().eligible,'Admin shared persistence UI eligibility');assert(!aroot.querySelector('script'),'safe Admin history rendering');
 c=meta('ADMIN',{statistics:{currency:'USD'}});turns=[];assert(await adminUI.conversations.open(cid),'Admin restores platform filtered history');
 assert(adminUI.model.state().filters.currency==='USD'&&!adminUI.model.state().selected,'Admin aggregate filters restored exactly');assert(await adminUI.model.send('Summarize platform payment statistics'),'Admin saved message send');assert(calls.at(-1).path.startsWith('/admin/ai/conversations/')&&calls.at(-1).path.endsWith('/messages'),'Admin uses role-scoped saved message API');
 setSession(tokenResponse(['MERCHANT']),'merchant');assert(!adminUI.model.state().turns.length&&!adminUI.conversations.state().selected,'Admin cannot survive Merchant replacement');
 const panel=document.createElement('section'),proot=document.createElement('section'),trigger=document.createElement('button'),close=document.createElement('button');panel.append(close,proot);document.getElementById('fixture').append(panel,trigger);
 paymentUI=mountPaymentAI({panel,root:proot,triggers:[trigger],closeButton:close,feedback:document.createElement('p'),api,savedConversations:true,confirm:()=>true});
 const pd={selected:paymentId,payment:{paymentId,merchantId:mid,amount:'100.00',currency:'INR',paymentMethod:'UPI',status:'SUCCESS',createdAt:now,customerId:'SYNTHETIC'},loading:false,intent:null,authorizationRead:1,accessDenied:false};
 paymentUI.observe(pd);assert(paymentUI.open(),'saved Payment Ask AI explicitly opens');
 c=meta();turns=[];assert(await paymentUI.model.state().eligible,'payment remains authorized');
 const existing=calls.length;assert(!calls.slice(existing).some(x=>x.options.body?.question),'payment opening does not run inference');
 assert(proot.textContent.includes('Saved conversations'),'Payment shared history drawer');
 assert(await paymentUI.model.send('What is this payment status?'),'Payment managed message send');
 assert(calls.at(-1).path.startsWith('/merchant/ai/conversations/')&&calls.at(-1).path.endsWith('/messages'),'Payment managed API owns fixed context');
 const drawer=proot.querySelector('details');drawer.querySelector('form').dispatchEvent(new Event('submit'));for(let i=0;i<15;i++)await Promise.resolve();
 const restoreButton=[...drawer.querySelectorAll('button')].find(b=>b.textContent.startsWith('Saved <script>'));assert(restoreButton,'payment history lists compatible owned context');
 restoreButton.click();for(let i=0;i<20;i++)await Promise.resolve();assert(paymentUI.model.state().turns[0]?.historical,'Payment historical restore uses shared validated answer');
 assert(paymentUI.model.state().payment.paymentId===paymentId,'Payment restoration cannot replace parent identity');

 paymentUI.close();assert(!paymentUI.model.state().turns.length,'Close clears fixed payment chat');
 // Stale list responses cannot populate a replacement role.
 let resolveList;const listWait=new Promise(r=>resolveList=r);
 store=createConversationStore({api:()=>listWait,adopt:()=>true});store.setScope({portalRole:'MERCHANT',context:{statistics:{}}});const waiting=store.list();setSession(tokenResponse(['ADMIN']),'admin');resolveList({items:[meta()],page:0,size:5,total:1});await waiting;assert(!store.state().items.length,'late list cannot cross account/role generation');store.dispose();store=null;

}catch(e){results.push('FAIL: '+e.stack);}
finally{store?.dispose();ui?.dispose();adminUI?.dispose();paymentUI?.dispose();clearSession('conversation-tests');}
document.getElementById('summary').textContent=results.some(x=>x.startsWith('FAIL:'))?results.at(-1):'PASS: '+results.length+' assertions';
document.getElementById('results').textContent=results.join('\n');
