import { request } from '../api/client.js';
import { getSession,getVersion,subscribe,checkExpiry,isUUID } from '../auth/session.js';
import { query,validatePage } from '../admin/model.js';
import { customRange } from '../analytics/charts.js';
import { boundedHistory,validateQuestion,validateScopedChat } from '../merchant-ai/schema.js';
import { chatFeedback } from '../merchant-ai/model.js';
const merchantID=id=>typeof id==='string'&&/^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$/.test(id);
const allowed=()=>{checkExpiry();const s=getSession();return s?.accountStatus==='ACTIVE'&&s.roles.includes('ADMIN');};
export function adminStatisticsFilters(input={}){
 if(!input||typeof input!=='object'||Array.isArray(input)||!Object.keys(input).every(k=>['currency','from','to'].includes(k))||input.currency&&!['INR','USD'].includes(input.currency)||Boolean(input.from)!==Boolean(input.to))throw new Error('Select INR/USD and both UTC dates, or leave both dates empty.');
 const out=input.currency?{currency:input.currency}:{};
 if(input.from){const range=customRange(input.from,input.to);const now=new Date(),tomorrow=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()+1);if(Date.parse(range.to)>tomorrow)throw new Error('Statistics must end no later than today UTC.');Object.assign(out,range);}
 return out;
}
export function adminChatRequest(question,turns,merchant,selected,filters){
 validateQuestion(question);
 if(!filters||typeof filters!=='object'||Array.isArray(filters)||!Object.keys(filters).every(k=>['currency','from','to'].includes(k))||filters.currency&&!['INR','USD'].includes(filters.currency)||Boolean(filters.from)!==Boolean(filters.to)||filters.from&&(!Number.isFinite(Date.parse(filters.from))||!Number.isFinite(Date.parse(filters.to))))throw new Error('Invalid aggregate context.');
 if(merchant&&!merchantID(merchant.merchantId))throw new Error('Select an authorized Merchant.');
 if(selected&&(!isUUID(selected.paymentId)||!merchantID(selected.merchantId)||merchant&&selected.merchantId!==merchant.merchantId))throw new Error('Payment and Merchant context do not match.');
 const context={...(merchant?{merchantId:merchant.merchantId}:{}),...(selected?{paymentId:selected.paymentId.toLowerCase()}:{statistics:{...filters}})};
 const body={question,history:boundedHistory(turns),context};if(new TextEncoder().encode(JSON.stringify(body)).length>32768)throw new Error('Chat request exceeds the 32 KiB UTF-8 limit. Start New Chat.');return body;
}
function pageData(data,kind,page,merchant){
 validatePage(data);if(data.page!==page||data.size!==5||data.items.length>5||data.total<data.items.length)throw new Error();const seen=new Set();
 const items=data.items.map(row=>{
  if(!merchantID(row.merchantId)||seen.has(kind==='merchants'?row.merchantId:row.paymentId))throw new Error();seen.add(kind==='merchants'?row.merchantId:row.paymentId);
  if(kind==='merchants'){
   if(!['PENDING_APPROVAL','ACTIVE','REJECTED','SUSPENDED'].includes(row.status)||row.businessName!=null&&(typeof row.businessName!=='string'||row.businessName.length>160))throw new Error();
   return {merchantId:row.merchantId,businessName:row.businessName??null,status:row.status};
  }
  if(!isUUID(row.paymentId)||merchant&&merchant.merchantId!==row.merchantId||typeof row.amount!=='string'||!/^(0|[1-9][0-9]{0,11})\.[0-9]{2}$/.test(row.amount)||!['INR','USD'].includes(row.currency)||!['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'].includes(row.status)||!Number.isFinite(Date.parse(row.createdAt)))throw new Error();
  return {paymentId:row.paymentId.toLowerCase(),merchantId:row.merchantId,amount:row.amount,currency:row.currency,status:row.status};
 });return {page:data.page,size:5,total:data.total,items};
}
export function createAdminChat(onChange,{api=request,locked=()=>false,onBusy=()=>{},managed=false}={}){
 let generation=0,profileSeq=0,merchantSeq=0,paymentSeq=0,controller,disposed=false;
 const initial=()=>({eligible:false,checking:false,merchant:null,selected:null,filters:{},turns:[],busy:false,startedAt:null,phase:'welcome',message:'Choose platform overview, an authorized Merchant or a payment. No AI request runs automatically.',failedQuestion:'',merchantPage:null,merchantBusy:false,merchantSearch:'',merchantMessage:'',paymentPage:null,paymentBusy:false,paymentSearch:'',paymentMessage:''});
 let state=initial();const emit=()=>{if(!disposed)onChange(structuredClone(state));};
 function busy(value){const changed=state.busy!==value;state.busy=value;if(changed)onBusy(value);}
 function invalidate(){generation++;controller?.abort();controller=null;busy(false);state.startedAt=null;}
 function clear(){invalidate();profileSeq++;merchantSeq++;paymentSeq++;state=initial();if(!allowed()){state.phase='unauthorized';state.message='Sign in with a current ACTIVE authorized Admin account.';}emit();}
 const off=subscribe(clear),valid=(g,v)=>!disposed&&g===generation&&v===getVersion()&&allowed();
 function lost(error){clear();state.phase='unauthorized';state.message=chatFeedback(error,'Admin');emit();}
 async function activate(){
  if(!allowed()){clear();return false;}if(state.eligible||state.checking)return state.eligible;
  const seq=++profileSeq,v=getVersion();state.checking=true;state.message='Checking current Admin authorization…';emit();
  try{const p=await api('/admin/profile');if(disposed||seq!==profileSeq||v!==getVersion()||!allowed())return false;
   if(!p||p.userId!==getSession().subject||p.enabled!==true||p.accountStatus!=='ACTIVE'||!Array.isArray(p.roles)||!p.roles.includes('ADMIN')||p.roles.some(r=>!['ADMIN','MERCHANT'].includes(r)))throw new Error();
   state.eligible=true;state.message='Ready. Platform overview uses full authorized INR/USD aggregates in the declared UTC window, not recent-record previews.';return true;
  }catch(e){if(seq===profileSeq&&v===getVersion()){lost({status:403});}return false;}
  finally{if(seq===profileSeq&&v===getVersion()){state.checking=false;emit();}}
 }
 async function load(kind,search='',page=0){
  if(!allowed()||!state.eligible||state.busy||locked()||!['merchants','payments'].includes(kind)||typeof search!=='string'||search.length>100||/[\x00-\x1f\x7f]/.test(search)||!Number.isInteger(page)||page<0||page>10000)return false;
  const isMerchant=kind==='merchants',prefix=isMerchant?'merchant':'payment',seq=isMerchant?++merchantSeq:++paymentSeq,v=getVersion(),merchant=structuredClone(state.merchant);
  state[prefix+'Busy']=true;state[prefix+'Page']=null;state[prefix+'Search']=search;state[prefix+'Message']='Loading authorized choices…';emit();
  try{const data=await api('/admin/'+kind+query({page,size:5,sort:'newest',...(search?{search}:{}),...(!isMerchant&&merchant?{merchantId:merchant.merchantId}:{})}));
   if(disposed||seq!==(isMerchant?merchantSeq:paymentSeq)||v!==getVersion()||!allowed())return false;
   state[prefix+'Page']=pageData(data,kind,page,merchant);state[prefix+'Message']=data.items.length?'Choose explicitly. Java reauthorizes every context on every question.':'No matching authorized choices.';return true;
  }catch(e){if(seq===(isMerchant?merchantSeq:paymentSeq)&&v===getVersion()){if([401,403].includes(e.status))lost(e);else state[prefix+'Message']='Choices are unavailable or inconsistent. Current context was not changed.';}return false;}
  finally{if(seq===(isMerchant?merchantSeq:paymentSeq)&&v===getVersion()){state[prefix+'Busy']=false;emit();}}
 }
 function replace(confirmed,apply){
  if(!allowed()||!state.eligible||locked()&&!state.busy)return false;
  if((state.turns.length||state.busy)&&!confirmed)return false;
  invalidate();merchantSeq++;paymentSeq++;state.merchantPage=null;state.merchantBusy=false;state.merchantSearch='';state.merchantMessage='';state.paymentPage=null;state.paymentBusy=false;state.paymentSearch='';state.paymentMessage='';
  state.turns=[];state.failedQuestion='';state.phase='welcome';state.message='Context replaced. Previous history and any pending response were invalidated. No AI request was sent.';apply();emit();return true;
 }
 function selectMerchant(id,confirmed=false){
  if(id==null)return replace(confirmed,()=>{state.merchant=null;state.selected=null;});
  const row=state.merchantPage?.items.find(m=>m.merchantId===id);if(!row)return false;
  return replace(confirmed,()=>{state.merchant=structuredClone(row);state.selected=null;});
 }
 function selectPayment(id,confirmed=false){
  if(id==null)return replace(confirmed,()=>{state.selected=null;});
  const row=state.paymentPage?.items.find(p=>p.paymentId===id?.toLowerCase());if(!row||state.merchant&&row.merchantId!==state.merchant.merchantId)return false;
  return replace(confirmed,()=>{state.selected=structuredClone(row);});
 }
 function setFilters(input,confirmed=false){let filters;try{filters=adminStatisticsFilters(input);}catch(e){state.message=e.message;emit();return false;}return replace(confirmed,()=>{state.filters=filters;state.selected=null;});}
 function cancel(){if(!state.busy)return false;const turn=state.turns.at(-1);invalidate();if(turn?.status==='sending'){turn.status='failed';turn.result=null;state.failedQuestion=turn.question;}state.phase='failed';state.message='Cancelled the browser wait. Server analysis may still finish. Its reply will be ignored; any retry requires an explicit action.';emit();return true;}
 function restart(){invalidate();merchantSeq++;paymentSeq++;const eligibility=state.eligible;state=initial();state.eligible=eligibility;state.message='New platform conversation. Previous responses will be ignored; server analysis may still finish.';emit();}
 async function send(question){
  if(!allowed()||!state.eligible||state.busy||locked()||!managed&&state.turns.length>=20&&!(state.turns.at(-1)?.status==='failed'&&state.turns.at(-1)?.question===question))return false;
  let body;try{body=adminChatRequest(question,state.turns,state.merchant,state.selected,state.filters);}catch(e){state.message=e.message;emit();return false;}
  const g=++generation,v=getVersion(),selected=structuredClone(state.selected);controller=new AbortController();const signal=controller.signal;
  let turn=state.turns.at(-1);if(!turn||turn.status!=='failed'||turn.question!==question){turn={question,status:'sending',result:null};state.turns.push(turn);}else turn.status='sending';
  busy(true);state.phase='sending';state.startedAt=Date.now();state.failedQuestion='';state.message='Collecting authorized Admin evidence and performing local analysis. No automatic retries.';emit();
  try{const data=await api('/admin/ai/chat',{method:'POST',body,signal});if(!valid(g,v))return false;let result;try{result=validateScopedChat(data,selected,'ADMIN_AUTHORIZED');}catch{throw {reason:'schema'};}
   turn.status='completed';turn.result=result;state.phase=result.intent==='INSUFFICIENT_EVIDENCE'?'insufficient':'completed';state.message=state.phase==='insufficient'?'More evidence or explicit context is needed. No facts were invented.':'Dated authorized analysis received. Read its limitations; this is not permission to act.';return true;
  }catch(e){if(!valid(g,v))return false;if([401,403,404].includes(e.status)){lost(e);return false;}turn.status='failed';state.failedQuestion=question;state.phase=e.code==='AI_UNAVAILABLE'?'disabled-or-unavailable':'failed';state.message=chatFeedback(e,'Admin');return false;
  }finally{if(valid(g,v)){controller=null;busy(false);state.startedAt=null;emit();}}
 }
 function forget(){invalidate();state.turns=[];state.failedQuestion='';state.phase='welcome';state.message='Conversation cleared; current authorized context is unchanged.';emit();}
 function restore(data){if(!allowed()||!state.eligible||data.conversation.portalRole!=='ADMIN')return false;invalidate();merchantSeq++;paymentSeq++;state.merchant=data.conversation.context.merchantId?data.conversation.merchant:null;state.selected=data.conversation.payment;state.filters=data.conversation.context.statistics||{};state.turns=data.completed;state.failedQuestion='';state.merchantPage=state.paymentPage=null;state.merchantBusy=state.paymentBusy=false;state.merchantSearch=state.paymentSearch='';state.phase='completed';state.message='Historical saved answers restored; no fresh inference was invoked.';emit();return true;}
 return {forget,restore,activate,loadMerchants:(s,p)=>load('merchants',s,p),loadPayments:(s,p)=>load('payments',s,p),selectMerchant,selectPayment,setFilters,send,cancel,retry:()=>state.failedQuestion?send(state.failedQuestion):Promise.resolve(false),restart,clear,busy:()=>state.busy,state:()=>structuredClone(state),dispose(){clear();disposed=true;off();}};
}
