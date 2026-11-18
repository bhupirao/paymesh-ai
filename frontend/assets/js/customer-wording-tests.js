import { renderAnswer } from './chat/render.js';
import { setSession,clearSession } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
import { publicChatFixture } from './merchant-ai-test-fixtures.js';
const checks=[];const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label);};
const reply=()=>({...structuredClone(publicChatFixture),answer:'No refunds have been recorded for this payment. The total refunded amount is $0.00, and $25.00 remains potentially eligible for refund, subject to verification.',moneyFacts:[{kind:'ORIGINAL_PAYMENT',amount:'25.00',currency:'USD',count:null},{kind:'OBSERVED_SUCCESSFUL_REFUNDS',amount:'0.00',currency:'USD',count:null},{kind:'REMAINING_REFUNDABLE',amount:'25.00',currency:'USD',count:null}],intent:'REFUND_SUMMARY'});
try{
 setSession(tokenResponse(['MERCHANT']),'wording-merchant');const host=document.createElement('section');let copied='';renderAnswer(host,reply(),{copy:async value=>copied=value});
 assert(host.children[0].textContent.startsWith('No refunds'),'answer precedes metadata');
 assert(!host.textContent.includes('REFUND_SUMMARY')&&!host.textContent.includes('Generation status')&&!host.textContent.includes('Java'),'Merchant view hides technical implementation');
 assert(![...host.querySelectorAll('summary')].some(n=>n.textContent==='Technical details'),'Merchant has no technical section');
 assert(host.textContent.includes('Recorded refunds')&&host.textContent.includes('Potentially refundable, subject to checks'),'friendly monetary labels');
 assert(!host.textContent.includes('Original payment'),'selected original payment is not repeated');
 assert(host.textContent.includes('0.00 USD')&&host.textContent.includes('25.00 USD'),'exact monetary strings retained');
 assert(host.textContent.includes('do not confirm bank settlement or money arrival'),'recorded refund is not bank settlement');
 [...host.querySelectorAll('button')].find(n=>n.textContent==='Copy answer').click();await Promise.resolve();assert(copied===reply().answer,'copy contains customer wording only');
 setSession(tokenResponse(['ADMIN']),'wording-admin');const admin=document.createElement('section');renderAnswer(admin,reply());const tech=[...admin.querySelectorAll('details')].find(n=>n.querySelector('summary')?.textContent==='Technical details');
 assert(tech&&!tech.open,'Admin technical section is collapsed');assert(tech.textContent.includes('REFUND_SUMMARY')&&tech.textContent.includes('Generation status'),'technical intent and generation metadata retained');assert(tech.textContent.includes('Original payment'),'complete technical monetary facts retained');
 const legacy={...reply(),answer:'Java deterministic snapshot REFUND_SUMMARY'};const old=document.createElement('section');renderAnswer(old,legacy);assert(old.children[0].textContent.includes('older format')&&!old.children[0].textContent.includes('Java'),'legacy answer safely separated without rewriting records');
 clearSession('wording-test');const noSession=document.createElement('section');renderAnswer(noSession,reply());assert(!noSession.textContent.includes('Generation status'),'no technical details without active Admin session');
 const empty={...reply(),moneyFacts:[],evidenceReferences:[],knowledgeReferences:[],limitations:['',' ']};const blank=document.createElement('section');renderAnswer(blank,empty);assert(!blank.querySelector('li')&&!blank.querySelector('h4'),'empty metadata does not create headings or bullets');
 const hostile={...reply(),answer:'<img src=x onerror=alert(1)>'};const safe=document.createElement('section');renderAnswer(safe,hostile);assert(!safe.querySelector('img')&&safe.textContent.includes('<img'),'untrusted text stays literal');
 document.getElementById('summary').textContent=`PASS: ${checks.length} assertions`;
}catch(e){document.getElementById('summary').textContent='FAIL: '+e.message;throw e;}finally{clearSession('wording-test-cleanup');}
