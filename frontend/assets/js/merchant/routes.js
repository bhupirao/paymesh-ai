import { adminRoute } from '../admin/routes.js';
export const MERCHANT_PAGES=Object.freeze({'/merchant/ai':'AI Assistant','/merchant/dashboard':'Dashboard','/merchant/payments':'Payments','/merchant/refunds':'Refunds','/merchant/payment-links':'Payment Links','/merchant/payment-links/create':'Create Payment Link','/merchant/profile':'Business Profile','/merchant/security':'Account Security'});
export function merchantRoute(method,path){
  if(typeof path!=='string'||!path.startsWith('/merchant/'))return false;
  if(/^\/merchant\/payment-links(?:\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?:\/cancel)?)?(?:\?.*)?$/.test(path)){
    if(path.includes('#')||/%(?![a-fA-F0-9]{2})/.test(path))return false;
    const [base,raw]=path.split('?');if(method==='POST')return raw===undefined&&(base==='/merchant/payment-links'||base.endsWith('/cancel'));
    if(method!=='GET'||base.endsWith('/cancel'))return false;if(base!=='/merchant/payment-links')return raw===undefined;
    const pairs=[...new URLSearchParams(raw||'')];return path.length<=2048&&new Set(pairs.map(([k])=>k)).size===pairs.length&&pairs.every(([k,v])=>v&&!/[\x00-\x1f\x7f]/.test(v)&&(k==='page'?/^\d{1,5}$/.test(v)&&+v<=10000:k==='size'?/^\d{1,2}$/.test(v)&&+v>=1&&+v<=50:k==='search'?v.length<=100:k==='status'?['ACTIVE','EXPIRED','CANCELLED','PAID','PROCESSING'].includes(v):k==='currency'?['INR','USD'].includes(v):false));
  }
  if(method==='POST')return path==='/merchant/profile/password'||path==='/merchant/ai/chat';
  const [base,query='']=path.split('?');
  if(!['/merchant/analytics','/merchant/dashboard','/merchant/payments','/merchant/refunds','/merchant/profile'].includes(base)||!adminRoute(method,path.replace('/merchant/','/admin/')))return false;
  const allowed=(base.endsWith('/dashboard')||base.endsWith('/analytics'))?['currency','from','to']:base.endsWith('/profile')?[]:['page','size','search','status','currency','sort','from','to'];
  return [...new URLSearchParams(query).keys()].every(k=>allowed.includes(k));
}
