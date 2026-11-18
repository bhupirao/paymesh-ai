import { element } from '../admin/view.js';
import { mountConversation } from '../chat/presentation.js';
import { chatButton as button } from '../chat/render.js';
import { createAdminChat } from './model.js';
export function adminSuggestions(state){
 if(state.selected)return ['What is this payment\'s recorded status?','How much was refunded?',"What is this payment's recorded refundable amount?"];
 const comparison=state.filters?.currency?`Summarize ${state.filters.currency} payment statistics`:'Compare INR and USD payment statistics';
 if(state.merchant)return ['Summarize this Merchant\'s payment statistics',comparison,'Explain payment timeout and uncertainty'];
 return ['Summarize platform payment statistics',comparison,'Explain payment timeout and uncertainty'];
}
function adminContext({getModel,change,locked}){
 const root=element('section',undefined,'ai-context');root.setAttribute('aria-label','Authorized Admin conversation context');root.append(element('h3','Admin context'));
 const selected=element('p');const platform=button('Use platform overview',()=>change(()=>getModel().selectMerchant(null,true))),merchant=button('Use selected Merchant overview',()=>change(()=>getModel().selectPayment(null,true)));root.append(selected,platform,merchant);
 const filters=element('form',undefined,'admin-filter-grid');filters.setAttribute('aria-label','Aggregate context filters');
 function field(labelText,type){const label=element('label',labelText,'admin-field'),input=element(type==='select'?'select':'input');input.className=type==='select'?'form-select':'form-control';if(type!=='select')input.type=type;label.append(input);filters.append(label);return input;}
 const currency=field('Aggregate currency','select');for(const value of ['','INR','USD']){const o=element('option',value||'INR and USD (separate)');o.value=value;currency.append(o);}
 const from=field('From UTC day (inclusive)','date'),to=field('Through UTC day (inclusive)','date');
 const apply=element('button','Apply aggregate context','btn btn-outline-primary btn-sm');apply.type='submit';filters.append(apply);filters.addEventListener('submit',e=>{e.preventDefault();change(()=>getModel().setFilters({currency:currency.value,from:from.value,to:to.value},true));});
 root.append(filters,element('p','Aggregate filters: default last 30 UTC days; custom range at most 93 days through today UTC. Selected-payment facts are not date/currency filtered. Applying aggregate filters clears the selected payment and conversation. Payment searches have independent filters.','small'));
 let filterSignature=null;
 function picker(kind,labelText){
  const form=element('form',undefined,'ai-actions'),label=element('label',labelText),search=element('input');search.type='search';search.maxLength=100;search.className='form-control';label.append(search);const find=element('button',`Search ${kind}`,'btn btn-outline-primary btn-sm');find.type='submit';form.append(label,find);
  form.addEventListener('submit',e=>{e.preventDefault();void getModel()[kind==='Merchants'?'loadMerchants':'loadPayments'](search.value.trim());});
  const message=element('p');message.setAttribute('role','status');const choices=element('div');root.append(form,message,choices);
  const isMerchant=kind==='Merchants',prefix=isMerchant?'merchant':'payment';
  return {clear(){search.value='';message.textContent='';choices.replaceChildren();},render(state){
   search.disabled=find.disabled=state.busy||!state.eligible||locked();find.disabled ||= state[prefix+'Busy'];message.textContent=state[prefix+'Message'];choices.replaceChildren();const page=state[prefix+'Page'];if(!page)return;
   for(const row of page.items){const label=isMerchant?`${row.businessName||'Business name not recorded'} · ${row.merchantId} · ${row.status}`:`${row.paymentId} · ${row.merchantId} · ${row.amount} ${row.currency} · ${row.status}`;
    const b=button(`Select ${label}`,()=>change(()=>getModel()[isMerchant?'selectMerchant':'selectPayment'](row[isMerchant?'merchantId':'paymentId'],true)));b.disabled=state.busy||locked();choices.append(b);}
   const nav=element('div',undefined,'ai-actions'),load=p=>void getModel()[isMerchant?'loadMerchants':'loadPayments'](state[prefix+'Search'],p);
   const prev=button(`← Previous ${kind}`,()=>load(page.page-1)),next=button(`Next ${kind} →`,()=>load(page.page+1));prev.disabled=state.busy||state[prefix+'Busy']||page.page===0;next.disabled=state.busy||state[prefix+'Busy']||(page.page+1)*5>=page.total;nav.append(prev,element('span',`Page ${page.page+1} · ${page.total} matching ${kind}`),next);choices.append(nav);
  }};
 }
 const merchants=picker('Merchants','Find Merchant (ID, business name or registered email)'),payments=picker('Payments','Find payment (exact UUID or customer ID)');
 return {root,replaced(){merchants.clear();payments.clear();},clear(){currency.value=from.value=to.value='';filterSignature=null;merchants.clear();payments.clear();},render(state){
  selected.textContent=state.selected?`Selected payment ${state.selected.paymentId} · Merchant ${state.selected.merchantId} · ${state.selected.amount} ${state.selected.currency} · recorded ${state.selected.status}`:state.merchant?`Merchant overview: ${state.merchant.businessName||'Business name not recorded'} · ${state.merchant.merchantId} · ${state.merchant.status}`:'Platform overview: full authorized INR/USD payment and refund aggregates, never combined across currencies.';
  merchant.hidden=!state.merchant;platform.disabled=merchant.disabled=state.busy||!state.eligible||locked();
  for(const f of [currency,from,to,apply])f.disabled=state.busy||!state.eligible||locked();
  const signature=JSON.stringify(state.filters);if(signature!==filterSignature){filterSignature=signature;currency.value=state.filters.currency||'';from.value=state.filters.from?.slice(0,10)||'';to.value=state.filters.to?new Date(Date.parse(state.filters.to)-86400000).toISOString().slice(0,10):'';}
  merchants.render(state);payments.render(state);
 }};
}
export function mountAdminAI(root,options={}){return mountConversation(root,{...options,allowCancel:true,titleText:'Admin AI Assistant',titleId:'admin-ai-title',helpId:'admin-ai-help',conversationScope:s=>({portalRole:'ADMIN',context:{...(s.merchant?{merchantId:s.merchant.merchantId}:{}),...(s.selected?{paymentId:s.selected.paymentId}:{statistics:{...s.filters}})}}),modelFactory:createAdminChat,createContext:adminContext,welcome:adminSuggestions});}
