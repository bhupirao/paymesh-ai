// Deliberately imports NO account/session module and sends no browser cookies or JWT.
export async function checkoutRequest(token,{pay=false,status=false,body,key}={}){
 if(typeof token!=='string'||!/^[A-Za-z0-9_-]{43}$/.test(token))throw {status:400};
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
 try{const headers={Accept:'application/json'};if(pay){headers['Content-Type']='application/json';headers['X-PayMesh-Checkout']='1';headers['Idempotency-Key']=key;}
  const response=await fetch('/api/v1/checkout/'+token+(pay?'/pay':status?'/status':''),{method:pay?'POST':'GET',headers,body:pay?JSON.stringify(body):undefined,credentials:'omit',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer',signal:controller.signal});
  if(!response.ok)throw {status:response.status};const text=await response.text();if(text.length>65536)throw {status:0};try{return JSON.parse(text);}catch{throw {status:0};}
 }catch(error){throw {status:Number.isInteger(error.status)?error.status:0};}finally{clearTimeout(timer);}
}
