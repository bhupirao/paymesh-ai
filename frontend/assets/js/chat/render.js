import { element } from '../admin/view.js';
import { generationLabel } from '../merchant-ai/schema.js';
import { getSession } from '../auth/session.js';
export const chatButton=(label,run)=>{const b=element('button',label,'btn btn-outline-primary btn-sm');b.type='button';b.addEventListener('click',run);return b;};
const list=(host,values)=>{const entries=values.filter(value=>typeof value==='string'&&value.trim());if(!entries.length){host.append(element('p','No additional entries.'));return;}const ul=element('ul');for(const value of entries)ul.append(element('li',value));host.append(ul);};
const labels={ORIGINAL_PAYMENT:'Original payment',OBSERVED_SUCCESSFUL_REFUNDS:'Recorded refunds',REMAINING_REFUNDABLE:'Potentially refundable, subject to checks',PAYMENT_AGGREGATE:'Recorded payments',REFUND_AGGREGATE:'Recorded refunds',CHECKOUT_AMOUNT:'Link amount'};
export function technicalAllowed(){const s=getSession();return s?.accountStatus==='ACTIVE'&&s.roles.includes('ADMIN');}
export function publicAnswer(result){return /\b(Java|Python|RAG|LLM|deterministic|snapshot)\b|chat evidence contract|approved general policy/i.test(result.answer)?'This saved answer uses an older format. Review the recorded amounts below, or ask again for an updated explanation.':result.answer;}
function amounts(host,values){const facts=element('dl',undefined,'ai-money');for(const m of values){facts.append(element('dt',labels[m.kind]||'Recorded amount'),element('dd',`${m.amount} ${m.currency}${m.count==null?'':` · ${m.count} records`}`));}host.append(facts);}
export function renderAnswer(host,result,{ask=()=>{},openPayment=()=>{},canAct=()=>true,copy=async value=>navigator.clipboard.writeText(value),announce=()=>{}}={}){
 const answer=publicAnswer(result);host.append(element('p',answer,'ai-answer'));
 host.append(element('p','Recorded payments and refunds do not confirm bank settlement or money arrival.','small'));
 const copyButton=chatButton('Copy answer',async()=>{if(!canAct())return;try{await copy(answer);if(canAct())announce('Answer copied.');}catch{if(canAct())announce('Clipboard unavailable. Select and copy the answer text manually.');}});host.append(copyButton);
 const sources=element('details');sources.append(element('summary','Sources and amounts'));
 const p=result.evidenceProvenance;sources.append(element('p',`Information recorded at ${p.collectedAt}. Earlier answers may describe earlier records.`));
 if(p.statisticsRange)sources.append(element('p',`Period: ${p.statisticsRange.from} to ${p.statisticsRange.to} (UTC, end exclusive). Currencies remain separate.`));
 // Original payment/link amounts already appear in the selected context. Other values
 // are available on demand rather than repeating the answer's figures by default.
 const money=result.moneyFacts.filter(m=>!['ORIGINAL_PAYMENT','CHECKOUT_AMOUNT'].includes(m.kind));if(money.length)amounts(sources,money);
 if(!result.evidenceReferences.length)sources.append(element('p','No transaction records were cited.'));
 for(const ref of result.evidenceReferences){const row=element('p',({PAYMENT:'Payment record',REFUND:'Refund record',GATEWAY_TRANSACTION:'Gateway record',STATISTICS:'Activity totals'})[ref.resourceType]||'Recorded information');if(ref.resourceType==='PAYMENT')row.append(chatButton('Open payment',()=>{if(canAct())openPayment(ref.resourceId);}));sources.append(row);}
 for(const k of result.knowledgeReferences)sources.append(element('p',k.title));
 if(!result.knowledgeReferences.length)sources.append(element('p','No guidance documents were cited.'));host.append(sources);
 // Presentation gate only. API authorization and response metadata are unchanged.
 if(technicalAllowed()){
  const tech=element('details');tech.append(element('summary','Technical details'),element('p',generationLabel(result)),element('p',`Intent: ${result.intent} · Generation status: ${result.generationStatus} · Mode: ${result.analysisMode}`));
  if(answer!==result.answer)tech.append(element('p',result.answer));
  tech.append(element('p',`Java-authorized evidence snapshot · ${p.collectedAt} · ${p.scope}`));amounts(tech,result.moneyFacts);
  for(const ref of result.evidenceReferences)tech.append(element('p',`${ref.resourceType} · ${ref.reference}`));
  for(const k of result.knowledgeReferences){const card=element('section');card.append(element('h5',k.title),element('p',`Document: ${k.documentId} · Chunk: ${k.chunkId}`),element('p',`Retrieval relevance: ${k.score}; not a probability of correctness.`));list(card,k.sources);tech.append(card);}
  tech.append(element('h4','Limitations'));list(tech,[...new Set([...p.limitations,...result.limitations])]);host.append(tech);
 }
 const follow=element('div',undefined,'ai-actions');for(const q of result.suggestedFollowUps)follow.append(chatButton(`Ask: ${q}`,()=>{if(canAct())ask(q);}));host.append(follow);
}
