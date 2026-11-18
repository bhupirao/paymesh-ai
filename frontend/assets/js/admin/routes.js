export const ADMIN_PAGES=Object.freeze({
  '/admin/ai':'AI Assistant','/admin/dashboard':'Dashboard','/admin/merchants':'Merchant Management','/admin/merchant':'Merchant Detail',
  '/admin/pending':'Pending Approvals','/admin/payments':'Payment Monitoring','/admin/refunds':'Refund Monitoring',
  '/admin/audit':'Audit History','/admin/accounts':'Admin Accounts','/admin/profile':'Admin Profile'
});
export function adminRoute(method,path){
  if(typeof path!=='string'||path.length>2048||path.includes('#')||/%(?![0-9a-f]{2})/i.test(path))return false;
  const [base,query='',extra]=path.split('?');if(extra!==undefined)return false;
  if(method==='POST')return !path.includes('?')&&['/admin/ai/chat','/admin/accounts','/admin/merchant/approve','/admin/merchant/reject','/admin/merchant/suspend','/admin/merchant/reactivate','/admin/profile/password'].includes(base);
  if(method!=='GET')return false;
  const detail=/^\/admin\/(payments|refunds)\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(base);
  if(!detail&&!['/admin/analytics','/admin/dashboard','/admin/merchants','/admin/merchant','/admin/payments','/admin/refunds','/admin/audit','/admin/accounts','/admin/profile'].includes(base))return false;
  const params=new URLSearchParams(query),keys=[...params.keys()];
  if(keys.length>10||new Set(keys).size!==keys.length)return false;
  if(detail||base==='/admin/profile')return keys.length===0;
  const allowed=base==='/admin/analytics'?['from','to','currency','merchantId']:base==='/admin/merchant'?['merchantId']:['page','size','search','status','currency','merchantId','sort','from','to'];
  for(const [key,value] of params){
    if(!allowed.includes(key)||!value||/[\x00-\x1f\x7f]/.test(value))return false;
    if(['search','merchantId'].includes(key)&&value.length>100)return false;
    if(['page','size'].includes(key)&&(!/^\d{1,5}$/.test(value)||Number(value)>(key==='size'?100:10000)||Number(value)<(key==='size'?1:0)))return false;
    if(key==='sort'&&!['newest','oldest'].includes(value))return false;
    if(key==='currency'&&!['INR','USD'].includes(value))return false;
    if(key==='status'&&!/^[A-Z_]{1,24}$/.test(value))return false;
    if(['from','to'].includes(key)&&(value.length>35||!Number.isFinite(Date.parse(value))))return false;
  }
  return base!=='/admin/merchant'||params.has('merchantId');
}
