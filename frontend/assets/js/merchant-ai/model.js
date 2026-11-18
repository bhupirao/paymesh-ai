import { request } from '../api/client.js';
import { getSession,getVersion,subscribe,checkExpiry } from '../auth/session.js';
import { validateMerchantData } from '../merchant/model.js';
import { query } from '../admin/model.js';
import { makeRequest,validateChat } from './schema.js';
export function chatFeedback(error,role='Merchant'){
 if(error.reason==='invalid_json'||error.reason==='schema')return 'The AI response could not be validated. No partial answer is displayed.';
 if(error.reason==='timeout'||error.status===504)return 'The request timed out. Server analysis may still be completing; browser cancellation does not stop it. Retry only deliberately.';
 if(error.code==='AI_CAPACITY')return 'AI capacity is busy. Wait, then retry explicitly. No automatic retry was made.';
 if(error.code==='AI_UNAVAILABLE')return 'AI chat is disabled or unavailable. Operator activation may be pending. No answer was generated.';
 return ({400:'The question or context was rejected. Remove secrets and identifiers or start a new chat.',401:`Sign in again to use ${role} AI.`,403:`${role} authorization is unavailable. Private chat was cleared.`,404:'The selected payment is unavailable or inaccessible. Select an authorized context again.',413:'The request is too large. Start a new chat.',415:'The service rejected the request format.',422:'The authorized evidence is unsupported, inconsistent or too large. No financial total was guessed.',429:'Request limit reached. Wait before explicitly retrying.',502:'The AI service response was unavailable or invalid. No partial answer is displayed.',503:'AI chat is unavailable or busy. Wait before explicitly retrying.'})[error.status]||'Unable to reach AI chat. The request may still be completing. Retry only deliberately.';
}
const eligible=()=>{checkExpiry();const s=getSession();return s?.roles.join(',')==='MERCHANT'&&s.accountStatus==='ACTIVE';};
export function createMerchantChat(onChange,{api=request,locked=()=>false,onBusy=()=>{},managed=false}={}){
 let generation=0,profileSeq=0,listSeq=0,controller,disposed=false;
 let state;const initial=()=>({eligible:false,checking:false,merchantId:null,selected:null,savedStatistics:null,turns:[],busy:false,startedAt:null,phase:'welcome',message:'Select overview or an authorized payment, then ask a question explicitly.',failedQuestion:'',page:null,listBusy:false,search:'',listMessage:''});
 state=initial();const emit=()=>{if(!disposed)onChange(structuredClone(state));};
 const busy=value=>{const changed=state.busy!==value;state.busy=value;if(changed)onBusy(value);};
 function invalidate(){generation++;controller?.abort();controller=null;busy(false);state.startedAt=null;}
 function clear(reason='cleared'){invalidate();profileSeq++;listSeq++;state=initial();state.phase=eligible()?'welcome':'unauthorized';state.message=eligible()?'Conversation cleared. No request was sent.':'Sign in with an ACTIVE authorized Merchant account.';emit();}
 const off=subscribe(()=>clear('session-change'));
 const valid=(g,v)=>!disposed&&g===generation&&v===getVersion()&&eligible();
 function restart(){invalidate();listSeq++;state={...state,selected:null,savedStatistics:null,turns:[],failedQuestion:'',phase:'welcome',message:'New conversation. Earlier requests may still finish on the server; their results will be ignored.',page:null,search:'',listBusy:false,listMessage:''};emit();}
 async function activate(){if(!eligible()){clear();return false;}if(state.eligible||state.checking)return state.eligible;const seq=++profileSeq,v=getVersion();state.checking=true;state.message='Checking current Merchant workspace eligibility…';emit();
  try{const profile=validateMerchantData('profile',await api('/merchant/profile'));if(disposed||seq!==profileSeq||v!==getVersion()||!eligible())return false;state.eligible=true;state.merchantId=profile.merchantId;state.phase='welcome';state.message='Ready. Overview uses current authorized last-30-UTC-day INR/USD statistics. Payment context uses its current evidence snapshot.';return true;
  }catch(e){if(seq===profileSeq&&v===getVersion()){clear();state.phase='unauthorized';state.message='Merchant workspace eligibility could not be confirmed. No chat request was sent.';emit();}return false;}
  finally{if(seq===profileSeq&&v===getVersion()){state.checking=false;emit();}}
 }
 async function loadPayments(search='',page=0){
  if(!eligible()||!state.eligible||state.busy||locked()||!Number.isInteger(page)||page<0||page>10000||typeof search!=='string'||search.length>100||/[\x00-\x1f\x7f]/.test(search))return false;
  const seq=++listSeq,v=getVersion();state.listBusy=true;state.listMessage='Loading authorized payment choices…';state.page=null;state.search=search;emit();
  try{const data=validateMerchantData('payments',await api('/merchant/payments'+query({page,size:5,sort:'newest',...(search?{search}:{})})));if(seq!==listSeq||v!==getVersion()||!eligible()||disposed)return false;if(data.items.length>5||data.page!==page||data.size!==5)throw new Error();state.page=data;state.listMessage=data.items.length?'Select a payment explicitly. Access is checked for every question.':'No matching authorized payments.';return true;
  }catch(e){if(seq===listSeq&&v===getVersion()){if(e.status===401||e.status===403)clear();else state.listMessage='Payment choices are unavailable. No context was changed.';}return false;}
  finally{if(seq===listSeq&&v===getVersion()){state.listBusy=false;emit();}}
 }
 function select(paymentId,confirmed=false){
  if(!eligible()||!state.eligible||locked()&&!state.busy)return false;
  const next=paymentId==null?null:state.page?.items.find(p=>p.paymentId.toLowerCase()===paymentId.toLowerCase());if(paymentId!=null&&!next)return false;
  if((state.selected?.paymentId||null)===(next?.paymentId||null))return true;
  if((state.turns.length||state.busy)&&!confirmed)return false;
  invalidate();state.savedStatistics=null;state.selected=next?{paymentId:next.paymentId.toLowerCase(),amount:next.amount,currency:next.currency,status:next.status}:null;state.turns=[];state.failedQuestion='';state.phase='welcome';state.message='Context replaced; previous conversation cleared. No AI request was sent.';emit();return true;
 }
 async function send(question){
  if(!eligible()||!state.eligible||state.busy||locked()||(!managed&&state.turns.length>=20&&!(state.turns.at(-1)?.status==='failed'&&state.turns.at(-1)?.question===question)))return false;
  let body;try{body=makeRequest(question,state.turns,state.selected);if(managed&&!state.selected&&state.savedStatistics)body.context={statistics:{...state.savedStatistics}};}catch(e){state.message=e.message;emit();return false;}
  const g=++generation,v=getVersion(),selected=structuredClone(state.selected);controller=new AbortController();const signal=controller.signal;
  let turn=state.turns.at(-1);if(!turn||turn.status!=='failed'||turn.question!==question){turn={question,status:'sending',result:null};state.turns.push(turn);}else turn.status='sending';
  busy(true);state.phase='sending';state.startedAt=Date.now();state.failedQuestion='';state.message='Collecting authorized evidence and analyzing locally may take several seconds. No automatic retries.';emit();
  try{const data=await api('/merchant/ai/chat',{method:'POST',body,signal});if(!valid(g,v))return false;let result;try{result=validateChat(data,selected);}catch{throw {reason:'schema'};}turn.status='completed';turn.result=result;state.phase=result.intent==='INSUFFICIENT_EVIDENCE'?'insufficient':'completed';state.message=result.intent==='INSUFFICIENT_EVIDENCE'?'More context is needed. Read the returned limitations.':'Analysis received. Facts describe the dated authorized snapshot, not a financial instruction.';return true;
  }catch(error){if(!valid(g,v))return false;
   if([401,403,404].includes(error.status)){invalidate();state={...initial(),phase:'unauthorized',message:chatFeedback(error)};return false;}
   turn.status='failed';state.phase=error.code==='AI_UNAVAILABLE'?'disabled-or-unavailable':'failed';state.failedQuestion=question;state.message=chatFeedback(error);return false;
  }finally{if(valid(g,v)){controller=null;busy(false);state.startedAt=null;emit();}else if(state.phase==='unauthorized')emit();}
 }
 function forget(){invalidate();state.turns=[];state.failedQuestion='';state.phase='welcome';state.message='Conversation cleared; current authorized context is unchanged.';emit();}
 function restore(data){if(!eligible()||!state.eligible||data.conversation.portalRole!=='MERCHANT'||data.conversation.merchantId!==state.merchantId)return false;invalidate();listSeq++;state.selected=data.conversation.payment;state.savedStatistics=data.conversation.context.statistics||null;state.turns=data.completed;state.failedQuestion='';state.page=null;state.listBusy=false;state.search='';state.phase='completed';state.message='Historical saved answers restored. Current payment facts are reauthorized on the next question.';emit();return true;}
 return {forget,restore,activate,send,loadPayments,select,restart,clear,busy:()=>state.busy,state:()=>structuredClone(state),dispose(){clear();disposed=true;off();},retry:()=>state.failedQuestion?send(state.failedQuestion):Promise.resolve(false)};
}
