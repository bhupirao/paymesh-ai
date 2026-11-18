import { request } from '../api/client.js';
import { decimal } from '../api/decimal.js';
import { getSession,getVersion,subscribe,isUUID } from '../auth/session.js';
export const statuses=['ACTIVE','CANCELLED','EXPIRED','PAID','PROCESSING'];
export function linkInput(raw){
  const r={amount:decimal(raw.amount),currency:raw.currency,paymentMethod:raw.paymentMethod,customerReference:raw.customerReference?.trim()||'',description:raw.description?.trim()||'',expiryHours:Number(raw.expiryHours)};
  if(!['INR','USD'].includes(r.currency)||!['CARD','UPI'].includes(r.paymentMethod)||r.currency==='USD'&&r.paymentMethod==='UPI'||![1,24,168].includes(r.expiryHours)||r.customerReference.length>100||r.description.length>500||/[\x00-\x1f\x7f\uD800-\uDFFF]/u.test(r.customerReference+r.description))throw new Error('Invalid link fields.');return Object.freeze(r);
}
export function validateLink(r,detail=false){
  if(!r||!isUUID(r.linkId)||typeof r.merchantId!=='string'||!r.merchantId||!statuses.includes(r.status)||decimal(r.amount)!==r.amount||!Number.isFinite(Date.parse(r.createdAt))||!Number.isFinite(Date.parse(r.updatedAt))||!Number.isFinite(Date.parse(r.expiresAt))||Date.parse(r.expiresAt)<=Date.parse(r.createdAt)||typeof r.customerReference!=='string'||r.customerReference.length>100||typeof r.description!=='string'||r.description.length>500||(r.status==='PAID'?!isUUID(r.paymentId):r.paymentId!==null))throw new Error('Invalid link response');
  linkInput({...r,expiryHours:1});if(r.gatewayName!==(r.currency==='INR'?'MOCK_RAZORPAY':'MOCK_STRIPE'))throw new Error();
  if(detail&&!/^\/checkout\/[A-Za-z0-9_-]{43}$/.test(r.checkoutPath))throw new Error();return r;
}
const feedback=e=>({400:'Check payment link fields.',401:'Sign in again.',403:'Merchant authorization denied.',404:'Payment link unavailable.',409:'Conflict. Refresh the link; do not resubmit blindly.',413:'Request too large.',415:'JSON request format required.',422:'Link request cannot be accepted.',429:'Request limit reached. Wait before retrying.'}[e.status]||'Outcome unavailable or uncertain. No automatic retry.');
export function createLinks(onChange,{api=request,locked=()=>false,random=()=>crypto.randomUUID()}={}){
  let state={items:[],total:0,page:0,filters:{},selected:null,review:null,busy:false,mutating:false,uncertain:false,cancelUncertain:false,message:''},seq=0,intent=null;
  const emit=()=>onChange({...state});const allowed=()=>getSession()?.roles.join(',')==='MERCHANT'&&getSession()?.accountStatus==='ACTIVE';
  const reset=()=>{seq++;intent=null;state={items:[],total:0,page:0,filters:{},selected:null,review:null,busy:false,mutating:false,uncertain:false,cancelUncertain:false,message:''};emit();};const off=subscribe(reset);
  const current=(n,v)=>n===seq&&v===getVersion();
  async function read(id=null,filters=state.filters,page=state.page){
    if(!allowed()||state.mutating)return false;const n=++seq,v=getVersion();state.busy=true;state.message='Loading authorized links…';state.selected=null;if(!id)state.items=[];emit();
    try{const q=new URLSearchParams({...Object.fromEntries(Object.entries(filters).filter(([,v])=>v)),page:String(page),size:'5'});const r=await api('/merchant/payment-links'+(id?'/'+id:'?'+q));if(!current(n,v))return false;
      if(id){validateLink(r,true);if(r.linkId!==id)throw new Error();state.selected=r;state.cancelUncertain=false;}else{if(!Array.isArray(r.items)||r.page!==page||r.size!==5||!Number.isSafeInteger(r.total)||r.total<0||r.items.length>5)throw new Error();r.items.forEach(x=>validateLink(x));const last=Math.max(0,Math.ceil(r.total/5)-1);if(page>last)return await read(null,filters,last);state.items=r.items;state.total=r.total;state.page=page;state.filters={...filters};}state.message='Authorized snapshot. Checkout execution requires explicit customer confirmation. Simulation only.';return true;
    }catch(e){if(current(n,v))state.message=feedback(e);return false;}finally{if(current(n,v)){state.busy=false;emit();}}
  }
  return {read,state:()=>({...state}),pending:()=>state.mutating||state.uncertain||state.cancelUncertain,
    review(raw){if(!allowed()||state.busy||state.mutating||state.uncertain||locked())return false;try{state.review=linkInput(raw);state.message='Review this simulated checkout link. No payment will be created.';emit();return true;}catch{state.message='Use a positive amount with at most 12 integer and 2 fractional digits, valid currency/method and bounded text.';emit();return false;}},
    newIntent(){if(state.mutating||state.uncertain||state.cancelUncertain)return false;seq++;state.busy=false;intent=null;state.review=null;state.selected=null;state.message='New link intent.';emit();return true;},
    async confirm(){
      if(!allowed()||state.mutating||state.busy||locked()||!state.review)return false;
      if(!intent)intent=Object.freeze({body:state.review,key:random()});const n=++seq,v=getVersion();state.mutating=true;state.message='Creating link. No automatic retry.';emit();
      try{const r=await api('/merchant/payment-links',{method:'POST',body:intent.body,idempotencyKey:intent.key,exactPayment:true,withStatus:true});if(!current(n,v))return false;
        if(![200,201].includes(r.status))throw new Error();validateLink(r.data,true);if(Date.parse(r.data.expiresAt)-Date.parse(r.data.createdAt)!==intent.body.expiryHours*3600000)throw new Error();for(const k of ['amount','currency','paymentMethod','customerReference','description'])if(r.data[k]!==intent.body[k])throw new Error();
        state.selected=r.data;state.review=null;state.uncertain=false;intent=null;state.message=r.status===200?'Original link recovered (idempotent replay).':'Payment link created. No financial payment was created.';return true;
      }catch(e){if(current(n,v)){state.uncertain=!e.status||e.status>=500||e.status===200||e.status===201;state.message=state.uncertain?'Creation outcome uncertain. Deliberately retry this exact intent with its original key. Refresh/logout loses memory-only recovery; inspect your links before another creation.':feedback(e);}return false;}
      finally{if(current(n,v)){state.mutating=false;emit();}}
    },
    async cancel(confirmed=false){
      if(!allowed()||!confirmed||state.mutating||state.busy||state.uncertain||state.cancelUncertain||locked()||state.selected?.status!=='ACTIVE')return false;
      const selected=state.selected,id=selected.linkId,n=++seq,v=getVersion();state.mutating=true;state.message='Cancelling link. No automatic retry.';emit();
      try{const r=await api('/merchant/payment-links/'+id+'/cancel',{method:'POST'});if(!current(n,v))return false;validateLink(r,true);if(r.linkId!==id||r.status!=='CANCELLED'||['merchantId','amount','currency','paymentMethod','gatewayName','checkoutPath'].some(k=>r[k]!==selected[k]))throw new Error();state.selected=r;state.message='Link cancelled.';return true;}
      catch(e){if(current(n,v)){state.cancelUncertain=!e.status||e.status>=500||e.status===200;state.message=state.cancelUncertain?'Cancellation unconfirmed. Refresh authoritative link details before considering another action.':feedback(e);}return false;}
      finally{if(current(n,v)){state.mutating=false;emit();}}
    },reset,dispose(){reset();off();}
  };
}
