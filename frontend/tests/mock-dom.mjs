// Minimal offline DOM for the browser-compatible suites, not a browser/layout emulator.
// Missing fixture IDs are provisioned to match the historical mocked runtime.
export function installMockDOM(){
 class MockEvent {constructor(type,options={}){this.type=type;Object.assign(this,options);}preventDefault(){this.defaultPrevented=true;}}
 class Target {constructor(){this.listeners=new Map();}addEventListener(t,f){if(!this.listeners.has(t))this.listeners.set(t,new Set());this.listeners.get(t).add(f);}removeEventListener(t,f){this.listeners.get(t)?.delete(f);}dispatchEvent(e){e.target??=this;for(const f of [...(this.listeners.get(e.type)||[])])f.call(this,e);return !e.defaultPrevented;}}
 const ids=new Map();let doc;
 class Node extends Target {
  constructor(tag='div'){super();this.tag=tag.toLowerCase();this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this._text='';this.value='';this.className='';this.hidden=false;this.disabled=false;this.style={};this.dataset={};this.parentNode=null;}
  set id(v){this.attrs.id=v;ids.set(v,this);}get id(){return this.attrs.id||'';}
  set textContent(v){for(const c of this.children)c.parentNode=null;this.children=[];this._text=String(v??'');}get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
  append(...nodes){for(let n of nodes){if(typeof n!=='object') {const t=new Node('#text');t.textContent=n;n=t;}if(n.parentNode)n.parentNode.children=n.parentNode.children.filter(c=>c!==n);n.parentNode=this;this.children.push(n);}}
  appendChild(n){this.append(n);return n;}replaceChildren(...nodes){this.textContent='';this.append(...nodes);}remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(n=>n!==this);this.parentNode=null;}
  setAttribute(k,v){if(k==='id')this.id=v;else this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k]??null;}removeAttribute(k){delete this.attrs[k];}hasAttribute(k){return k in this.attrs;}
  matches(s){if(s.startsWith('#'))return this.id===s.slice(1);const m=s.match(/^(\w+)?(?:\[([^=\]]+)(?:=["']?([^"'\]]+)["']?)?\])?$/);return !!m&&(!m[1]||this.tag===m[1])&&(!m[2]||this.hasAttribute(m[2])&&(m[3]===undefined||this.getAttribute(m[2])===m[3]));}
  querySelectorAll(s){const options=s.split(',').map(t=>t.trim());return this.children.flatMap(c=>[...(options.some(t=>c.matches(t))?[c]:[]),...c.querySelectorAll(s)]);}querySelector(s){return this.querySelectorAll(s)[0]||null;}
  closest(s){return this.matches(s)?this:this.parentNode?.closest(s)||null;}contains(n){return n===this||this.children.some(c=>c.contains(n));}focus(){doc.activeElement=this;}click(){if(!this.disabled)this.dispatchEvent(new MockEvent('click',{button:0}));}reportValidity(){return true;}setCustomValidity(v){this.validationMessage=v;}reset(){for(const n of this.querySelectorAll('input,textarea'))n.value='';}scrollIntoView(){}
 }
 doc=new Target();doc.createElement=tag=>new Node(tag);doc.createTextNode=s=>{const n=new Node('#text');n.textContent=s;return n;};doc.body=new Node('body');doc.head=new Node('head');doc.getElementById=id=>{if(!ids.has(id)){const n=new Node();n.id=id;doc.body.append(n);}return ids.get(id);};doc.querySelector=s=>s.startsWith('#')?doc.getElementById(s.slice(1)):doc.body.querySelector(s);doc.querySelectorAll=s=>doc.body.querySelectorAll(s);doc.visibilityState='visible';
 globalThis.Event=MockEvent;globalThis.EventTarget=Target;globalThis.document=doc;globalThis.window=globalThis;
 const events=new Target();globalThis.addEventListener=events.addEventListener.bind(events);globalThis.removeEventListener=events.removeEventListener.bind(events);globalThis.dispatchEvent=events.dispatchEvent.bind(events);
 globalThis.location={pathname:'/',href:'http://127.0.0.1:5500/',origin:'http://127.0.0.1:5500'};globalThis.navigator={locks:{request:async(name,f)=>f()}};globalThis.isSecureContext=true;
 globalThis.fetch=async()=>{throw new Error('Unmocked network is forbidden');};globalThis.confirm=()=>false;
 return doc;
}
