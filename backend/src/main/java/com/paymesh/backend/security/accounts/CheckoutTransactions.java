package com.paymesh.backend.security.accounts;
import com.paymesh.backend.dto.*;
import com.paymesh.backend.service.internal.InternalPaymentService;
import java.time.*;
import java.util.*;
import java.math.BigDecimal;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;

/** Link capability authorization, NOT an impersonated Merchant/Admin principal. */
@Service
public class CheckoutTransactions {
 private final AuthStore store;private final AccountAdministrationLock lock;private final InternalPaymentService payments;private final AccountAudit audit;private final CheckoutDemoGate gate;
 public CheckoutTransactions(AuthStore store,AccountAdministrationLock lock,InternalPaymentService payments,AccountAudit audit,CheckoutDemoGate gate){this.store=store;this.lock=lock;this.payments=payments;this.audit=audit;this.gate=gate;}
 public static class Missing extends RuntimeException{} public static class Conflict extends RuntimeException{}
 public record Accepted(UUID attemptId,PaymentResponse payment,String simulation,boolean replay){}
 public static void token(String token){if(!AuthStore.opaqueFormat(token))throw new IllegalArgumentException();}
 private Instant now(){return store.jdbc.queryForObject("SELECT clock_timestamp()",java.sql.Timestamp.class).toInstant();}
 private Map<String,Object> link(String token,boolean update){token(token);var rows=store.jdbc.queryForList("SELECT * FROM "+store.table("payment_links")+" WHERE public_token=?"+(update?" FOR UPDATE":""),token);if(rows.isEmpty())throw new Missing();return rows.getFirst();}
 private boolean eligible(String merchant){return store.jdbc.queryForObject("SELECT count(*) FROM "+store.table("merchants")+" m JOIN "+store.table("merchant_administration")+" a USING(merchant_id) JOIN "+store.table("merchant_memberships")+" mm USING(merchant_id) JOIN "+store.table("app_users")+" u USING(user_id) WHERE m.merchant_id=? AND m.active AND m.verified AND a.status='ACTIVE' AND mm.active AND u.enabled AND u.account_status='ACTIVE' AND (SELECT count(*) FROM "+store.table("merchant_memberships")+" WHERE merchant_id=m.merchant_id)=1 AND (SELECT count(*) FROM "+store.table("merchant_memberships")+" WHERE user_id=u.user_id)=1 AND (SELECT count(*) FROM "+store.table("user_roles")+" WHERE user_id=u.user_id)=1 AND EXISTS(SELECT 1 FROM "+store.table("user_roles")+" WHERE user_id=u.user_id AND role_name='MERCHANT')",Integer.class,merchant)==1;}
 private List<Map<String,Object>> attempts(Object id){return store.jdbc.queryForList("SELECT a.*,p.status AS payment_status FROM "+store.table("checkout_attempts")+" a JOIN "+store.table("payments")+" p USING(payment_id) WHERE a.link_id=? ORDER BY a.created_at DESC,a.attempt_id DESC",id);}
 @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ) public Map<String,Object> read(String token){var l=link(token,false);var all=attempts(l.get("link_id"));var latest=all.stream().filter(a->!a.get("status").equals("FAILED")).findFirst().orElse(all.isEmpty()?null:all.getFirst());String status=l.get("status").toString();
  if(!status.equals("PAID")&&latest!=null&&Set.of("PROCESSING","UNCERTAIN").contains(latest.get("status")))status=latest.get("status").toString();
  boolean available=eligible(l.get("merchant_id").toString());if(status.equals("ACTIVE")){if(!AuthStore.instant(l,"expires_at").isAfter(now()))status="EXPIRED";else if(!available)status="UNAVAILABLE";else if(latest!=null&&latest.get("status").equals("FAILED"))status="FAILED";}
  String business=store.jdbc.query("SELECT business_name FROM "+store.table("merchant_registrations")+" WHERE merchant_id=?",(r,n)->r.getString(1),l.get("merchant_id")).stream().findFirst().orElse("PayMesh merchant (business name not recorded)");
  var response=new LinkedHashMap<String,Object>();response.put("merchantName",business);response.put("orderReference",l.get("customer_reference"));response.put("description",l.get("description"));response.put("amount",((BigDecimal)l.get("amount")).toPlainString());response.put("currency",l.get("currency"));response.put("paymentMethod",l.get("payment_method"));response.put("expiresAt",AuthStore.instant(l,"expires_at").toString());response.put("checkoutStatus",status);response.put("canPay",available&&Set.of("ACTIVE","FAILED").contains(status)&&all.size()<5);response.put("simulationChoices",gate.enabled()?List.of("SUCCESS","FAILED","TIMEOUT"):List.of());response.put("simulationNotice","Simulation only. No bank debit, settlement or money arrival is represented.");
  response.put("attemptReference",latest==null?null:latest.get("attempt_id"));response.put("attemptStatus",latest==null?null:latest.get("status"));response.put("paymentStatus",latest==null?null:latest.get("payment_status"));response.put("receiptReference",status.equals("PAID")?all.stream().filter(a->a.get("status").equals("SUCCESS")).map(a->a.get("attempt_id")).findFirst().orElse(null):null);response.put("paidAt",status.equals("PAID")?AuthStore.instant(l,"updated_at").toString():null);return response;
 }
 @Transactional(propagation=Propagation.REQUIRES_NEW) public Accepted accept(String token,String key,String simulation){
  token(token);if(key==null||!key.matches("[A-Za-z0-9._:-]{1,128}"))throw new IllegalArgumentException();if(simulation!=null&&!Set.of("SUCCESS","FAILED","TIMEOUT").contains(simulation))throw new IllegalArgumentException();
  lock.acquire();var l=link(token,true);var all=attempts(l.get("link_id"));String digest=AuthStore.digest(key),request=AuthStore.digest("confirmed:true;simulation:"+(simulation==null?"NONE":simulation));
  for(var a:all)if(a.get("key_digest").equals(digest)){if(!a.get("request_digest").equals(request))throw new Conflict();return new Accepted((UUID)a.get("attempt_id"),null,null,true);}
  if(simulation!=null&&!gate.enabled())throw new IllegalArgumentException();
  if(!l.get("status").equals("ACTIVE")||!AuthStore.instant(l,"expires_at").isAfter(now())||!eligible(l.get("merchant_id").toString())||all.size()>=5||all.stream().anyMatch(a->!a.get("status").equals("FAILED")))throw new Conflict();
  PaymentLinks.validate(new PaymentLinks.Input(((BigDecimal)l.get("amount")).toPlainString(),l.get("currency").toString(),l.get("payment_method").toString(),"","",1));
  UUID attempt=UUID.randomUUID();var created=payments.createPayment(new PaymentRequest(l.get("merchant_id").toString(),(BigDecimal)l.get("amount"),l.get("currency").toString(),"checkout-"+attempt,l.get("payment_method").toString()),"checkout:"+attempt);UUID payment=created.payment().paymentId();payments.claimPaymentForProcessing(payment);
  store.jdbc.update("INSERT INTO "+store.table("checkout_attempts")+"(attempt_id,link_id,merchant_id,payment_id,key_digest,request_digest,status,simulation_outcome) VALUES (?,?,?,?,?,?,'PROCESSING',?)",attempt,l.get("link_id"),l.get("merchant_id"),payment,digest,request,simulation);
  audit.checkoutAccepted(l.get("merchant_id").toString(),attempt);return new Accepted(attempt,payments.getPaymentById(payment),simulation,false);
 }
 @Transactional(propagation=Propagation.REQUIRES_NEW) public void uncertain(UUID id){store.jdbc.update("UPDATE "+store.table("checkout_attempts")+" a SET status='UNCERTAIN',updated_at=clock_timestamp() WHERE attempt_id=? AND status='PROCESSING' AND EXISTS(SELECT 1 FROM "+store.table("payments")+" p WHERE p.payment_id=a.payment_id AND p.status='PROCESSING')",id);}
}
