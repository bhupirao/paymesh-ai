import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
const source=fs.readFileSync(new URL('../docs/api/site.js',import.meta.url),'utf8');
function boot(base='https://bhupirao.github.io/paymesh-ai/'){
  let options;const state={textContent:''};
  const window={SwaggerUIBundle:value=>{options=value;},addEventListener:(name,callback)=>{assert.equal(name,'DOMContentLoaded');callback();}};
  vm.runInNewContext(source,{window,document:{baseURI:base,getElementById:id=>{assert.equal(id,'reference-state');return state;}},URL});
  return {options,state};
}
test('spec URL is relative under the project subpath',()=>{assert.equal(boot().options.url,'./openapi.json');});
test('all API methods are disabled',()=>{const o=boot().options;assert.equal(o.supportedSubmitMethods.length,0);assert.equal(o.tryItOutEnabled,false);});
test('remote validator and authorization persistence are disabled',()=>{const o=boot().options;assert.equal(o.validatorUrl,null);assert.equal(o.persistAuthorization,false);assert.equal(o.withCredentials,false);});
test('only the local spec GET is allowed, with credentials omitted',()=>{const o=boot().options;const r=o.requestInterceptor({url:'https://bhupirao.github.io/paymesh-ai/openapi.json',method:'GET',headers:{Authorization:'SYNTHETIC_CANARY'}});assert.equal(r.credentials,'omit');assert.equal(Object.keys(r.headers).length,0);});
test('relative spec request works on localhost and Pages',()=>{for(const base of ['http://127.0.0.1:12345/paymesh-ai/','https://bhupirao.github.io/paymesh-ai/'])assert.equal(boot(base).options.requestInterceptor({url:'./openapi.json'}).credentials,'omit');});
test('POST execution is rejected even against the spec path',()=>{assert.throws(()=>boot().options.requestInterceptor({url:'./openapi.json',method:'POST'}),/read-only/);});
test('same-origin API calls are rejected',()=>{for(const url of ['/api/v1/auth/login','./api/v1/payments'])assert.throws(()=>boot().options.requestInterceptor({url,method:'GET'}),/read-only/);});
test('backend and external hosts are rejected',()=>{for(const url of ['http://127.0.0.1:18080/api/v1/payments','https://example.invalid/openapi.json'])assert.throws(()=>boot().options.requestInterceptor({url}),/read-only/);});
test('queries and fragments cannot carry request data',()=>{for(const url of ['./openapi.json?token=SYNTHETIC_CANARY','./openapi.json#SYNTHETIC_CANARY'])assert.throws(()=>boot().options.requestInterceptor({url}),/read-only/);});
test('authorization controls are replaced with inert components',()=>{const c=boot().options.plugins[0]().components;assert.equal(c.authorizeBtn(),null);assert.equal(c.authorizationPopup(),null);});
test('completion feedback states that no backend is used',()=>{const {options,state}=boot();options.onComplete();assert.match(state.textContent,/No backend connection/);});
test('missing Swagger assets give a static-source fallback',()=>{const state={textContent:''};vm.runInNewContext(source,{window:{addEventListener:(n,cb)=>cb()},document:{baseURI:'https://bhupirao.github.io/paymesh-ai/',getElementById:()=>state},URL});assert.match(state.textContent,/API execution remains disabled/);});
