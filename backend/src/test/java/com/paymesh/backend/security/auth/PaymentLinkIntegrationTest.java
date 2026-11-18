package com.paymesh.backend.security.auth;

import com.paymesh.backend.testing.BusinessJwtTestSupport;
import com.paymesh.backend.security.accounts.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.*;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.*;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

@SpringBootTest @AutoConfigureMockMvc(print=MockMvcPrint.NONE)
class PaymentLinkIntegrationTest extends BusinessJwtTestSupport {
 @Autowired MockMvc mvc;@Autowired com.fasterxml.jackson.databind.ObjectMapper json;
 @MockitoSpyBean SecurityAuditEventRepository audits;
 Identity owner,other;String merchant;
 @BeforeEach void setup()throws Exception{merchant="links-"+UUID.randomUUID();owner=identity("MERCHANT",Set.of(merchant));other=identity("MERCHANT",Set.of("links-other-"+UUID.randomUUID()));}
 Map<String,Object> input(){return new LinkedHashMap<>(Map.of("amount","999999999999.99","currency","INR","paymentMethod","UPI","customerReference","order-1","description","Test only","expiryHours",24));}
 MvcResult create(Identity actor,String key,Map<String,Object> in)throws Exception{return mvc.perform(post("/api/v1/merchant/payment-links").with(jwt(actor)).header("Idempotency-Key",key).contentType("application/json").content(json.writeValueAsBytes(in))).andReturn();}
 com.fasterxml.jackson.databind.JsonNode body(MvcResult r)throws Exception{return json.readTree(r.getResponse().getContentAsByteArray());}
 MvcResult get(Identity who,String path)throws Exception{return mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get("/api/v1/merchant/payment-links"+path).with(jwt(who))).andReturn();}
 MvcResult cancel(Identity who,String id)throws Exception{return mvc.perform(post("/api/v1/merchant/payment-links/"+id+"/cancel").with(jwt(who))).andReturn();}
 @Test void creationUsesOwnedGatewayAndExactAmountWithoutFinancialMutation()throws Exception{
  long payments=jdbc.queryForObject("SELECT count(*) FROM payments",Long.class);var r=create(owner,"create",input());assertEquals(201,r.getResponse().getStatus());var b=body(r);assertEquals(merchant,b.get("merchantId").asText());assertEquals("999999999999.99",b.get("amount").asText());assertEquals("MOCK_RAZORPAY",b.get("gatewayName").asText());assertTrue(b.get("checkoutPath").asText().matches("/checkout/[A-Za-z0-9_-]{43}"));assertTrue(b.get("paymentId").isNull());assertEquals(payments,jdbc.queryForObject("SELECT count(*) FROM payments",Long.class));assertEquals("no-store",r.getResponse().getHeader("Cache-Control"));
 }
 @Test void exactReplayConflictAndMerchantScopedKeys()throws Exception{
  var first=body(create(owner,"same",input()));var replay=create(owner,"same",input());assertEquals(200,replay.getResponse().getStatus());assertEquals(first,body(replay));var changed=input();changed.put("amount","1.00");assertEquals(409,create(owner,"same",changed).getResponse().getStatus());assertEquals(201,create(other,"same",input()).getResponse().getStatus());
 }
 @Test void canonicalAmountsReplay()throws Exception{var a=input();a.put("amount","1");var first=body(create(owner,"canonical",a));a.put("amount","1.00");assertEquals(first,body(create(owner,"canonical",a)));}
 @Test void gatewayAllowlist()throws Exception{for(String currency:List.of("INR","USD"))for(String method:List.of("UPI","CARD")){var a=input();a.put("currency",currency);a.put("paymentMethod",method);var r=create(owner,UUID.randomUUID().toString(),a);assertEquals(currency.equals("USD")&&method.equals("UPI")?400:201,r.getResponse().getStatus());}}
 @Test void invalidAmountsFieldsAndMassAssignmentFail()throws Exception{
  for(String v:List.of("0","-1","1.001","1000000000000","1e2","01.00")){var a=input();a.put("amount",v);assertEquals(400,create(owner,"bad",a).getResponse().getStatus(),v);}
  for(String field:List.of("merchantId","status","gateway","paymentId","role","checkoutUrl")){var a=input();a.put(field,"forbidden");assertEquals(400,create(owner,"bad",a).getResponse().getStatus());}
  for(int hours:List.of(0,2,169)){var a=input();a.put("expiryHours",hours);assertEquals(400,create(owner,"bad",a).getResponse().getStatus());}
 }
 @Test void ownedDetailsAndCancellationHideOtherMerchants()throws Exception{String id=body(create(owner,"owned",input())).get("linkId").asText();assertEquals(404,get(other,"/"+id).getResponse().getStatus());assertEquals(404,cancel(other,id).getResponse().getStatus());assertEquals(200,cancel(owner,id).getResponse().getStatus());assertEquals(409,cancel(owner,id).getResponse().getStatus());assertEquals("CANCELLED",body(get(owner,"/"+id)).get("status").asText());}
 @Test void expiryIsEffectiveReadOnlyAndCannotCancel()throws Exception{String id=body(create(owner,"expired",input())).get("linkId").asText();jdbc.update("UPDATE payment_links SET created_at=now()-interval '2 hour',expires_at=now()-interval '1 hour' WHERE link_id=?",UUID.fromString(id));assertEquals("EXPIRED",body(get(owner,"/"+id)).get("status").asText());assertEquals("ACTIVE",jdbc.queryForObject("SELECT status FROM payment_links WHERE link_id=?",String.class,UUID.fromString(id)));assertEquals(409,cancel(owner,id).getResponse().getStatus());assertEquals(1,body(get(owner,"?status=EXPIRED")).get("total").asInt());}
 @Test void listsBoundedOwnedAndNeverExposeTokens()throws Exception{create(owner,"one",input());create(owner,"two",input());create(other,"other",input());var p=body(get(owner,"?size=1&page=1&currency=INR&search=order"));assertEquals(2,p.get("total").asInt());assertEquals(1,p.get("items").size());assertFalse(p.toString().contains("checkoutPath"));assertFalse(p.toString().contains("public_token"));for(String q:List.of("size=51","page=-1","merchantId=OTHER","sort=amount","status=SUCCESS","page=0&page=1"))assertEquals(400,get(owner,"?"+q).getResponse().getStatus());}
 @Test void wrongRolesMissingAndRevokedJwtDenied()throws Exception{assertEquals(401,mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get("/api/v1/merchant/payment-links")).andReturn().getResponse().getStatus());assertEquals(403,create(identity("ADMIN",Set.of()),"admin",input()).getResponse().getStatus());jdbc.update("UPDATE app_users SET authorization_version=authorization_version+1 WHERE user_id=?",owner.userId());assertEquals(401,get(owner,"").getResponse().getStatus());}
 @Test void suspendedMembershipFailsClosed()throws Exception{jdbc.update("UPDATE merchant_administration SET status='SUSPENDED' WHERE merchant_id=?",merchant);assertEquals(403,create(owner,"suspended",input()).getResponse().getStatus());}
 @Test void auditActorAndRollback()throws Exception{
  var made=body(create(owner,"audit",input()));var events=audits.findByEventTypeAndResourceId("PAYMENT_LINK_CREATED",made.get("linkId").asText());assertEquals(owner.userId(),events.getFirst().getActorUserId());assertTrue(events.getFirst().getMetadata().isEmpty());
  doThrow(new IllegalStateException("test-only")).when(audits).saveAndFlush(argThat(e->e!=null&&e.getEventType().equals("PAYMENT_LINK_CREATED")));try{assertEquals(503,create(owner,"rollback",input()).getResponse().getStatus());assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM payment_links WHERE merchant_id=? AND idempotency_key='rollback'",Integer.class,merchant));}finally{reset(audits);}
 }
 @Test void concurrentDuplicateCreationCommitsOneLinkAndAudit()throws Exception{var pool=java.util.concurrent.Executors.newFixedThreadPool(2);try{var a=pool.submit(()->create(owner,"concurrent",input()));var b=pool.submit(()->create(owner,"concurrent",input()));var x=a.get();var y=b.get();assertEquals(Set.of(200,201),Set.of(x.getResponse().getStatus(),y.getResponse().getStatus()));assertEquals(body(x).get("linkId"),body(y).get("linkId"));assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM payment_links WHERE merchant_id=? AND idempotency_key='concurrent'",Integer.class,merchant));}finally{pool.shutdownNow();}}
 @Test void pendingAndInactiveMembershipCannotCreate()throws Exception{jdbc.update("UPDATE merchant_memberships SET active=false WHERE user_id=?",owner.userId());assertEquals(403,create(owner,"inactive",input()).getResponse().getStatus());}
 @Test void missingKeyAndBodyLimitAreRejected()throws Exception{assertEquals(413,mvc.perform(post("/api/v1/merchant/payment-links/not-a-uuid/cancel").with(jwt(owner)).contentType("application/json").content("x".repeat(4097))).andReturn().getResponse().getStatus());assertEquals(400,mvc.perform(post("/api/v1/merchant/payment-links").with(jwt(owner)).contentType("application/json").content(json.writeValueAsBytes(input()))).andReturn().getResponse().getStatus());assertEquals(413,mvc.perform(post("/api/v1/merchant/payment-links").with(jwt(owner)).contentType("application/json").content("x".repeat(4097))).andReturn().getResponse().getStatus());}

}
