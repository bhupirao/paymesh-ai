import { createPaginatedTable } from '../components/paginated-table.js';
import { createChartsPanel } from '../analytics/charts.js';
import { createAdminWorkspace, transitions } from './model.js';
import { ADMIN_PAGES } from './routes.js';
import { signOut } from '../auth/persistence.js';

const fields={merchantId:'Merchant ID',businessName:'Business',email:'Email',status:'Status',amount:'Amount',currency:'Currency',paymentId:'Payment UUID',refundId:'Refund UUID',createdAt:'Created',occurredAt:'Time',eventType:'Event',actorUserId:'Actor UUID',outcome:'Outcome',login:'Login',accountStatus:'Account status',enabled:'Enabled'};
const columns={merchants:['merchantId','businessName','email','status','createdAt'],pending:['merchantId','businessName','email','status','createdAt'],payments:['paymentId','merchantId','amount','currency','status','createdAt'],refunds:['refundId','paymentId','merchantId','amount','currency','status','createdAt'],audit:['occurredAt','eventType','actorUserId','merchantId','outcome'],accounts:['login','accountStatus','enabled','createdAt']};
export function element(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text??'Unavailable');if(cls)node.className=cls;return node;}
export function pairs(host,data){host.replaceChildren();for(const [key,value] of Object.entries(data||{})){const row=element('p');row.append(element('strong',`${fields[key]||key}: `),element('span',Array.isArray(value)?value.join(', '):value===null?'Not recorded':value));host.append(row);}}
export function mountAdmin({navigate,openPayment,financialLocked}){
  const charts=createChartsPanel({role:'admin'});
  const root=document.getElementById('admin-workspace');let state;
  const title=element('h2','Admin workspace');title.tabIndex=-1;
  const message=element('p','','admin-feedback');message.setAttribute('role','status');message.setAttribute('aria-live','polite');
  const content=element('div');root.append(title,message,content);
  const button=(label,action)=>{const b=element('button',label,'btn btn-outline-primary');b.type='button';b.addEventListener('click',action);b.disabled=Boolean(state?.pending);return b;};
  function labeled(form,label,name,type='text',value=''){
    const wrap=element('label',label,'admin-field');const input=element('input');input.name=name;input.type=type;input.value=value;input.className='form-control';input.disabled=state.pending;wrap.append(input);form.append(wrap);return input;
  }
  function table(data,keys,onRow){
    const wrap=element('div',undefined,'table-responsive');wrap.tabIndex=0;wrap.setAttribute('aria-label','Scrollable records');
    const table=element('table',undefined,'table');const head=element('thead');const tr=element('tr');
    for(const key of keys){const th=element('th',fields[key]||key);th.scope='col';tr.append(th);}if(onRow){const th=element('th','Details');th.scope='col';tr.append(th);}head.append(tr);table.append(head);
    const body=element('tbody');for(const row of data){const tr=element('tr');for(const key of keys)tr.append(element('td',row[key]??'Not recorded'));if(onRow){const td=element('td');td.append(button('Open',()=>onRow(row)));tr.append(td);}body.append(tr);}table.append(body);wrap.append(table);return wrap;
  }
  function filters(){
    const form=element('form',undefined,'admin-filter-grid');const view=state.view;
    if(view==='merchant'){
      const input=labeled(form,'Merchant ID','merchantId','text',state.filters.merchantId||state.merchantId);input.required=true;input.maxLength=100;
    }else{
      if(view!=='dashboard')labeled(form,view==='audit'?'Exact audit event':view==='accounts'?'Exact Admin login':'Search','search','search',state.filters.search||'').maxLength=100;
      if(view!=='accounts')labeled(form,'Merchant ID filter','merchantId','text',state.filters.merchantId||'').maxLength=100;
      if(['payments','refunds','dashboard'].includes(view)){
        const label=element('label','Currency','admin-field'),select=element('select');select.name='currency';select.className='form-select';
        for(const value of ['','INR','USD']){const option=element('option',value||'All currencies (separate totals)');option.value=value;select.append(option);}select.value=state.filters.currency||'';label.append(select);form.append(label);
      }
      if(['merchants','payments','refunds','dashboard'].includes(view)){
        const label=element('label','Status','admin-field'),select=element('select');select.name='status';select.className='form-select';
        const statuses=view==='merchants'?Object.keys(transitions):view==='refunds'?['SUCCESS']:['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'];
        for(const value of ['',...statuses]){const option=element('option',value||'All statuses');option.value=value;select.append(option);}select.value=state.filters.status||'';label.append(select);form.append(label);
      }
      if(view!=='accounts'){labeled(form,'From (UTC instant, optional)','from','text',state.filters.from||'').placeholder='2026-11-01T00:00:00Z';labeled(form,'To (UTC instant, optional)','to','text',state.filters.to||'').placeholder='2026-11-30T23:59:59Z';}
      if(view!=='dashboard'){const label=element('label','Order','admin-field'),select=element('select');select.name='sort';select.className='form-select';for(const value of ['newest','oldest']){const option=element('option',value);option.value=value;select.append(option);}select.value=state.filters.sort||'newest';label.append(select);form.append(label);}
    }
    const submit=element('button','Apply / Look up','btn btn-primary');submit.disabled=state.busy||state.pending;form.append(submit);
    form.addEventListener('submit',event=>{event.preventDefault();if(form.reportValidity())void model.load(view,Object.fromEntries(new FormData(form)),0);});content.append(form);
  }
  function profile(){
    const box=element('div');pairs(box,state.data);content.append(box);
    const form=element('form',undefined,'admin-filter-grid');
    const current=labeled(form,'Current password','currentPassword','password');current.autocomplete='current-password';current.required=true;
    const next=labeled(form,'New password','newPassword','password');next.autocomplete='new-password';next.required=true;
    const confirm=labeled(form,'Confirm new password','confirmPassword','password');confirm.autocomplete='new-password';confirm.required=true;
    form.append(element('p','Minimum 12 Unicode characters, maximum 72 UTF-8 bytes. Password change revokes all previous sessions and requires sign-in.'));
    const toggle=button('Show / hide passwords',()=>{const show=current.type==='password';for(const input of [current,next,confirm])input.type=show?'text':'password';toggle.setAttribute('aria-pressed',String(show));});toggle.setAttribute('aria-pressed','false');form.append(toggle);
    const submit=element('button','Change password and sign out','btn btn-primary');submit.disabled=state.pending;form.append(submit);
    form.addEventListener('submit',async event=>{event.preventDefault();if(!form.reportValidity())return;const values=[current.value,next.value,confirm.value];current.value=next.value=confirm.value='';const work=model.changePassword(...values);values.fill('');if(await work){await signOut();navigate('/admin/login');}});content.append(form);
  }
  function createAccount(){
    const form=element('form',undefined,'admin-filter-grid');form.append(element('h3','Create an additional administrator'));
    const login=labeled(form,'Admin login','login');login.required=true;login.maxLength=255;login.autocomplete='off';
    const password=labeled(form,'New Admin password','password','password');password.required=true;password.autocomplete='new-password';
    const confirm=labeled(form,'Confirm password','confirmPassword','password');confirm.required=true;confirm.autocomplete='new-password';
    const submit=element('button','Review Admin creation','btn btn-outline-primary');submit.disabled=state.pending;form.append(submit);
    form.addEventListener('submit',event=>{event.preventDefault();if(!form.reportValidity())return;
      const confirmed=window.confirm('Create an enabled ACTIVE ADMIN account for '+login.value+'? This grants administrative authority.');
      if(!confirmed)return;const values=[login.value,password.value,confirm.value];password.value=confirm.value='';void model.createAccount(...values,true);values.fill('');});content.append(form);
  }
  function merchant(){
    const box=element('div');pairs(box,state.data);content.append(box);
    if(!state.data)return;
    if(state.data.status==='PENDING_APPROVAL'&&!state.data.registrationUserId){content.append(element('p','Historical unclaimed registry: no registration profile exists. Approval actions are unavailable; use the supported reviewed provisioning procedure.'));return;}
    for(const action of transitions[state.data.status]||[]){
      const form=element('form',undefined,'admin-action-form');form.append(element('h3',action[0].toUpperCase()+action.slice(1)));
      if(action==='approve'){
        const ref=labeled(form,'External ownership review reference','reviewReference');ref.required=true;ref.maxLength=100;ref.minLength=3;
        const label=element('label','I attest that ownership was reviewed for this exact Merchant.');const check=element('input');check.name='ownershipAttested';check.type='checkbox';check.required=true;label.prepend(check);form.append(label);
      }else{const reason=labeled(form,'Required reason (1–500 characters)','reason');reason.required=true;reason.maxLength=500;}
      const review=element('button','Review '+action,'btn btn-outline-primary');review.disabled=state.pending||state.uncertain;form.append(review);
      form.addEventListener('submit',event=>{event.preventDefault();if(form.reportValidity()){const values=Object.fromEntries(new FormData(form));values.ownershipAttested=Boolean(values.ownershipAttested);if(model.review(action,values))root.querySelector('[role="dialog"]')?.focus();}});content.append(form);
    }
  }
  let pagedTables=[],tablePages=new Map(),tableScope=null;
  function clearTables(){for(const t of pagedTables)t.dispose();pagedTables=[];}
  function dashboardTable(rows,keys,label,key){
    const t=createPaginatedTable({rows,columns:keys,labels:fields,label,page:tablePages.get(key)||0,onPage:page=>tablePages.set(key,page)});
    pagedTables.push(t);return t.root;
  }
  function render(next){clearTables();charts.hide();state=next;const scope=JSON.stringify(state.filters||{});if(!state.view||state.view==='dashboard'&&scope!==tableScope){tablePages.clear();tableScope=state.view?scope:null;}root.hidden=!state.view;title.textContent=state.view?ADMIN_PAGES['/admin/'+state.view]||'Admin Dashboard':'Admin workspace';message.textContent=state.message;content.replaceChildren();content.setAttribute('aria-busy',String(state.busy||state.pending));
    if(!state.view)return;
    content.append(element('p','Simulation only. Recorded amounts do not establish bank debit, settlement or refund arrival.','small text-secondary'));
    if(state.view==='dashboard')content.append(element('p','Record summaries and charts have independent, explicitly labeled filters.'));
    if(state.view!=='profile')filters();
    content.append(button('Refresh authoritative data',()=>void model.refresh()));
    if(state.busy){content.append(element('p','Loading…'));return;}
    if(state.view==='merchant')merchant();
    else if(state.view==='profile'&&state.data)profile();
    else if(state.view==='dashboard'&&state.data){
      void charts.attach(content,state.data);
      const metrics=element('div');pairs(metrics,{totalMerchants:state.data.totalMerchants,pendingRegistrations:state.data.pendingRegistrations});content.append(metrics);
      for(const [key,label] of Object.entries({merchantCounts:'Merchant lifecycle counts (all registry records)',paymentCounts:'Payment counts (filters applied)',refundCounts:'Refund counts (filters applied)',paymentAmounts:'Recorded payment amounts by currency and status',refundAmounts:'Recorded refund amounts by currency and status',recentRegistrations:'Recent registrations (all)',recentPayments:'Recent payments (filters applied)'})){
        content.append(element('h3',label));const rows=state.data[key];if(!key.startsWith('recent')&&Array.isArray(rows)){content.append(dashboardTable(rows,Object.keys(rows[0]||{}),label,key));continue;}if(!Array.isArray(rows)||!rows.length)content.append(element('p','No records in this snapshot.'));else content.append(table(rows,Object.keys(rows[0]),key==='recentRegistrations'?row=>{model.load('merchant',{merchantId:row.merchantId});navigate('/admin/merchant');}:key==='recentPayments'?row=>openPayment(row.paymentId):undefined));
      }
    }else if(state.data?.items){
      if(!state.data.items.length)content.append(element('p','No records match the current filters.'));
      else content.append(table(state.data.items,columns[state.view],['merchants','pending'].includes(state.view)?row=>{model.load('merchant',{merchantId:row.merchantId});navigate('/admin/merchant');}:['payments','refunds'].includes(state.view)?row=>openPayment(row.paymentId):undefined));
      content.append(element('p',`Page ${state.data.page+1} · ${state.data.total} matching records`));
      const previous=button('Previous',()=>void model.load(state.view,state.filters,state.page-1));previous.disabled=state.pending||state.page===0;const next=button('Next',()=>void model.load(state.view,state.filters,state.page+1));next.disabled=state.pending||(state.page+1)*state.data.size>=state.data.total;content.append(previous,next);
    }
    if(state.view==='accounts')createAccount();
    if(state.intent){const dialog=element('section',undefined,'admin-review surface');dialog.setAttribute('role','dialog');dialog.setAttribute('aria-label','Confirm Merchant administration');dialog.tabIndex=-1;
      dialog.append(element('h3','Confirm administrative action'));const details=element('div');pairs(details,{action:state.intent.action,from:state.intent.from,...state.intent.body});dialog.append(details);
      const confirm=button('Confirm '+state.intent.action,()=>void model.confirm());dialog.append(confirm,button('Cancel review',()=>model.cancel()));content.append(dialog);
    }
  }
  const model=createAdminWorkspace(render,{financialLocked});model.start();
  return {show:path=>{root.hidden=false;const view=path.split('/').pop();if(view==='dashboard'&&model.state().view===view)void charts.attach(content,state.data);else void model.show(view);},hide(){charts.hide();root.hidden=true;},pending:model.pending,clear:model.reset};
}
