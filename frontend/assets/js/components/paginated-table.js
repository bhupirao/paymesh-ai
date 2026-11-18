// Presentation only: full rows remain available; no monetary arithmetic or server paging.
export function createPaginatedTable({rows=[],columns=[],labels={},label='Exact-value records',pageSize=5,page=0,onPage=()=>{}}={}){
  if(!Number.isInteger(pageSize)||pageSize<1||pageSize>5)throw new Error('Invalid table page size');
  const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
  let data=[],current=0,disposed=false;
  const root=el('section');root.className='dashboard-paged-table';root.setAttribute('aria-label',label);
  const empty=el('p','No records in this authorized range.');
  const wrap=el('div');wrap.className='table-responsive';wrap.tabIndex=0;wrap.setAttribute('aria-label',label+' · scrollable exact data');
  const table=el('table');table.className='table';const head=el('thead'),header=el('tr');
  for(const key of columns){const th=el('th',labels[key]||key);th.scope='col';header.append(th);}head.append(header);
  const body=el('tbody');table.append(head,body);wrap.append(table);
  const announcement=el('p');announcement.className='small text-secondary mb-2';announcement.setAttribute('role','status');announcement.setAttribute('aria-live','polite');announcement.setAttribute('aria-atomic','true');announcement.tabIndex=-1;
  const nav=el('nav');nav.className='dashboard-table-pagination';nav.setAttribute('aria-label',label+' pagination');
  const previous=el('button','←');previous.type='button';previous.className='btn btn-outline-primary btn-sm';previous.setAttribute('aria-label','Previous page · '+label);
  const indicator=el('span');indicator.className='small';indicator.setAttribute('aria-hidden','true');
  const next=el('button','→');next.type='button';next.className='btn btn-outline-primary btn-sm';next.setAttribute('aria-label','Next page · '+label);
  nav.append(previous,indicator,next);root.append(empty,wrap,announcement,nav);
  const snapshot=()=>{const total=data.length,pages=Math.ceil(total/pageSize),start=total?current*pageSize:0;return {page:current,pages,total,start:total?start+1:0,end:Math.min(start+pageSize,total),rows:data.slice(start,start+pageSize)};};
  function render(focusFrom=null){
    const s=snapshot();body.replaceChildren();for(const row of s.rows){const tr=el('tr');for(const key of columns)tr.append(el('td',row[key]??'Not recorded'));body.append(tr);}
    empty.hidden=s.total!==0;wrap.hidden=s.total===0;announcement.hidden=s.total===0;nav.hidden=s.total<=pageSize;
    previous.disabled=current===0||s.pages===0;next.disabled=s.pages===0||current>=s.pages-1;
    indicator.textContent=`${s.total?current+1:0} / ${s.pages}`;
    announcement.textContent=s.total?`Showing ${s.start}–${s.end} of ${s.total}. Page ${current+1} of ${s.pages}.`:'';
    onPage(current);
    // Preserve keyboard navigation when the activated arrow becomes disabled at an edge.
    if(focusFrom?.disabled){if(!nav.hidden)(focusFrom===next?previous:next).focus();else announcement.focus();}
  }
  function go(to,focusFrom=null){if(disposed||!Number.isInteger(to))return false;const last=Math.max(0,Math.ceil(data.length/pageSize)-1);const target=Math.max(0,Math.min(last,to));if(target===current)return false;current=target;render(focusFrom);return true;}
  previous.addEventListener('click',()=>go(current-1,previous));next.addEventListener('click',()=>go(current+1,next));
  function setRows(value,{reset=false}={}){if(disposed)return;if(!Array.isArray(value))throw new Error('Invalid table rows');data=value.slice();current=reset?0:Math.max(0,Math.min(current,Math.max(0,Math.ceil(data.length/pageSize)-1)));render();}
  current=Number.isInteger(page)&&page>=0?page:0;setRows(rows);
  return {root,previous,next,announcement,indicator,controls:nav,body,snapshot,setRows,go,nextPage:()=>go(current+1),previousPage:()=>go(current-1),reset:()=>go(0),
    dispose(){disposed=true;data=[];current=0;body.replaceChildren();announcement.textContent='';previous.disabled=next.disabled=true;root.replaceChildren();}};
}
