import { isUUID } from '../auth/session.js';
const modes={DETERMINISTIC:['DISABLED','NOT_ATTEMPTED','NO_RELEVANT_CONTEXT','RETRIEVAL_UNAVAILABLE'],RAG_ASSISTED:['NOT_ATTEMPTED','DISABLED','TIMEOUT','UNAVAILABLE','INVALID_RESPONSE','VALIDATION_FAILED','CONTEXT_LIMIT'],RAG_LLM:['SUCCEEDED']};
const intents=['PAYMENT_STATUS','PAYMENT_FAILURE','PROCESSING','REFUND_SUMMARY','GATEWAY','STATISTICS','CHECKOUT','KNOWLEDGE','INSUFFICIENT_EVIDENCE','UNSUPPORTED'];
const kinds=['ORIGINAL_PAYMENT','OBSERVED_SUCCESSFUL_REFUNDS','REMAINING_REFUNDABLE','PAYMENT_AGGREGATE','REFUND_AGGREGATE','CHECKOUT_AMOUNT'];
const require=value=>{if(!value)throw new Error('Invalid chat response');};
const text=(s,max)=>typeof s==='string'&&s.trim().length>0&&[...s].length<=max&&!/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(s)&&!/[\uD800-\uDFFF]/u.test(s);
const strings=(v,max,len)=>Array.isArray(v)&&v.length<=max&&v.every(s=>text(s,len));
export function validateQuestion(q){
 if(typeof q!=='string'||!q.trim()||!text(q,1000))throw new Error('Enter 1–1,000 Unicode characters; no control characters or malformed Unicode.');
 if(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|\b[A-Za-z0-9_-]{43,}\b|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b(password|secret|authorization|cookie|refresh.?token|api.?key|cvv|pin)\s*[:=]\s*\S+|\b[0-9][0-9 ()+-]{8,}[0-9]\b/i.test(q))throw new Error('Remove credentials, contact details and raw identifiers. Select an authorized payment using the context controls.');
 return q;
}
export function boundedHistory(turns){
 const out=[];let length=0;
 for(const turn of [...turns].reverse()){
  if(turn.status!=='completed')continue;
  const pair=[{role:'user',content:turn.question},{role:'assistant',content:turn.result.answer}];
  // Never truncate a financial explanation or borrow history across a missing long turn.
  if(pair.some(m=>[...m.content].length>1000)||out.length+2>8||length+pair.reduce((n,m)=>n+[...m.content].length,0)>6000)break;
  try{pair.forEach(m=>validateQuestion(m.content));}catch{break;}
  length+=pair.reduce((n,m)=>n+[...m.content].length,0);out.unshift(...pair);
 }
 return out;
}
export function makeRequest(question,turns,selected){
 validateQuestion(question);const body={question,history:boundedHistory(turns),context:selected?{paymentId:selected.paymentId.toLowerCase()}:{statistics:{}}};
 if(new TextEncoder().encode(JSON.stringify(body)).length>32768)throw new Error('Chat request exceeds the 32 KiB UTF-8 limit. Start a new conversation.');
 return body;
}
export function validateChat(data,selected){return validateScopedChat(data,selected,'MERCHANT_OWNED');}
export function validateScopedChat(data,selected,scope){
 require(data&&Object.keys(data).sort().join(',')==='analysisMode,answer,correlationId,evidenceProvenance,evidenceReferences,generationStatus,intent,knowledgeReferences,limitations,moneyFacts,suggestedFollowUps');
 require(isUUID(data.correlationId)&&text(data.answer,6000)&&intents.includes(data.intent));
 const p=data.evidenceProvenance;
 require(p&&p.source==='JAVA_AUTHORIZED_DATABASE_SNAPSHOT'&&p.scope===scope&&text(p.collectedAt,40)&&/^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/.test(p.collectedAt)&&Number.isFinite(Date.parse(p.collectedAt))&&strings(p.limitations,20,500));
 if(p.statisticsRange!=null)require(p.statisticsRange.timezone==='UTC'&&p.statisticsRange.endExclusive===true&&Number.isFinite(Date.parse(p.statisticsRange.from))&&Number.isFinite(Date.parse(p.statisticsRange.to)));
 require(modes[data.analysisMode]?.includes(data.generationStatus));
 require(Array.isArray(data.evidenceReferences)&&data.evidenceReferences.length<=66);const refs=new Set();
 for(const ref of data.evidenceReferences){require(text(ref.reference,80)&&!refs.has(ref.reference));refs.add(ref.reference);
  if(ref.resourceType==='PAYMENT')require(selected&&ref.reference==='payment:selected'&&ref.resourceId?.toLowerCase()===selected.paymentId.toLowerCase());
  else require(({REFUND:'refund:',GATEWAY_TRANSACTION:'gateway:',STATISTICS:'statistics:'})[ref.resourceType]&&ref.reference.startsWith(({REFUND:'refund:',GATEWAY_TRANSACTION:'gateway:',STATISTICS:'statistics:'})[ref.resourceType])&&ref.resourceId==null);
 }
 require(Array.isArray(data.knowledgeReferences)&&data.knowledgeReferences.length<=5);
 for(const k of data.knowledgeReferences)require(text(k.documentId,60)&&text(k.chunkId,120)&&text(k.title,120)&&strings(k.sources,5,200)&&typeof k.score==='number'&&Number.isFinite(k.score)&&k.score>=0&&k.score<=1);
 require(data.analysisMode==='DETERMINISTIC'?data.knowledgeReferences.length===0:data.knowledgeReferences.length>0);
 require(strings(data.limitations,40,600)&&strings(data.suggestedFollowUps,3,120));
 require(Array.isArray(data.moneyFacts)&&data.moneyFacts.length<=6);
 for(const m of data.moneyFacts)require(kinds.includes(m.kind)&&typeof m.amount==='string'&&/^(0|[1-9][0-9]{0,23})\.[0-9]{2}$/.test(m.amount)&&['INR','USD'].includes(m.currency)&&(m.count==null||Number.isSafeInteger(m.count)&&m.count>=0));
 return data;
}
export function generationLabel(result){return result.analysisMode==='RAG_LLM'?'Local LLM selection succeeded — not independent proof of relevance or factual correctness':result.analysisMode==='RAG_ASSISTED'?'RAG-assisted deterministic explanation — no successful LLM generation':'Deterministic explanation — no successful LLM generation';}
