// Real presentation and history-view modules, synthetic lifecycle/store boundary.
// No network, credentials, native browser, or model execution.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../assets/js');
async function mount(role){
  const context=vm.createContext({console,structuredClone,queueMicrotask,setTimeout:()=>0,clearTimeout(){}});
  const cache=new Map(),calls=[];let notify,store,model,external=false,subscriptions=0;
  const state={eligible:true,busy:false,checking:false,turns:[],message:'',failedQuestion:'',startedAt:null};
  const saved={items:[],page:0,total:0,search:'',busy:false,selected:{conversationId:'synthetic',title:'Synthetic history',version:1,turnCount:1},message:'',messagePage:0,messageTotal:1,uncertainDelete:false};
  const emit=()=>notify(structuredClone(state));
  function createConversationStore(options){
    subscriptions++;
    store={state:()=>structuredClone(saved),blocked:()=>saved.busy,
      setScope(scope){if(!scope&&saved.selected){saved.selected=null;options.onChange(structuredClone(saved));}},
      restoreLast(){return false;},transport(){throw Error('NETWORK_NOT_ALLOWED');},
      change(patch){Object.assign(saved,patch);options.onChange(structuredClone(saved));},
      rename(title){calls.push('rename');saved.selected={...saved.selected,title,version:saved.selected.version+1};this.change({});},
      remove(){calls.push('delete');this.change({selected:null,items:[]});},
      list(){calls.push('list');this.change({items:[saved.selected],total:1});},
      open(){calls.push('load');},newChat(){this.change({selected:null});},dispose(){calls.push('dispose');}};
    return store;
  }
  const exportsFor=(relative)=>{
    if(relative==='api/client.js')return {request(){throw Error('NETWORK_NOT_ALLOWED');}};
    if(relative==='conversations/store.js')return {createConversationStore};
    if(relative==='admin/view.js')return {element(tag,text,cls){const n=context.document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}};
    if(relative==='chat/render.js')return {chatButton(text,run){const b=context.document.createElement('button');b.textContent=text;b.addEventListener('click',run);return b;},renderAnswer(host){const answer=context.document.createElement('p');answer.className='ai-answer';answer.textContent='Synthetic answer';host.append(answer);}};
  };
  async function load(file){
    file=path.resolve(file);if(cache.has(file))return cache.get(file);
    const stub=exportsFor(path.relative(root,file).replaceAll(path.sep,'/'));
    const m=stub?new vm.SyntheticModule(Object.keys(stub),function(){for(const [k,v] of Object.entries(stub))this.setExport(k,v);},{context,identifier:file}):new vm.SourceTextModule(fs.readFileSync(file,'utf8'),{context,identifier:file});
    cache.set(file,m);await m.link((s,parent)=>load(path.resolve(path.dirname(parent.identifier),s)));return m;
  }
  const dom=await load(path.resolve(root,'../../tests/mock-dom.mjs'));await dom.evaluate();dom.namespace.installMockDOM();
  const module=await load(path.join(root,'chat/presentation.js'));await module.evaluate();
  const host=context.document.createElement('section');
  const ui=module.namespace.mountConversation(host,{titleText:role,titleId:'title',helpId:'help',savedConversations:true,api:()=>{throw Error('NETWORK_NOT_ALLOWED');},
    locked:()=>external,confirm:()=>true,conversationScope:()=>({portalRole:role,context:{statistics:{}}}),welcome:()=>[],
    createContext:()=>({root:context.document.createElement('section'),clear(){},render(){}}),
    modelFactory(onChange){notify=onChange;model={state:()=>structuredClone(state),activate(){},busy:()=>state.busy,dispose(){},restart(){},restore(){return true;},clear(){},forget(){}};return model;}});
  ui.show();
  const all=(n=host)=>[n,...n.children.flatMap(c=>all(c))];
  const button=text=>all().find(n=>n.tag==='button'&&n.textContent===text);
  const title=()=>all().find(n=>n.tag==='label'&&n._text==='Conversation title').children[0];
  const form=()=>title().parentNode.parentNode;
  return {ui,host,state,store,calls,emit,title,button,form,context,all,
    lock(value){external=value;emit();},get subscriptions(){return subscriptions;},
    start(){state.busy=true;emit();},finish(success=true){store.change({});state.busy=false;state.turns=[{question:'Synthetic',status:success?'completed':'failed',result:{}}];emit();}};
}
for(const role of ['MERCHANT','ADMIN']){
  test(`${role}: title locks on send and unlocks after completed transport then model idle`,async()=>{
    const e=await mount(role);assert.equal(e.title().disabled,false);e.start();assert.equal(e.title().disabled,true);
    e.store.change({});assert.equal(e.title().disabled,true);e.finish();assert.equal(e.title().disabled,false);
    assert.equal(e.all().some(n=>n.className==='ai-answer'),true);e.ui.dispose();
  });
  test(`${role}: failed send unlocks existing editable history without a store notification afterward`,async()=>{
    const e=await mount(role);e.start();e.finish(false);assert.equal(e.title().disabled,false);
    assert.equal(e.button('Rename saved conversation').disabled,false);assert.equal(e.button('Delete saved conversation').disabled,false);e.ui.dispose();
  });
  test(`${role}: active history operation and external lock remain authoritative`,async()=>{
    const e=await mount(role);e.start();e.store.change({busy:true});e.state.busy=false;e.emit();assert.equal(e.title().disabled,true);
    assert.equal(e.button('Load saved conversations').disabled,true);e.store.change({busy:false});assert.equal(e.title().disabled,false);
    e.lock(true);assert.equal(e.title().disabled,true);assert.equal(e.button('Delete saved conversation').disabled,true);
    e.lock(false);assert.equal(e.title().disabled,false);e.ui.dispose();
  });
  test(`${role}: losing eligibility clears selection and never enables edits`,async()=>{
    const e=await mount(role);e.state.eligible=false;e.emit();assert.equal(e.store.state().selected,null);assert.equal(e.title().disabled,true);
    assert.equal(e.button('Rename saved conversation').disabled,true);assert.equal(e.button('Delete saved conversation').disabled,true);e.ui.dispose();
  });
  test(`${role}: typed title survives model notifications and native history actions remain connected`,async()=>{
    const e=await mount(role);e.title().value='Edited synthetic';e.emit();e.emit();assert.equal(e.title().value,'Edited synthetic');
    e.form().dispatchEvent(new e.context.Event('submit'));assert.equal(e.store.state().selected.title,'Edited synthetic');assert.equal(e.store.state().selected.version,2);
    const search=e.all().find(n=>n.tag==='input'&&n.type==='search');search.parentNode.parentNode.dispatchEvent(new e.context.Event('submit'));
    e.button('Edited synthetic · Current').click();e.button('Delete saved conversation').click();
    assert.deepEqual(e.calls,['rename','list','load','delete']);assert.equal(e.title().disabled,true);e.ui.dispose();
  });
  test(`${role}: repeated model notifications do not create subscriptions or duplicate handlers`,async()=>{
    const e=await mount(role);for(let i=0;i<10;i++){e.start();e.finish();}
    assert.equal(e.subscriptions,1);e.title().value='Once';e.form().dispatchEvent(new e.context.Event('submit'));
    assert.equal(e.calls.filter(v=>v==='rename').length,1);e.ui.dispose();assert.equal(e.calls.filter(v=>v==='dispose').length,1);
  });
}
