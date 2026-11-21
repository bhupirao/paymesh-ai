// Offline module-graph integration. Real app bootstrap, persistence, session,
// router, bookmark and conversation store; rendering adapters only are stubbed.
// No network, native browser or accepted server credentials are used.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {webcrypto} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../assets/js');
const id='12345678-1234-4234-8234-123456789abc',sid='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',cid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
async function boot({route='/merchant/ai',role='MERCHANT',status=200,bookmark=true,owner=id,sessionId=sid,reject=false,legacy=false}={}){
  let release,started;const begun=new Promise(resolve=>started=resolve),pending=new Promise(resolve=>release=resolve);
  const requests=[],mounts=[],channels=[];let router,store,adopted;
  const context=vm.createContext({console,URL,URLSearchParams,TextEncoder,TextDecoder,Uint8Array,AbortController,Response,crypto:webcrypto,structuredClone,atob,btoa,queueMicrotask,setTimeout:()=>0,clearTimeout(){},setInterval:()=>0});
  const cache=new Map();
  async function load(file){
    file=path.resolve(file);if(cache.has(file))return cache.get(file);
    let module;
    const relative=path.relative(root,file).replaceAll(path.sep,'/');
    const empty={};
    if(relative==='features/refunds-view.js')empty.mountRefunds=()=>{mounts.push('refunds');return {render(){},financialLocked:()=>false,locked:()=>false,selected:()=>null};};
    if(relative==='investigation/view.js')empty.mountInvestigation=()=>({observe(){},busy:()=>false});
    if(relative==='features/payments-view.js')empty.mountPayments=()=>({observeLookup(){},refreshLocks(){},investigationBlocked:()=>false,mutationBusy:()=>false});
    if(relative==='payment-ai/view.js')empty.mountPaymentAI=()=>{
      mounts.push('payment-chat');
      // Reproduce the eager payment store's real session-change subscription.
      const eager=cache.get(path.join(root,'conversations/store.js')).namespace.createConversationStore({adopt:()=>false});
      return {observe(){},enter(){},leave(){},busy:()=>false,eager};
    };
    if(relative==='portals/view.js')empty.mountPortals=()=>{
      mounts.push('portals');
      const {createRouter}=cache.get(path.join(root,'portals/router.js')).namespace;
      const {createConversationStore}=cache.get(path.join(root,'conversations/store.js')).namespace;
      router=createRouter(next=>{
        context.document.getElementById('private-view').hidden=next.page!=='dashboard';
        if(next.page==='dashboard'&&next.path.endsWith('/ai')&&!store){
          store=createConversationStore({adopt:data=>{adopted=data;return true;},api:async(endpoint,options)=>{
            requests.push({endpoint,method:options?.method||'GET'});
            return {conversation:{conversationId:cid,portalRole:role,contextType:role==='ADMIN'?'PLATFORM':'MERCHANT',context:{statistics:{}},title:'Synthetic saved history',version:1,turnCount:0,merchantId:role==='MERCHANT'?'synthetic-merchant':null,merchant:role==='MERCHANT'?{merchantId:'synthetic-merchant',status:'ACTIVE',businessName:'Synthetic'}:null,payment:null,activeRequest:null,createdAt:'2026-11-21T00:00:00Z',updatedAt:'2026-11-21T00:00:00Z',expiresAt:'2027-01-01T00:00:00Z'},turns:[],page:0,size:5,total:0};
          }});
          store.setScope({portalRole:role,context:{statistics:{}}});void store.restoreLast();
        }
      });router.start();return {refresh:router.refresh,navigate:router.navigate,loginRole:()=>router.current()?.role,switchBlocked:()=>false};
    };
    if(Object.keys(empty).length){module=new vm.SyntheticModule(Object.keys(empty),function(){for(const [key,value] of Object.entries(empty))this.setExport(key,value);},{context,identifier:file});}
    else {
      let source=fs.readFileSync(file,'utf8');
      if(relative==='app.js'&&legacy){
        source=source.replace("const persistence=installPersistence();\nawait persistence.restore().catch(()=>{clearSession('refresh-failed');});\n",'')
          .replace('workspace.start();','workspace.start();\nconst persistence=installPersistence();\nvoid persistence.restore();');
      }
      module=new vm.SourceTextModule(source,{context,identifier:file});
    }
    cache.set(file,module);await module.link((specifier,parent)=>load(path.resolve(path.dirname(parent.identifier),specifier)));return module;
  }
  // Install the existing deliberately limited DOM, not a browser emulator.
  const dom=await load(path.resolve(root,'../../tests/mock-dom.mjs'));await dom.evaluate();dom.namespace.installMockDOM();
  context.document.getElementById('private-view').hidden=true;
  context.history={state:{marker:'preserve',...(bookmark?{paymeshConversation:{subject:owner,session:sessionId,role,entry:'portal',id:cid}}:{})},replaceState(value,unused,next){this.state=value;if(next){context.location.pathname=next;context.location.href=context.location.origin+next;}},pushState(value,unused,next){this.state=value;context.location.pathname=next;context.location.href=context.location.origin+next;}};
  context.location.pathname=route;context.location.href=context.location.origin+route;
  context.BroadcastChannel=class{constructor(){channels.push(this);}postMessage(){}close(){}};
  const now=Math.floor(Date.now()/1000),encode=x=>Buffer.from(JSON.stringify(x)).toString('base64url');
  const token={tokenType:'Bearer',expiresIn:900,expiresAt:new Date((now+900)*1000).toISOString(),accessToken:encode({alg:'RS256'})+'.'+encode({sub:id,sid,roles:[role],account_status:'ACTIVE',iat:now,exp:now+900})+'.c3ludGhldGlj'};
  context.fetch=async(url,options)=>{
    assert.equal(url,'/api/v1/auth/refresh');assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers.Authorization,undefined);
    requests.push({endpoint:url,method:'POST'});started();await pending;
    if(reject)throw new Error('SYNTHETIC_NETWORK_UNAVAILABLE');
    return new Response(JSON.stringify(status===200?token:{}),{status});
  };
  // Preload actual modules used by the rendering adapters. Graph modules have
  // shared identities, so real session subscriptions and bookmark rules apply.
  for(const name of ['conversations/store.js','portals/router.js']){const m=await load(path.join(root,name));await m.evaluate();}
  const app=await load(path.join(root,'app.js')),evaluation=app.evaluate();await begun;
  return {context,requests,mounts,channels,release,token,async finish(){release();await evaluation;for(let i=0;i<64;i++)await Promise.resolve();},get router(){return router;},get store(){return store;},get adopted(){return adopted;},session:cache.get(path.join(root,'auth/session.js')).namespace};
}
for(const role of ['MERCHANT','ADMIN'])test(`${role} AI refresh restores route and owner-bound bookmark after one native refresh`,async()=>{
  const env=await boot({role,route:`/${role.toLowerCase()}/ai`});
  assert.deepEqual(env.mounts,[]);assert.equal(env.context.location.pathname,`/${role.toLowerCase()}/ai`);assert.equal(env.context.history.state.marker,'preserve');
  await env.finish();assert.equal(env.router.current().path,`/${role.toLowerCase()}/ai`);
  assert.equal(env.store.state().selected.conversationId,cid);assert.equal(env.adopted.conversation.portalRole,role);
  assert.equal(env.context.history.state.marker,'preserve');assert.equal(env.context.history.state.paymeshConversation.id,cid);
  assert.deepEqual(env.requests.map(x=>x.method),['POST','GET']);assert.equal(env.requests[1].endpoint,`/${role.toLowerCase()}/ai/conversations/${cid}/messages?page=0&size=5`);
  assert.equal(JSON.stringify(env.context.history.state).includes(env.token.accessToken),false);
});
test('Merchant payments refresh preserves exact protected route',async()=>{const env=await boot({route:'/merchant/payments',bookmark:false});await env.finish();assert.equal(env.router.current().path,'/merchant/payments');assert.equal(env.context.history.state.marker,'preserve');assert.equal(env.requests.length,1);});
test('unauthenticated deep links redirect only after refresh settles',async()=>{for(const role of ['MERCHANT','ADMIN']){const env=await boot({route:`/${role.toLowerCase()}/ai`,role,status:401});assert.equal(env.mounts.length,0);await env.finish();assert.equal(env.router.current().path,`/${role.toLowerCase()}/login`);assert.equal(env.session.getSession(),null);assert.equal(env.store,undefined);assert.equal(env.context.history.state,null);}});
test('failed restoration remains unauthenticated and never mounts protected history',async()=>{const env=await boot({reject:true});await env.finish();assert.equal(env.router.current().path,'/merchant/login');assert.equal(env.session.getSession(),null);assert.equal(env.requests.length,1);});
test('wrong-role restoration cannot access the requested private portal',async()=>{const env=await boot({role:'ADMIN',route:'/merchant/ai'});await env.finish();assert.equal(env.router.current().path,'/merchant/login');assert.equal(env.router.current().denied,true);assert.equal(env.store,undefined);});
test('logout and subsequent protected navigation cannot restore private content',async()=>{const env=await boot();await env.finish();env.session.clearSession('logout');assert.equal(env.router.current().path,'/merchant/login');assert.equal(env.store.state().selected,null);env.router.navigate('/merchant/ai');assert.equal(env.router.current().page,'login');assert.equal(env.context.history.state?.paymeshConversation??null,null);});
test('cross-tab invalidation clears restored content and does not revive the route',async()=>{const env=await boot();await env.finish();env.channels[0].onmessage({data:{type:'logout'}});assert.equal(env.session.getSession(),null);assert.equal(env.store.state().selected,null);assert.equal(env.router.current().page,'login');env.router.navigate('/merchant/ai');assert.equal(env.router.current().page,'login');});
test('cross-tab revocation during bootstrap rejects the late refresh response',async()=>{const env=await boot();env.channels[0].onmessage({data:{type:'logout'}});await env.finish();assert.equal(env.session.getSession(),null);assert.equal(env.router.current().page,'login');assert.equal(env.requests.length,1);});
test('foreign owner or session bookmarks are cleared without fetching conversations',async()=>{for(const overrides of [{owner:cid},{sessionId:cid}]){const env=await boot(overrides);await env.finish();assert.equal(env.router.current().path,'/merchant/ai');assert.equal(env.store.state().selected,null);assert.equal(env.context.history.state.paymeshConversation,null);assert.equal(env.requests.length,1);assert.equal(env.context.history.state.marker,'preserve');}});
test('malicious route inputs never become protected routes or external redirects',async()=>{const env=await boot({bookmark:false});await env.finish();for(const route of ['https://evil.invalid','//evil.invalid','/merchant/../admin/ai','/merchant/%2e%2e/admin/ai','/merchant/ai?next=https://evil.invalid','/merchant/ai#private','/unknown']){env.router.navigate(route);assert.equal(env.router.current().page,'not-found');assert.ok(!env.context.location.pathname.includes('evil.invalid'));}});
test('public navigation during pending bootstrap is respected rather than replaying an old private target',async()=>{const env=await boot();env.context.location.pathname='/merchant/signup';await env.finish();assert.equal(env.router.current().path,'/merchant/signup');assert.equal(env.store,undefined);});

test('the pre-fix bootstrap order reproduces erased route and bookmark with the same real modules',async()=>{const env=await boot({legacy:true});assert.ok(env.mounts.length>0);assert.equal(env.context.location.pathname,'/merchant/login');assert.equal(env.context.history.state,null);await env.finish();assert.equal(env.router.current().path,'/merchant/dashboard');assert.equal(env.adopted,undefined);});
