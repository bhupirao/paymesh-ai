const id='[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',prefix='/'+ '(?:merchant|admin)'+'/ai/conversations';
export function conversationRoute(method,path){
 if(typeof path!=='string'||path.length>2048||path.includes('#')||/%(?![a-fA-F0-9]{2})/.test(path))return false;
 const parts=path.split('?');if(parts.length>2||parts.length===2&&!parts[1])return false;const base=parts[0];
 if(method==='POST')return parts.length===1&&new RegExp(`^${prefix}(?:/${id}/(?:messages|rename|delete))?$`).test(base);
 if(method!=='GET')return false;
 const list=new RegExp(`^${prefix}$`).test(base),messages=new RegExp(`^${prefix}/${id}/messages$`).test(base);
 if(!list&&!messages&&!new RegExp(`^${prefix}(?:/${id}|/creations/${id}|/${id}/requests/${id})$`).test(base))return false;
 const params=[...new URLSearchParams(parts[1]||'')];if(params.length>4||new Set(params.map(([k])=>k)).size!==params.length)return false;
 const keys=list?['page','size','search','paymentId']:messages?['page','size']:[];
 return params.every(([k,v])=>keys.includes(k)&&v&&!/[\x00-\x1f\x7f]/.test(v)&&(k==='page'?/^\d{1,5}$/.test(v)&&+v<=10000:k==='size'?/^\d{1,2}$/.test(v)&&+v>=1&&+v<=10:k==='search'?[...v].length<=120:new RegExp(`^${id}$`).test(v)));
}
