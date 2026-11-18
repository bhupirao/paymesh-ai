import { mountMerchantAI } from '../merchant-ai/view.js';
import { mountLinks } from '../payment-links/view.js';
import { createPaginatedTable } from '../components/paginated-table.js';
import { createChartsPanel } from '../analytics/charts.js';
import { createMerchantWorkspace } from './model.js';
import { MERCHANT_PAGES } from './routes.js';
import { element,pairs } from '../admin/view.js';
import { signOut } from '../auth/persistence.js';
export function mountMerchant({navigate,openPayment,financialLocked,onChatBusy=()=>{}}){
  const linksRoot=document.getElementById('merchant-links-workspace');linksRoot.hidden=true;const links=mountLinks(linksRoot,{navigate,openPayment,financialLocked});
  let chat;const ai=()=>chat??=mountMerchantAI(document.getElementById('merchant-ai-workspace'),{openPayment,locked:financialLocked,onBusy:onChatBusy});
  const charts=createChartsPanel({role:'merchant'});
  const root=document.getElementById('merchant-workspace');let state,visible=false;
  const labels={merchantId:'Merchant ID',accountStatus:'Account status',businessStatus:'Business status',merchantVerified:'Ownership verified',merchantActive:'Merchant active',membershipActive:'Membership active',merchantCreatedAt:'Registry created',approvedAt:'Approved',businessName:'Business name',email:'Registered email',firstName:'First name',lastName:'Last name',mobile:'Mobile',businessType:'Business type',country:'Country',registeredAt:'Registered',registrationAvailable:'Registration profile available',login:'Login',paymentId:'Payment UUID',refundId:'Refund UUID',customerId:'Customer ID',createdAt:'Created',amount:'Amount',currency:'Currency',status:'Status',count:'Count'};
  const profilePairs=(host,data)=>pairs(host,Object.fromEntries(Object.entries(data).map(([k,v])=>[labels[k]||k,typeof v==='boolean'?(v?'Yes':'No'):v])));
  const title=element('h2','Merchant workspace');title.tabIndex=-1;
  const message=element('p');message.setAttribute('role','status');message.setAttribute('aria-live','polite');const content=element('div');root.append(title,message,content);
  const button=(label,action)=>{const b=element('button',label,'btn btn-outline-primary');b.type='button';b.disabled=state?.pending||false;b.addEventListener('click',action);return b;};
  function field(form,label,name,type='text',value=''){const wrap=element('label',label,'admin-field'),input=element('input');input.type=type;input.name=name;input.value=value;input.className='form-control';input.disabled=state.pending;wrap.append(input);form.append(wrap);return input;}
  function table(rows,keys,open=false){
    if(!rows.length)return element('p','No matching records in this authorized snapshot.');
    const wrap=element('div',undefined,'table-responsive');wrap.tabIndex=0;wrap.setAttribute('aria-label','Scrollable Merchant records');const t=element('table',undefined,'table');const head=element('thead'),tr=element('tr');
    for(const key of [...keys,...(open?['Details']:[])]){const th=element('th',labels[key]||key);th.scope='col';tr.append(th);}head.append(tr);t.append(head);const body=element('tbody');
    for(const row of rows){const tr=element('tr');for(const key of keys)tr.append(element('td',row[key]??'Not recorded'));if(open){const td=element('td');td.append(button('Open payment',()=>openPayment(row.paymentId)));tr.append(td);}body.append(tr);}t.append(body);wrap.append(t);return wrap;
  }
  function filters(){
    const f=element('form',undefined,'admin-filter-grid');
    if(state.view!=='dashboard'){field(f,'Exact Payment UUID or Customer ID','search','search',state.filters.search||'').maxLength=100;
      const label=element('label','Status','admin-field'),select=element('select');select.name='status';select.className='form-select';for(const v of ['',...(state.view==='refunds'?['SUCCESS']:['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'])]){const o=element('option',v||'All statuses');o.value=v;select.append(o);}select.value=state.filters.status||'';label.append(select);f.append(label);
    }
    const label=element('label','Currency','admin-field'),select=element('select');select.name='currency';select.className='form-select';for(const v of ['','INR','USD']){const o=element('option',v||'All currencies (separate totals)');o.value=v;select.append(o);}select.value=state.filters.currency||'';label.append(select);f.append(label);
    field(f,'From (optional UTC instant)','from','text',state.filters.from||'').placeholder='2026-11-01T00:00:00Z';field(f,'To (optional UTC instant)','to','text',state.filters.to||'').placeholder='2026-11-30T23:59:59Z';
    if(state.view!=='dashboard'){const label=element('label','Order','admin-field'),s=element('select');s.name='sort';s.className='form-select';for(const v of ['newest','oldest']){const o=element('option',v);o.value=v;s.append(o);}s.value=state.filters.sort||'newest';label.append(s);f.append(label);}
    const submit=element('button','Apply filters','btn btn-primary');submit.disabled=state.pending||state.busy;f.append(submit);f.addEventListener('submit',e=>{e.preventDefault();if(f.reportValidity())void model.load(state.view,Object.fromEntries(new FormData(f)));});content.append(f);
  }
  function security(){
    const f=element('form',undefined,'admin-filter-grid');const current=field(f,'Current password','currentPassword','password');current.autocomplete='current-password';current.required=true;
    const next=field(f,'New password','newPassword','password');next.autocomplete='new-password';next.required=true;const confirm=field(f,'Confirm new password','confirmPassword','password');confirm.autocomplete='new-password';confirm.required=true;
    f.append(element('p','Minimum 12 Unicode code points, maximum 72 UTF-8 bytes. Changing your password revokes all previous sessions; fresh sign-in is required. ACTIVE verified Merchants only.'));
    const toggle=button('Show / hide passwords',()=>{const show=current.type==='password';for(const input of [current,next,confirm])input.type=show?'text':'password';toggle.setAttribute('aria-pressed',String(show));});toggle.setAttribute('aria-pressed','false');f.append(toggle);
    const submit=element('button','Review password change','btn btn-primary');submit.disabled=state.pending||state.uncertain;f.append(submit);
    f.addEventListener('submit',async e=>{e.preventDefault();if(!f.reportValidity())return;if(!window.confirm('Change your Merchant password, revoke previous sessions and require fresh sign-in?'))return;
      const values=[current.value,next.value,confirm.value];current.value=next.value=confirm.value='';const work=model.changePassword(...values,true);values.fill('');if(await work){await signOut();navigate('/merchant/login');const feedback=document.getElementById('login-feedback');if(feedback)feedback.textContent='Password changed successfully. Sign in again. Previous sessions have been revoked.';}});content.append(f);
  }
  let pagedTables=[],tablePages=new Map(),tableScope=null;
  function clearTables(){for(const t of pagedTables)t.dispose();pagedTables=[];}
  function dashboardTable(rows,keys,label,key){
    const t=createPaginatedTable({rows,columns:keys,labels:labels,label,page:tablePages.get(key)||0,onPage:page=>tablePages.set(key,page)});
    pagedTables.push(t);return t.root;
  }
  function render(next){clearTables();charts.hide();state=next;const scope=JSON.stringify(state.filters||{});if(!state.view||state.view==='dashboard'&&scope!==tableScope){tablePages.clear();tableScope=state.view?scope:null;}root.hidden=!visible||!state.view;title.textContent=MERCHANT_PAGES['/merchant/'+state.view]||'Merchant workspace';message.textContent=state.message;content.replaceChildren();content.setAttribute('aria-busy',String(state.busy||state.pending));if(!state.view)return;
    content.append(element('p','Simulated payment records only. Totals are not available balance, revenue, bank settlement or refund arrival.','small text-secondary'));
    if(state.view==='dashboard')content.append(element('p','Record summaries and charts have independent, explicitly labeled filters.'));
    if(['dashboard','payments','refunds'].includes(state.view))filters();content.append(button('Refresh authorized snapshot',()=>void model.refresh()));
    if(state.uncertain)content.append(element('p','A prior password-change outcome remains unconfirmed. Do not resubmit. Sign in manually to establish account state.'));
    if(state.busy){content.append(element('p','Loading…'));return;}if(!state.data)return;
    if(state.view==='profile'){const box=element('div');profilePairs(box,state.data);content.append(box);if(!state.data.registrationAvailable)content.append(element('p','This provisioned Merchant has no registration profile. Missing business/contact details are not recorded.'));}
    else if(state.view==='security')security();
    else if(state.view==='dashboard'){
      void charts.attach(content);
      const cards=element('div',undefined,'merchant-metrics');const metric=element('section',undefined,'surface');metric.append(element('h3','Payments in selected scope'),element('p',state.data.totalPayments));cards.append(metric);const refundMetric=element('section',undefined,'surface');refundMetric.append(element('h3','Refund records in selected scope'),element('p',state.data.refundCounts.reduce((n,r)=>n+BigInt(r.count),0n).toString()));cards.append(refundMetric);for(const row of state.data.paymentAmounts){const card=element('section',undefined,'surface');card.append(element('h3',row.currency+' · '+row.status),element('p',row.amount),element('p','Recorded payment amount'));cards.append(card);}content.append(cards);
      const identity=element('div');profilePairs(identity,state.data.profile);content.append(identity);
      for(const [key,label] of [['paymentCounts','Payment counts'],['refundCounts','Refund counts'],['paymentAmounts','Recorded payment amounts'],['refundAmounts','Recorded refund amounts']]){content.append(element('h3',label));content.append(dashboardTable(state.data[key],key.endsWith('Amounts')?['currency','status','amount']:['status','count'],label,key));}
      content.append(element('h3','Recent payments'),table(state.data.recentPayments,['paymentId','amount','currency','status','createdAt'],true),element('h3','Recent refunds'),table(state.data.recentRefunds,['refundId','paymentId','amount','currency','status','createdAt'],true));
    }else{
      content.append(table(state.data.items,state.view==='payments'?['paymentId','customerId','amount','currency','status','createdAt']:['refundId','paymentId','amount','currency','status','createdAt'],true));
      content.append(element('p',`Page ${state.data.page+1} · ${state.data.total} matching records`));const prev=button('Previous',()=>void model.load(state.view,state.filters,state.page-1));prev.disabled=state.pending||state.page===0;const next=button('Next',()=>void model.load(state.view,state.filters,state.page+1));next.disabled=state.pending||(state.page+1)*state.data.size>=state.data.total;content.append(prev,next);
    }
  }
  const model=createMerchantWorkspace(render,{financialLocked});model.start();return {show:path=>{if(path==='/merchant/ai'){links.hide();charts.hide();root.hidden=true;ai().show();return true;}chat?.clear();chat?.hide();if(path.startsWith('/merchant/payment-links')){charts.hide();root.hidden=true;return links.show(path);}links.hide();visible=true;root.hidden=false;return model.show(path.split('/').pop());},hide(){chat?.hide();links.hide();charts.hide();visible=false;root.hidden=true;for(const input of root.querySelectorAll('input[autocomplete="current-password"],input[autocomplete="new-password"]'))input.value='';},clearChat:()=>chat?.clear(),chatBusy:()=>Boolean(chat?.busy()),pending:()=>model.pending()||links.pending()||Boolean(chat?.busy()),dispose(){chat?.dispose();links.dispose();linksRoot.replaceChildren();charts.dispose();model.reset();model.dispose();root.replaceChildren();}};
}
