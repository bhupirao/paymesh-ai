import { createPaginatedTable } from './components/paginated-table.js';
import { createChartsPanel } from './analytics/charts.js';
import { setSession,clearSession } from './auth/session.js';
import { tokenResponse } from './test-fixtures.js';
const results=[],assert=(v,label)=>{if(!v)throw new Error(label);results.push(label);};
let panel;const controls=[];const fixture=document.getElementById('fixture');
const rows=Array.from({length:30},(_,i)=>({date:`Day ${i+1}`,amount:'9007199254740993.01',count:i<25?1:0}));
const make=opts=>{const t=createPaginatedTable(opts);controls.push(t);fixture.append(t.root);return t;};
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
try{
  const original=JSON.stringify(rows);const table=make({rows,columns:['date','count','amount'],label:'Daily payment volume'});
  assert(table.snapshot().pages===6,'30 rows produce six pages');assert(table.snapshot().rows.length===5,'at most five rows');assert(table.indicator.textContent==='1 / 6','initial page indicator');assert(table.previous.disabled&&!table.next.disabled,'initial edge buttons');assert(table.announcement.textContent.includes('Showing 1–5 of 30'),'first record range');
  table.next.click();assert(table.snapshot().page===1,'next arrow navigates');assert(table.snapshot().rows[0].date==='Day 6'&&table.snapshot().rows[4].date==='Day 10','only selected rows rendered');assert(table.announcement.textContent.includes('Showing 6–10 of 30'),'next range announced');
  table.previous.click();assert(table.snapshot().page===0&&table.previous.disabled,'previous returns first page');
  table.go(5);assert(table.next.disabled&&!table.previous.disabled,'last edge buttons');assert(table.indicator.textContent==='6 / 6','last page indicator');assert(table.snapshot().rows[4].count===0,'zero-count days retained');assert(!table.nextPage(),'no page beyond last');assert(table.previousPage(),'previous helper navigates');
  assert(table.previous.getAttribute('aria-label').includes('Previous page'),'previous accessible name');assert(table.next.getAttribute('aria-label').includes('Next page'),'next accessible name');assert(table.announcement.getAttribute('aria-live')==='polite'&&table.announcement.getAttribute('aria-atomic')==='true','screen reader announcements');assert(table.previous.type==='button'&&table.next.type==='button','buttons cannot submit surrounding filters');
  assert(table.body.textContent.includes('9007199254740993.01'),'exact decimal text retained');assert(JSON.stringify(rows)===original,'source data unchanged by paging');
  const partial=make({rows:rows.slice(0,12),columns:['date']});partial.go(2);assert(partial.snapshot().rows.length===2,'final partial page');assert(partial.snapshot().start===11&&partial.snapshot().end===12,'partial page range');
  const small=make({rows:rows.slice(0,5),columns:['date']});assert(small.controls.hidden,'five rows hide controls');assert(small.snapshot().rows.length===5,'five rows shown');small.setRows(rows.slice(0,3));assert(small.controls.hidden&&small.snapshot().total===3,'fewer than five hide controls');
  const empty=make({rows:[],columns:['date']});assert(empty.controls.hidden&&empty.previous.disabled&&empty.next.disabled,'empty controls disabled and hidden');assert(empty.root.textContent.includes('No records in this authorized range.'),'existing empty message');assert(empty.snapshot().pages===0&&empty.snapshot().rows.length===0,'no invented empty row');
  table.go(4);partial.go(1);assert(table.snapshot().page===4&&partial.snapshot().page===1,'independent table state');table.setRows(rows.slice(0,12));assert(table.snapshot().page===2&&table.snapshot().rows.length===2,'refresh clamps invalid page');table.setRows(rows.slice(0,11));assert(table.snapshot().page===2,'refresh retains still-valid page');table.setRows(rows.slice(0,11),{reset:true});assert(table.snapshot().page===0,'explicit reset first page');
  const unsafe=make({rows:[{text:'<img src=x onerror=alert(1)>'}],columns:['text'],label:'<script>unsafe</script>'});assert(unsafe.body.textContent.includes('<img')&&!unsafe.root.querySelector('img'),'safe text rendering');
  let rejected=false;try{createPaginatedTable({pageSize:6});}catch{rejected=true;}assert(rejected,'page size cannot exceed five');assert(!table.go(NaN),'invalid index rejected');
  unsafe.dispose();assert(unsafe.snapshot().total===0&&unsafe.root.textContent==='','disposed table clears private rows');assert(!unsafe.nextPage(),'disposed controls inert');
  setSession(tokenResponse(['MERCHANT']),'synthetic');let calls=0,plots=[],destroyed=0,allStatuses=true;
  const dataFor=path=>{
    const p=new URL('http://test.invalid'+path).searchParams,from=p.get('from'),to=p.get('to'),currency=p.get('currency');const count=(Date.parse(to)-Date.parse(from))/86400000,nonzero=Math.max(0,count-5);
    return {range:{from,to,timezone:'UTC',endExclusive:true},paymentCounts:allStatuses?['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'].map((status,i)=>({currency,status,count:Math.floor(nonzero/6)+(i<nonzero%6?1:0)})).filter(r=>r.count>0):[{currency,status:'SUCCESS',count:nonzero}],refundCounts:[{currency,status:'SUCCESS',count:1}],paymentMethods:[{currency,paymentMethod:'CARD',count:nonzero}],amountComparison:[{currency,paymentAmount:nonzero+'.00',refundAmount:'0.01'}],dailyPayments:Array.from({length:count},(_,i)=>({date:new Date(Date.parse(from)+i*86400000).toISOString().slice(0,10),currency,count:i<nonzero?1:0,amount:i<nonzero?'1.00':'0.00'}))};
  };
  class Plot{constructor(canvas,config){plots.push(config);}destroy(){destroyed++;}}
  panel=createChartsPanel({role:'merchant',ChartClass:Plot,api:async path=>{calls++;return dataFor(path);}});
  await panel.attach(fixture);
  const buttons=(name)=>Array.from(panel.root.querySelectorAll('button')).filter(b=>(b.getAttribute('aria-label')||'').includes(name));
  const dailyNext=()=>buttons('Next page · Daily payment volume')[0];const statusNext=()=>buttons('Next page · Payment status')[0];
  const dailyTable=()=>Array.from(panel.root.querySelectorAll('section')).find(n=>n.getAttribute('aria-label')?.startsWith('Daily payment volume'));
  const statusTable=()=>Array.from(panel.root.querySelectorAll('section')).find(n=>n.getAttribute('aria-label')?.startsWith('Payment status'));
  const line=plots.find(p=>p.type==='line'),beforeChart=JSON.stringify(line.data),beforeCalls=calls;
  assert(line.data.labels.length===30&&line.data.datasets[0].data.slice(-5).every(n=>n===0),'full chart keeps all30 days including zero days');
  dailyNext().click();statusNext().click();assert(dailyTable().textContent.includes('Page 2 of 6')&&statusTable().textContent.includes('Page 2 of 2'),'independent analytics pagers');
  assert(JSON.stringify(line.data)===beforeChart,'chart data unchanged on table navigation');assert(calls===beforeCalls,'table navigation performs no API call');
  for(let i=0;i<4;i++)dailyNext().click();assert(dailyTable().textContent.includes('Page 6 of 6'),'all30 daily rows reachable');
  allStatuses=false;await panel.refresh();assert(dailyTable().textContent.includes('Page 6 of 6'),'same-filter refresh retains valid daily page');assert(statusTable().textContent.includes('Page 1 of 1'),'shrinking aggregate refresh clamps page');
  const currency=Array.from(panel.root.querySelectorAll('select'))[0];currency.value='USD';Array.from(panel.root.querySelectorAll('button')).find(b=>b.textContent==='Last 30 Days').click();await tick();assert(dailyTable().textContent.includes('Page 1 of 6'),'currency change resets first page');assert(dailyTable().textContent.includes('USD')&&!dailyTable().textContent.includes('INR'),'currencies remain separate');
  dailyNext().click();Array.from(panel.root.querySelectorAll('button')).find(b=>b.textContent==='Last 7 Days').click();await tick();assert(dailyTable().textContent.includes('Page 1 of 2'),'date range change resets first page');
  clearSession('logout');assert(panel.root.textContent==='','logout clears private tables and pagination DOM');assert(destroyed>0,'existing chart destruction preserved');
  setSession(tokenResponse(['MERCHANT']),'replacement');await panel.attach(fixture);assert(dailyTable().textContent.includes('Page 1 of 6'),'replacement starts first page in default range');assert(panel.filters().currency==='INR','replacement clears old currency scope');
  document.getElementById('summary').textContent=`PASS: ${results.length} assertions`;
}catch(e){document.getElementById('summary').textContent='FAIL: '+e.message;throw e;}
finally{panel?.dispose();for(const t of controls)t.dispose();clearSession('test-cleanup');}
