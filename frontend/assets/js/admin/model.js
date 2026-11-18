import { request } from '../api/client.js';
import { getSession,getVersion,subscribe,clearSession } from '../auth/session.js';
export const transitions=Object.freeze({PENDING_APPROVAL:['approve','reject'],ACTIVE:['suspend'],SUSPENDED:['reactivate'],REJECTED:[]});
export function adminFeedback(error){
  return ({400:'Check fields, filters, attestation and password requirements.',401:'Session expired or revoked. Sign in again.',403:'Access denied; check authorization or your current password.',404:'Requested record is unavailable.',409:'State changed or ownership needs review. Refresh authoritative details.',413:'Request exceeds the permitted size.',429:'Request limit reached. Wait before trying again.'})[error.status] || 'Outcome unavailable or unconfirmed. Refresh authoritative state before another action. No automatic retry.';
}
export function query(values={}){
  const out=new URLSearchParams();
  for(const key of ['page','size','search','status','currency','merchantId','sort','from','to'])if(values[key]!==undefined&&values[key]!=='')out.set(key,String(values[key]));
  return out.size?'?'+out.toString():'';
}
export function validatePage(value){
  if(!value||!Array.isArray(value.items)||!Number.isInteger(value.page)||!Number.isInteger(value.size)||value.size<1||value.size>100||!Number.isSafeInteger(value.total)||value.total<0)throw new Error('Invalid list response');return value;
}
export function createAdminWorkspace(onChange,{api=request,financialLocked=()=>false}={}){
  let state={view:null,data:null,busy:false,pending:false,message:'',intent:null,uncertain:false,filters:{},page:0,merchantId:''},seq=0;
  const emit=()=>onChange({...state,filters:{...state.filters}});
  const allowed=()=>getSession()?.roles.includes('ADMIN')&&getSession()?.accountStatus==='ACTIVE';
  const reset=()=>{seq++;state={view:null,data:null,busy:false,pending:false,message:'',intent:null,uncertain:false,filters:{},page:0,merchantId:''};emit();};
  const off=subscribe(reset);
  async function load(view,filters={},page=0){
    if(!allowed()||state.pending)return false;
    const current=++seq,version=getVersion();
    state={...state,view,filters:{...filters},page,busy:true,data:null,intent:null,message:'Loading authorized Admin data…'};emit();
    try{
      const endpoint=view==='pending'?'merchants':view==='merchant'?'merchant':view;
      const values={...filters,...(view==='pending'?{status:'PENDING_APPROVAL'}:{}),...(['profile','merchant','dashboard'].includes(view)?{}:{page,size:25})};
      if(view==='merchant'&&!values.merchantId){state.message='Enter a Merchant ID or choose one from Merchant Management.';return false;}
      const data=await api('/admin/'+endpoint+query(values));
      if(current!==seq||version!==getVersion())return false;
      if(['merchants','pending','payments','refunds','audit','accounts'].includes(view))validatePage(data);
      if(view==='merchant'&&(!data||data.merchantId!==values.merchantId||!Object.hasOwn(transitions,data.status)))throw new Error('Invalid merchant');
      state.data=data;state.merchantId=view==='merchant'?values.merchantId:state.merchantId;
      // Only a fresh authoritative detail read resolves an uncertain action on that same Merchant.
      if(view==='merchant'&&values.merchantId===state.uncertainMerchant){state.uncertain=false;state.uncertainMerchant=null;}
      state.message='Authorized snapshot loaded. Refresh to obtain current state.';return true;
    }catch(error){if(current===seq&&version===getVersion())state.message=error.status===undefined?'Invalid administrative response; no action is enabled.':adminFeedback(error);return false;}
    finally{if(current===seq&&version===getVersion()){state.busy=false;emit();}}
  }
  return {
    start:emit,dispose:off,state:()=>({...state}),reset,
    pending:()=>state.pending,
    async show(view){if(state.view!==view)return load(view,view==='merchant'&&state.merchantId?{merchantId:state.merchantId}:{});},
    load,
    refresh:()=>load(state.view,state.filters,state.page),
    review(action,fields){
      if(!allowed()||state.busy||state.pending||state.uncertain||financialLocked()||state.view!=='merchant'||!state.data||!transitions[state.data.status]?.includes(action))return false;
      if(state.data.status==='PENDING_APPROVAL'&&!state.data.registrationUserId){state.message='Unclaimed historical registry record: registration approval is unavailable; ownership needs supported review.';emit();return false;}
      const body={merchantId:state.data.merchantId};
      if(action==='approve'){
        if(!fields.ownershipAttested||!/^[A-Za-z0-9][A-Za-z0-9._/\-]{2,99}$/.test(fields.reviewReference||'')){state.message='Explicit ownership attestation and review reference (3–100 supported characters) are required.';emit();return false;}
        Object.assign(body,{reviewReference:fields.reviewReference,ownershipAttested:true});
      }else{
        const reason=fields.reason?.trim();if(!reason||reason.length>500||/[\x00-\x1f\x7f]/.test(reason)){state.message='A reason of 1–500 characters without control characters is required.';emit();return false;}
        body.reason=reason;
      }
      state.intent=Object.freeze({action,from:state.data.status,body:Object.freeze(body)});state.message='Review the exact Merchant and transition. Submission requires explicit confirmation.';emit();return true;
    },
    cancel(){if(!state.pending){state.intent=null;emit();}},
    async confirm(){
      if(!allowed()||!state.intent||state.pending||state.uncertain||financialLocked())return false;
      const intent=state.intent,version=getVersion(),current=++seq;state.pending=true;state.message='Administrative action pending…';emit();
      try{
        const data=await api('/admin/merchant/'+intent.action,{method:'POST',body:intent.body});
        if(version!==getVersion()||current!==seq)return false;
        if(!data||data.merchantId!==intent.body.merchantId||data.status!==({approve:'ACTIVE',reject:'REJECTED',suspend:'SUSPENDED',reactivate:'ACTIVE'})[intent.action])throw new Error('Invalid action response');
        state.data=null;state.intent=null;state.message='Action confirmed. Refresh Merchant details explicitly before another action.';return true;
      }catch(error){
        if(version!==getVersion()||current!==seq)return false;
        state.message=adminFeedback(error);state.data=null;state.intent=null;
        state.uncertain=true;state.uncertainMerchant=intent.body.merchantId;return false;
      }finally{if(version===getVersion()&&current===seq){state.pending=false;emit();}}
    },
    async createAccount(login,password,confirmation,confirmed){
      if(!allowed()||state.pending||state.busy||financialLocked()||!confirmed)return false;
      if(password!==confirmation||[...password].length<12||new TextEncoder().encode(password).length>72||password.includes('\0')){state.message='Check matching Admin passwords and policy.';emit();return false;}
      const version=getVersion(),current=++seq;state.pending=true;emit();
      try{const result=await api('/admin/accounts',{method:'POST',body:{login,password,confirmPassword:confirmation}});
        if(version!==getVersion()||current!==seq)return false;
        if(!result||result.login!==login.trim().toLowerCase()||result.accountStatus!=='ACTIVE'||!result.enabled||result.roles?.join(',')!=='ADMIN')throw new Error();
        state.data=null;state.message='Additional Admin confirmed. Refresh the Admin account list.';return true;
      }catch(error){if(version===getVersion()&&current===seq)state.message=adminFeedback(error);return false;}
      finally{password=confirmation='';if(version===getVersion()&&current===seq){state.pending=false;emit();}}
    },
    async changePassword(currentPassword,newPassword,confirmPassword){
      if(!allowed()||state.pending||state.busy||financialLocked())return false;
      if(newPassword!==confirmPassword||[...newPassword].length<12||new TextEncoder().encode(newPassword).length>72||newPassword.includes('\0')){state.message='Matching passwords: minimum 12 Unicode characters, maximum 72 UTF-8 bytes.';emit();return false;}
      const version=getVersion(),current=++seq;state.pending=true;state.message='Changing password…';emit();
      try{
        await api('/admin/profile/password',{method:'POST',body:{currentPassword,newPassword,confirmPassword}});
        if(version!==getVersion()||current!==seq)return false;
        clearSession('password-changed');return true;
      }catch(error){if(version===getVersion()&&current===seq)state.message=adminFeedback(error);return false;}
      finally{currentPassword=newPassword=confirmPassword='';if(version===getVersion()&&current===seq){state.pending=false;emit();}}
    }
  };
}
