import { isUUID } from '../auth/session.js';
import { validateScopedChat } from '../merchant-ai/schema.js';
const valid=v=>{if(!v)throw new Error('Invalid saved conversation');};
const merchant=id=>typeof id==='string'&&/^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$/.test(id);
export function canonicalContext(raw={}){
 valid(raw&&typeof raw==='object'&&!Array.isArray(raw)&&Object.keys(raw).every(k=>['paymentId','paymentLinkId','merchantId','statistics'].includes(k))&&!raw.paymentLinkId);
 const out={};if(raw.paymentId!=null){valid(isUUID(raw.paymentId));out.paymentId=raw.paymentId.toLowerCase();}if(raw.merchantId!=null){valid(merchant(raw.merchantId));out.merchantId=raw.merchantId;}
 if(raw.statistics!=null){valid(!out.paymentId&&typeof raw.statistics==='object'&&!Array.isArray(raw.statistics)&&Object.keys(raw.statistics).every(k=>['from','to','currency'].includes(k)));const s={};for(const k of ['from','to'])if(raw.statistics[k]!=null){valid(Number.isFinite(Date.parse(raw.statistics[k])));s[k]=new Date(raw.statistics[k]).toISOString();}valid(Boolean(s.from)===Boolean(s.to));if(raw.statistics.currency!=null){valid(['INR','USD'].includes(raw.statistics.currency));s.currency=raw.statistics.currency;}out.statistics=s;}
 if(!out.paymentId&&!out.statistics)out.statistics={};return out;
}
export const contextKey=value=>JSON.stringify(canonicalContext(value));
export function validateSummary(c,role){
 valid(c&&isUUID(c.conversationId)&&c.portalRole===role&&['PLATFORM','MERCHANT','PAYMENT'].includes(c.contextType)&&typeof c.title==='string'&&[...c.title].length>=1&&[...c.title].length<=120&&!/[\x00-\x1f\x7f]/.test(c.title)&&Number.isSafeInteger(c.version)&&c.version>=0&&Number.isInteger(c.turnCount)&&c.turnCount>=0&&c.turnCount<=50);
 for(const key of ['createdAt','updatedAt','expiresAt'])valid(typeof c[key]==='string'&&Number.isFinite(Date.parse(c[key])));
 const ctx=canonicalContext(c.context);if(role==='MERCHANT')valid(!ctx.merchantId&&merchant(c.merchantId));
 if(ctx.merchantId)valid(ctx.merchantId===c.merchantId);
 if(ctx.paymentId){const p=c.payment;valid(c.contextType==='PAYMENT'&&p&&p.paymentId===ctx.paymentId&&p.merchantId===c.merchantId&&merchant(p.merchantId)&&typeof p.amount==='string'&&/^(0|[1-9][0-9]{0,11})\.[0-9]{2}$/.test(p.amount)&&['INR','USD'].includes(p.currency)&&['CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'].includes(p.status));}else valid(c.payment==null);
 if(c.merchantId!=null)valid(merchant(c.merchantId)&&c.merchant&&c.merchant.merchantId===c.merchantId&&['ACTIVE','PENDING_APPROVAL','REJECTED','SUSPENDED'].includes(c.merchant.status)&&(c.merchant.businessName==null||typeof c.merchant.businessName==='string'&&c.merchant.businessName.length<=160));
 if(c.activeRequest!=null)valid(isUUID(c.activeRequest.requestId)&&Number.isSafeInteger(c.activeRequest.expectedVersion)&&['IN_PROGRESS','UNCERTAIN'].includes(c.activeRequest.status));return {...c,context:ctx};
}
export function validateMessages(payload,role){const c=validateSummary(payload?.conversation,role);valid(Array.isArray(payload.turns)&&payload.turns.length<=10&&Number.isInteger(payload.page)&&payload.page>=0&&Number.isInteger(payload.size)&&payload.size>=1&&payload.size<=10&&Number.isInteger(payload.total)&&payload.total===c.turnCount);let previous=0;
 const turns=payload.turns.map(t=>{valid(t&&isUUID(t.requestId)&&Number.isInteger(t.turnIndex)&&t.turnIndex>previous&&t.turnIndex<=c.turnCount&&typeof t.question==='string'&&[...t.question].length<=1000&&Number.isFinite(Date.parse(t.createdAt)));previous=t.turnIndex;validateScopedChat(t.response,c.payment,c.portalRole==='ADMIN'?'ADMIN_AUTHORIZED':'MERCHANT_OWNED');return {question:t.question,result:t.response,status:'completed',requestId:t.requestId,turnIndex:t.turnIndex,historical:true};});return {...payload,conversation:c,completed:turns};}
