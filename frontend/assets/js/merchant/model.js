import { request } from '../api/client.js';
import { getSession,getVersion,subscribe,clearSession,isUUID } from '../auth/session.js';
import { query,validatePage,adminFeedback } from '../admin/model.js';
export function validPassword(next,confirm){return typeof next==='string'&&next===confirm&&[...next].length>=12&&new TextEncoder().encode(next).length<=72&&!/[\u0000\uD800-\uDFFF]/u.test(next);}
const statuses=['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'];
export function validateMerchantData(view,data){
  if(view==='profile'||view==='security'){
    if(!data||typeof data.merchantId!=='string'||!data.merchantId||data.accountStatus!=='ACTIVE'||data.businessStatus!=='ACTIVE'||data.merchantVerified!==true||data.merchantActive!==true||data.membershipActive!==true||typeof data.registrationAvailable!=='boolean')throw new Error();return data;
  }
  const records=(rows,refund=false)=>{if(!Array.isArray(rows))throw new Error();for(const r of rows)if(!isUUID(r.paymentId)||(refund&&!isUUID(r.refundId))||!['INR','USD'].includes(r.currency)||typeof r.amount!=='string'||!/^\d+(?:\.\d{1,2})?$/.test(r.amount)||!(refund?['SUCCESS']:statuses).includes(r.status)||!Number.isFinite(Date.parse(r.createdAt)))throw new Error();};
  if(view==='dashboard'){
    validateMerchantData('profile',data?.profile);if(!Number.isSafeInteger(data.totalPayments)||data.totalPayments<0)throw new Error();
    for(const key of ['paymentAmounts','refundAmounts']){if(!Array.isArray(data[key]))throw new Error();for(const r of data[key])if(!['INR','USD'].includes(r.currency)||typeof r.amount!=='string'||!/^\d+(?:\.\d{1,2})?$/.test(r.amount)||!(key==='refundAmounts'?['SUCCESS']:statuses).includes(r.status))throw new Error();}
    for(const key of ['paymentCounts','refundCounts']){if(!Array.isArray(data[key]))throw new Error();for(const r of data[key])if(!Number.isSafeInteger(r.count)||r.count<0||!(key==='refundCounts'?['SUCCESS']:statuses).includes(r.status))throw new Error();}
    records(data.recentPayments);records(data.recentRefunds,true);
  }else{validatePage(data);records(data.items,view==='refunds');}return data;
}
export function createMerchantWorkspace(onChange,{api=request,financialLocked=()=>false}={}){
  let state={view:null,data:null,busy:false,pending:false,uncertain:false,message:'',filters:{},page:0},seq=0;
  const emit=()=>onChange({...state,filters:{...state.filters}});
  const allowed=()=>getSession()?.roles.join(',')==='MERCHANT'&&getSession()?.accountStatus==='ACTIVE';
  const reset=()=>{seq++;state={view:null,data:null,busy:false,pending:false,uncertain:false,message:'',filters:{},page:0};emit();};
  const off=subscribe(reset);
  async function load(view,filters={},page=0){
    if(!allowed()||state.pending||!['dashboard','payments','refunds','profile','security'].includes(view))return false;
    const current=++seq,version=getVersion();state={...state,view,data:null,busy:true,filters:{...filters},page,message:'Loading authorized Merchant snapshot…'};emit();
    try{
      const data=await api('/merchant/'+(view==='security'?'profile':view)+query({...filters,...(['payments','refunds'].includes(view)?{page,size:25}:{})}));
      if(current!==seq||version!==getVersion())return false;
      state.data=validateMerchantData(view,data);state.message='Authorized snapshot. Refresh for current state. Simulation only.';return true;
    }catch(error){if(current===seq&&version===getVersion())state.message=error.status===undefined?'Invalid Merchant response; records withheld.':adminFeedback(error);return false;}
    finally{if(current===seq&&version===getVersion()){state.busy=false;emit();}}
  }
  return {start:emit,reset,dispose:off,state:()=>({...state}),pending:()=>state.pending,load,
    refresh:()=>load(state.view,state.filters,state.page),show:view=>load(view),
    async changePassword(currentPassword,newPassword,confirmPassword,confirmed=false){
      if(!allowed()||!confirmed||state.pending||state.busy||state.uncertain||financialLocked())return false;
      if(!currentPassword||!validPassword(newPassword,confirmPassword)){state.message='Matching passwords: minimum 12 Unicode code points, maximum 72 UTF-8 bytes; no NUL or malformed Unicode.';emit();return false;}
      const version=getVersion(),operation=++seq;state.pending=true;state.message='Changing password. No automatic retry.';emit();
      try{
        const result=await api('/merchant/profile/password',{method:'POST',body:{currentPassword,newPassword,confirmPassword}});
        if(operation!==seq||version!==getVersion())return false;
        if(typeof result?.message!=='string')throw new Error();
        clearSession('password-changed');return true;
      }catch(error){if(operation===seq&&version===getVersion()){
        state.uncertain=!error.status||error.status>=500||error.status===200;
        state.message=state.uncertain?'Password outcome uncertain. Do not retry automatically. Sign in manually with the appropriate credentials; previous sessions may be revoked.':adminFeedback(error);
      }return false;}
      finally{currentPassword=newPassword=confirmPassword='';if(operation===seq&&version===getVersion()){state.pending=false;emit();}}
    }
  };
}
