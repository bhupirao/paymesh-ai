import { createPaginatedTable } from '../components/paginated-table.js';
import { request } from '../api/client.js';
import { getVersion,subscribe } from '../auth/session.js';
const palette=['#2563eb','#0f766e','#d97706','#b91c1c','#7c3aed','#475569'];
const labels={currency:'Currency',status:'Status',count:'Count',amount:'Recorded amount',paymentAmount:'Recorded payment amount',refundAmount:'Recorded refund amount',date:'UTC day',paymentMethod:'Payment method'};
const statusColors={CREATED:'#2563eb',PROCESSING:'#d97706',SUCCESS:'#0f766e',FAILED:'#b91c1c',CANCELLED:'#475569',REFUNDED:'#7c3aed',ACTIVE:'#0f766e',PENDING_APPROVAL:'#d97706',REJECTED:'#b91c1c',SUSPENDED:'#475569'};
const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
export function rangePreset(name,now=new Date()){
  const end=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate()+1));
  const days=({today:1,week:7,month:30})[name];if(!days)throw new Error('Select an explicit range');
  return {from:new Date(end.getTime()-days*86400000).toISOString(),to:end.toISOString()};
}
export function customRange(from,to){
  if(!/^\d{4}-\d\d-\d\d$/.test(from)||!/^\d{4}-\d\d-\d\d$/.test(to))throw new Error('Invalid dates');
  const first=new Date(from+'T00:00:00Z'),last=new Date(to+'T00:00:00Z');
  if(first.toISOString().slice(0,10)!==from||last.toISOString().slice(0,10)!==to||last<first||last-first>=93*86400000)throw new Error('Range must be 1–93 UTC days');
  return {from:first.toISOString(),to:new Date(last.getTime()+86400000).toISOString()};
}
export function validateAnalytics(d){
  if(!d||d.range?.timezone!=='UTC'||d.range?.endExclusive!==true||!Number.isFinite(Date.parse(d.range.from))||!Number.isFinite(Date.parse(d.range.to)))throw new Error();
  for(const key of ['paymentCounts','refundCounts','dailyPayments','paymentMethods','amountComparison'])if(!Array.isArray(d[key])||d[key].length>400)throw new Error();
  for(const key of ['paymentCounts','refundCounts','dailyPayments','paymentMethods'])for(const r of d[key])if(!['INR','USD'].includes(r.currency)||!Number.isSafeInteger(r.count)||r.count<0)throw new Error();
  for(const r of d.amountComparison)if(!['INR','USD'].includes(r.currency)||!['paymentAmount','refundAmount'].every(k=>typeof r[k]==='string'&&/^\d+(?:\.\d+)?$/.test(r[k])))throw new Error();
  for(const r of d.dailyPayments)if(!/^\d{4}-\d\d-\d\d$/.test(r.date)||typeof r.amount!=='string'||!/^\d+(?:\.\d+)?$/.test(r.amount))throw new Error();
  for(const r of d.paymentCounts)if(!['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'].includes(r.status))throw new Error();
  for(const r of d.refundCounts)if(r.status!=='SUCCESS')throw new Error();
  for(const r of d.paymentMethods)if(typeof r.paymentMethod!=='string'||!r.paymentMethod||r.paymentMethod.length>100)throw new Error();
  if(d.merchantCounts&&(!Array.isArray(d.merchantCounts)||d.merchantCounts.some(r=>!['PENDING_APPROVAL','ACTIVE','REJECTED','SUSPENDED'].includes(r.status)||!Number.isSafeInteger(r.count)||r.count<0)))throw new Error();
  return d;
}
export function createChartsPanel({role,api=request,ChartClass=globalThis.Chart}={}){
  const root=node('section');root.className='analytics-panel';let seq=0,instances=[],tables=[],pages=new Map(),tableScope=null,attached=false,inFlightKey=null,existing={},filters={currency:'INR',...rangePreset('month')};
  const destroy=()=>{for(const chart of instances)chart.destroy();instances=[];for(const table of tables)table.dispose();tables=[];};
  const clear=()=>{seq++;inFlightKey=null;existing={};destroy();root.replaceChildren();attached=false;};const resetSession=()=>{clear();pages.clear();tableScope=null;filters={currency:'INR',...rangePreset('month')};};const unsubscribe=subscribe(resetSession);
  function fallback(host,rows,keys,title){
    const details=node('details');details.open=true;details.append(node('summary','Accessible data table (exact values)'));
    const table=createPaginatedTable({rows,columns:keys,labels,label:title,page:pages.get(title)||0,onPage:page=>pages.set(title,page)});
    tables.push(table);details.append(table.root);host.append(details);
  }
  function chart(grid,title,type,rows,labelKey,valueKeys,keys){
    const card=node('section');card.className='surface analytics-card';card.append(node('h3',title));
    const positive=rows.some(r=>valueKeys.some(k=>Number(r[k])>0));
    const finite=rows.every(r=>valueKeys.every(k=>Number.isFinite(Number(r[k]))));
    if(positive&&finite&&ChartClass){
      const frame=node('div');frame.className='chart-frame';const canvas=node('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',title+'. Equivalent exact data in the table below.');canvas.append(node('p','See the equivalent data table.'));frame.append(canvas);card.append(frame);
      try{instances.push(new ChartClass(canvas,{type,data:{labels:rows.map(r=>r[labelKey]),datasets:valueKeys.map((key,i)=>({label:labels[key]||key,data:rows.map(r=>Number(r[key])),backgroundColor:type==='doughnut'?rows.map((r,j)=>statusColors[r[labelKey]]||palette[j%palette.length]):palette[i],borderColor:palette[i],borderWidth:type==='line'?2:0,tension:0.2}))},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{position:'bottom'}},...(type==='doughnut'?{cutout:'68%'}:{scales:{y:{beginAtZero:true}}})}}));}catch{frame.replaceChildren(node('p','Graph unavailable; exact data remains below.'));}
    }else card.append(node('p',positive?'Graph unavailable or value outside visualization range; exact data remains below.':'No activity in this range.'));
    fallback(card,rows,keys,title);grid.append(card);
  }
  async function load(){
    const key=JSON.stringify([filters.from,filters.to,filters.currency,filters.merchantId||'']);if(inFlightKey===key)return false;inFlightKey=key;if(tableScope!==key){pages.clear();tableScope=key;}
    const current=++seq,version=getVersion();destroy();root.replaceChildren();root.setAttribute('aria-busy','true');
    const title=node('h2','Dashboard analytics · UTC');root.append(title);controls();const status=node('p','Loading complete authorized analytics…');status.setAttribute('role','status');root.append(status);
    try{
      const p=new URLSearchParams(filters);const data=validateAnalytics(await api('/'+role+'/analytics?'+p));
      if(current!==seq||version!==getVersion()||!attached)return false;
      if(role==='admin'&&Array.isArray(existing.merchantCounts))data.merchantCounts=existing.merchantCounts;existing={};
      validateAnalytics(data);
      if(role==='admin'&&!Array.isArray(data.merchantCounts))throw new Error();
      if(data.range.from!==new Date(filters.from).toISOString().replace('.000Z','Z')&&Date.parse(data.range.from)!==Date.parse(filters.from))throw new Error();
      if(Date.parse(data.range.to)!==Date.parse(filters.to))throw new Error();
      status.textContent='All records in the selected UTC range, not a recent-page sample. Charts are approximate visualizations; exact amounts are in the tables. Recorded amounts include all payment states, not settlement/revenue. Refunds use their own creation time and actual refund status.';
      const grid=node('div');grid.className='analytics-grid';root.append(grid);
      if(role==='admin')chart(grid,'Merchant lifecycle · all registry records','doughnut',data.merchantCounts||[],'status',['count'],['status','count']);
      const selected=key=>data[key].filter(r=>r.currency===filters.currency);
      chart(grid,'Payment status · '+filters.currency,'doughnut',selected('paymentCounts'),'status',['count'],['currency','status','count']);
      chart(grid,'Daily payment volume · counts · '+filters.currency,'line',selected('dailyPayments'),'date',['count'],['date','currency','count','amount']);
      chart(grid,'Recorded payments versus refunds · '+filters.currency,'bar',selected('amountComparison'),'currency',['paymentAmount','refundAmount'],['currency','paymentAmount','refundAmount']);
      if(role==='merchant')chart(grid,'Payment method · '+filters.currency,'doughnut',selected('paymentMethods'),'paymentMethod',['count'],['currency','paymentMethod','count']);
      return true;
    }catch{if(current===seq&&version===getVersion())status.textContent='Analytics unavailable or invalid. No partial graph shown. Check the range (1–93 UTC days, no future days) and refresh explicitly.';return false;}
    finally{if(current===seq&&version===getVersion()){inFlightKey=null;root.setAttribute('aria-busy','false');}}
  }
  function controls(){
    const f=node('form');f.className='admin-filter-grid';
    function input(label,type,value){const l=node('label',label),i=node('input');i.type=type;i.value=value;i.className='form-control';l.append(i);f.append(l);return i;}
    const from=input('Start day (UTC)','date',filters.from.slice(0,10));const to=input('End day inclusive (UTC)','date',new Date(Date.parse(filters.to)-86400000).toISOString().slice(0,10));
    const label=node('label','Chart currency'),currency=node('select');currency.className='form-select';for(const c of ['INR','USD']){const o=node('option',c);o.value=c;currency.append(o);}currency.value=filters.currency;label.append(currency);f.append(label);
    let merchant;if(role==='admin')merchant=input('Merchant ID (charts only, optional)','text',filters.merchantId||'');
    const custom=node('button','Apply custom range / refresh');custom.className='btn btn-primary';f.append(custom);
    f.addEventListener('submit',e=>{e.preventDefault();try{filters={...customRange(from.value,to.value),currency:currency.value,...(merchant?.value?{merchantId:merchant.value}:{})};void load();}catch{root.append(node('p','Choose a valid range of 1–93 UTC days.'));}});
    for(const [key,text] of [['today','Today'],['week','Last 7 Days'],['month','Last 30 Days']]){const b=node('button',text);b.type='button';b.className='btn btn-outline-primary';b.addEventListener('click',()=>{filters={...rangePreset(key),currency:currency.value,...(merchant?.value?{merchantId:merchant.value}:{})};void load();});f.append(b);}root.append(f);
  }
  return {root,attach(host,available={}){attached=true;existing=available;host.append(root);return load();},hide:clear,refresh:load,filters:()=>({...filters}),dispose(){resetSession();unsubscribe();}};
}
