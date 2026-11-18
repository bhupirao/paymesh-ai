import { request } from '../api/client.js';
import { checkExpiry,getSession,getVersion,subscribe } from '../auth/session.js';
import { validatePayment } from '../features/workspace.js';
import { decimal } from '../api/decimal.js';
import { boundedHistory,validateQuestion,validateScopedChat } from '../merchant-ai/schema.js';
import { chatFeedback } from '../merchant-ai/model.js';
export function paymentRole(){checkExpiry();const s=getSession();if(s?.accountStatus!=='ACTIVE')return null;return s.roles.includes('ADMIN')?'ADMIN':s.roles.join(',')==='MERCHANT'?'MERCHANT':null;}
export function paymentChatRequest(question,turns){validateQuestion(question);const body={question,history:boundedHistory(turns)};if(new TextEncoder().encode(JSON.stringify(body)).length>32768)throw new Error('Chat request exceeds 32 KiB UTF-8. Start New Chat.');return body;}
export function paymentSuggestions(state){const status=state.payment?.status;return ['What is this payment\'s recorded status?',...(status==='PROCESSING'?['Why is this payment processing?']:status==='FAILED'?['Why did this payment fail?']:[]),'What about the gateway?','How much was refunded?',"What is this payment's recorded refundable amount?"];}
export function createPaymentChat(onChange,{api=request,locked=()=>false,onBusy=()=>{},managed=false}={}){
 const initial=()=>({open:false,eligible:false,checking:false,payment:null,role:null,turns:[],busy:false,phase:'welcome',startedAt:null,failedQuestion:'',message:'Open Ask AI from an authorized selected payment. No automatic request.'});
 let state=initial(),context=null,signature='',generation=0,controller,denied=null,disposed=false;
 const emit=()=>{if(!disposed)onChange(structuredClone(state));};
 function busy(value){const changed=state.busy!==value;state.busy=value;if(changed)onBusy(value);}
 function invalidate(){generation++;controller?.abort();controller=null;busy(false);state.startedAt=null;}
 function close(){generation++;controller?.abort();controller=null;const wasBusy=state.busy;state=initial();state.message=wasBusy?'Ask AI closed. Server analysis may still finish; its reply will be ignored.':'Ask AI closed. Conversation cleared.';if(wasBusy)onBusy(false);emit();}
 function leave(){context=null;signature='';close();}
 const off=subscribe(()=>{denied=null;leave();});
 const ready=()=>Boolean(context?.ready&&context.version===getVersion()&&context.role===paymentRole());
 const valid=(g,v,id,role)=>!disposed&&g===generation&&v===getVersion()&&state.open&&state.payment?.paymentId===id&&role===paymentRole()&&context?.payment?.paymentId===id;
 function cancel(message='Browser wait cancelled. Server analysis may still finish. Its reply will be ignored; retry only deliberately.'){
  if(!state.busy)return false;const turn=state.turns.at(-1);invalidate();if(turn?.status==='sending'){turn.status='failed';turn.result=null;state.failedQuestion=turn.question;}state.phase='failed';state.message=message;emit();return true;
 }
 function observe(details){
  let payment=null;const role=paymentRole(),version=getVersion();try{if(role&&!details.accessDenied&&!(denied&&denied.version===version&&denied.id===details.selected&&!(details.authorizationRead>denied.read))&&details.payment&&details.selected){const p=validatePayment(details.payment,details.selected);if(typeof p.amount!=='string'||!['INR','USD'].includes(p.currency))throw new Error();payment={paymentId:p.paymentId.toLowerCase(),merchantId:p.merchantId,amount:decimal(p.amount),currency:p.currency,paymentMethod:p.paymentMethod,status:p.status};}}catch{/* No unverified detail can become a chat scope. */}
  const next={payment,role,version,read:details.authorizationRead||0,ready:Boolean(payment&&!details.loading),blocked:Boolean(details.intent)};
  const key=JSON.stringify([payment?.paymentId,payment?.merchantId,role,version]);const changed=key!==signature;signature=key;const previous=context;context=next;
  if(changed||!payment){if(state.open||state.turns.length||state.busy)close();return;}
  if(state.open){const dataChanged=JSON.stringify(previous?.payment)!==JSON.stringify(payment);const reading=previous?.ready&&!next.ready;
   if((dataChanged||reading)&&state.busy)cancel('Payment details changed or are refreshing. The old reply is ignored; earlier answers remain dated snapshots. Retry only after the authorized read completes.');
   state.payment=structuredClone(payment);if(!next.ready)state.message='Payment details are refreshing. Sending is paused; earlier answers remain dated snapshots.';else if(dataChanged)state.message='Recorded payment details changed. Earlier answers describe earlier snapshots; the next question uses fresh payment records.';emit();}
 }
 function open(){if(!ready()||context.blocked||locked())return false;if(state.open)return true;state={...initial(),open:true,eligible:true,payment:structuredClone(context.payment),role:context.role,message:'Ask explicitly about this authorized payment. Earlier answers are dated snapshots; Records are checked for every question. Checkout/link association is not supplied by this payment-only endpoint.'};emit();return true;}
 function restart(){if(!state.open)return;invalidate();state={...initial(),open:true,eligible:true,payment:structuredClone(context?.payment||state.payment),role:state.role,message:'New conversation for this payment. Previous replies are ignored; server analysis may still finish. No request was sent.'};emit();}
 async function send(question){
  if(!state.open||!state.eligible||!ready()||context.blocked||locked()||state.busy||!managed&&state.turns.length>=20&&!(state.turns.at(-1)?.status==='failed'&&state.turns.at(-1)?.question===question))return false;
  let body;try{body=paymentChatRequest(question,state.turns);}catch(e){state.message=e.message;emit();return false;}
  const g=++generation,v=getVersion(),id=context.payment.paymentId,role=context.role;controller=new AbortController();const signal=controller.signal;
  let turn=state.turns.at(-1);if(!turn||turn.status!=='failed'||turn.question!==question){turn={question,status:'sending',result:null};state.turns.push(turn);}else turn.status='sending';
  state.phase='sending';state.startedAt=Date.now();state.failedQuestion='';state.message='Reading fresh authorized payment evidence and analyzing locally. No automatic retries.';busy(true);emit();
  try{const data=await api(`/payments/${id}/ai/chat`,{method:'POST',body,signal});if(!valid(g,v,id,role))return false;let result;try{result=validateScopedChat(data,{paymentId:id},role==='ADMIN'?'ADMIN_AUTHORIZED':'MERCHANT_OWNED');}catch{throw {reason:'schema'};}
   turn.status='completed';turn.result=result;state.phase=result.intent==='INSUFFICIENT_EVIDENCE'?'insufficient':'completed';state.message=state.phase==='insufficient'?'The selected payment evidence is insufficient for this question. Read the returned limitations.':'Dated answer received. It does not replace the authoritative payment/refund status or authorize any action.';return true;
  }catch(e){if(!valid(g,v,id,role))return false;if([401,403,404].includes(e.status)){denied={version:v,id,read:context?.read||0};leave();state.phase='unauthorized';state.message=chatFeedback(e,role==='ADMIN'?'Admin':'Merchant');emit();return false;}turn.status='failed';state.failedQuestion=question;state.phase=e.code==='AI_UNAVAILABLE'?'disabled-or-unavailable':'failed';state.message=chatFeedback(e,role==='ADMIN'?'Admin':'Merchant');return false;
  }finally{if(valid(g,v,id,role)){controller=null;busy(false);state.startedAt=null;emit();}}
 }
 function restore(data){if(!state.open||!ready()||data.conversation.portalRole!==state.role||data.conversation.context.paymentId!==state.payment.paymentId||data.conversation.context.merchantId||data.conversation.context.statistics)return false;invalidate();state.turns=data.completed;state.failedQuestion='';state.phase='completed';state.message='Historical same-payment answers restored. They are not a new investigation.';emit();return true;}
 return {forget:restart,restore,observe,open,close,leave,clear:close,restart,cancel,send,retry:()=>state.failedQuestion?send(state.failedQuestion):Promise.resolve(false),activate:async()=>state.open,ready,busy:()=>state.busy,canOpen:()=>ready()&&!context.blocked&&!locked(),state:()=>structuredClone(state),dispose(){leave();disposed=true;off();}};
}
