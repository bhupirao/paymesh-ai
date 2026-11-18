import { element } from '../admin/view.js';
import { createMerchantChat } from './model.js';
import { mountConversation } from '../chat/presentation.js';
import { chatButton as button } from '../chat/render.js';
export { renderAnswer } from '../chat/render.js';
export const WELCOME=['Summarize payment statistics','What is idempotency?','How does checkout handle a timeout?'];
function merchantContext({getModel,change,locked}){
 const root=element('section',undefined,'ai-context');root.setAttribute('aria-label','Conversation context');
 const selected=element('p'),overview=button('Use overview context',()=>change(()=>getModel().select(null,true)));
 const form=element('form',undefined,'ai-actions'),label=element('label','Find an authorized payment (exact UUID or customer ID)'),search=element('input');search.className='form-control';search.type='search';search.maxLength=100;label.append(search);
 const find=element('button','Search payments','btn btn-outline-primary btn-sm');find.type='submit';form.append(label,find);form.addEventListener('submit',e=>{e.preventDefault();void getModel().loadPayments(search.value.trim());});
 const message=element('p');message.setAttribute('role','status');const choices=element('div');root.append(element('h3','Context'),selected,overview,form,message,choices);
 return {root,clear(){search.value='';choices.replaceChildren();},render(state){
  selected.textContent=state.selected?`Selected payment ${state.selected.paymentId} · ${state.selected.amount} ${state.selected.currency} · recorded ${state.selected.status}`:(state.savedStatistics&&Object.keys(state.savedStatistics).length?('Saved overview filters: '+JSON.stringify(state.savedStatistics)+'. '):'')+'Overview: current authorized last-30-UTC-day payment/refund aggregates; INR and USD separated. Select a payment for its status, gateway or refund explanation.';
  overview.disabled=find.disabled=search.disabled=state.busy||!state.eligible||locked();find.disabled ||= state.listBusy;message.textContent=state.listMessage;choices.replaceChildren();
  if(state.page){for(const p of state.page.items){const b=button(`Select ${p.paymentId} · ${p.amount} ${p.currency} · ${p.status}`,()=>change(()=>getModel().select(p.paymentId,true)));b.disabled=state.busy||locked();choices.append(b);}
   const nav=element('div',undefined,'ai-actions'),prev=button('← Previous payments',()=>void getModel().loadPayments(state.search,state.page.page-1)),next=button('Next payments →',()=>void getModel().loadPayments(state.search,state.page.page+1));prev.disabled=state.listBusy||state.busy||state.page.page===0;next.disabled=state.listBusy||state.busy||(state.page.page+1)*5>=state.page.total;nav.append(prev,element('span',`Page ${state.page.page+1} · ${state.page.total} matching records`),next);choices.append(nav);}
 }};
}
export function mountMerchantAI(root,options={}){return mountConversation(root,{...options,titleText:'Merchant AI Assistant',titleId:'merchant-ai-title',helpId:'merchant-ai-help',conversationScope:s=>({portalRole:'MERCHANT',context:s.selected?{paymentId:s.selected.paymentId}:{statistics:{...(s.savedStatistics||{})}}}),modelFactory:createMerchantChat,createContext:merchantContext,welcome:()=>WELCOME});}
