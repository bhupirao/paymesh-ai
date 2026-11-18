package com.paymesh.backend.security.auth;

import com.paymesh.backend.testing.BusinessJwtTestSupport;
import com.paymesh.backend.security.accounts.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.*;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

@SpringBootTest @AutoConfigureMockMvc(print=MockMvcPrint.NONE)
class MerchantPortalIntegrationTest extends BusinessJwtTestSupport {
    @Autowired JwtKeyMaterial keys;@Autowired MockMvc mvc;@Autowired MerchantRegistration registration;@Autowired MerchantAdministration administration;@Autowired com.fasterxml.jackson.databind.ObjectMapper json;
    @MockitoSpyBean SecurityAuditEventRepository audits;
    String mid;Identity owner,other;
    static final String OLD="test-only-old-merchant-password",NEXT="test-only-new-merchant-password";
    @BeforeEach void setup()throws Exception{mid="portal-"+UUID.randomUUID();owner=identity("MERCHANT",Set.of(mid));other=identity("MERCHANT",Set.of("other-"+UUID.randomUUID()));jdbc.update("UPDATE app_users SET password_hash=? WHERE user_id=?",passwordEncoder.encode(OLD),owner.userId());}
    MvcResult read(Identity user,String path)throws Exception{return mvc.perform(get("/api/v1/merchant"+path).with(jwt(user))).andReturn();}
    com.fasterxml.jackson.databind.JsonNode body(MvcResult r)throws Exception{return json.readTree(r.getResponse().getContentAsByteArray());}
    UUID payment(String merchant,String currency,String status)throws Exception{UUID id=UUID.randomUUID();jdbc.update("INSERT INTO merchants(merchant_id) VALUES (?) ON CONFLICT DO NOTHING",merchant);jdbc.update("INSERT INTO payments(payment_id,merchant_id,customer_id,amount,currency,payment_method,status) VALUES (?,?,'portal-customer',100.01,?,'CARD',?)",id,merchant,currency,status);return id;}
    MvcResult password(String current,String next,String confirm)throws Exception{return mvc.perform(post("/api/v1/merchant/profile/password").with(jwt(owner)).contentType("application/json").content(json.writeValueAsBytes(Map.of("currentPassword",current,"newPassword",next,"confirmPassword",confirm)))).andReturn();}
    List<Map<String,Object>> snapshot(String t){return jdbc.queryForList("SELECT row_to_json(x)::text AS row FROM "+t+" x ORDER BY row_to_json(x)::text");}
    @Test void emptyDashboardAndLegacyProfileAreHonest()throws Exception{
        var d=read(owner,"/dashboard");assertEquals(200,d.getResponse().getStatus());assertEquals(0,body(d).get("totalPayments").asInt());assertTrue(body(d).get("recentRefunds").isEmpty());
        var p=body(read(owner,"/profile"));assertEquals(mid,p.get("merchantId").asText());assertFalse(p.get("registrationAvailable").asBoolean());assertTrue(p.get("businessName").isNull());assertFalse(p.has("approvedBy"));assertFalse(p.has("passwordHash"));
    }
    @Test void totalsAreOwnedExactAndCurrencySeparated()throws Exception{
        UUID inr=payment(mid,"INR","SUCCESS");payment(mid,"USD","SUCCESS");payment("other-unowned", "USD","SUCCESS");
        jdbc.update("INSERT INTO refunds(refund_id,payment_id,amount,status) VALUES (?,?,0.01,'SUCCESS')",UUID.randomUUID(),inr);
        var d=body(read(owner,"/dashboard"));assertEquals(2,d.get("totalPayments").asInt());assertEquals(2,d.get("paymentAmounts").size());assertEquals("100.01",d.get("paymentAmounts").get(0).get("amount").asText());assertEquals("0.01",d.get("refundAmounts").get(0).get("amount").asText());
        assertEquals(1,body(read(owner,"/dashboard?currency=USD")).get("totalPayments").asInt());
    }
    @Test void listsFiltersPaginationAndCustomerSearchAreOwned()throws Exception{
        UUID own=payment(mid,"INR","SUCCESS");payment(mid,"USD","FAILED");payment("other-unowned","INR","SUCCESS");
        assertEquals(2,body(read(owner,"/payments")).get("total").asInt());assertEquals(1,body(read(owner,"/payments?currency=INR&status=SUCCESS")).get("items").size());
        assertEquals(1,body(read(owner,"/payments?search="+own)).get("total").asInt());assertEquals(2,body(read(owner,"/payments?search=portal-customer")).get("total").asInt());
        assertEquals(0,body(read(other,"/payments?search="+own)).get("total").asInt());assertEquals(1,body(read(owner,"/payments?size=1&page=1&sort=oldest")).get("items").size());
        assertEquals(0,body(read(owner,"/payments?to=2000-01-01T00:00:00Z")).get("total").asInt());
    }
    @Test void refundListCannotLeakOtherMerchants()throws Exception{
        UUID p=payment(mid,"INR","SUCCESS");jdbc.update("INSERT INTO refunds(refund_id,payment_id,amount,status) VALUES (?,?,1.00,'SUCCESS')",UUID.randomUUID(),p);
        assertEquals(1,body(read(owner,"/refunds")).get("total").asInt());assertEquals(0,body(read(other,"/refunds?search="+p)).get("total").asInt());
        assertTrue(Set.of(403,404).contains(mvc.perform(get("/api/v1/payments/"+p).with(jwt(other))).andReturn().getResponse().getStatus()));
    }
    @Test void wrongRoleAndMissingJwtDenied()throws Exception{
        var admin=identity("ADMIN",Set.of());for(String path:List.of("/dashboard","/payments","/refunds","/profile")){assertEquals(401,mvc.perform(get("/api/v1/merchant"+path)).andReturn().getResponse().getStatus());assertEquals(403,read(admin,path).getResponse().getStatus());}
    }
    @Test void inactiveUnverifiedAmbiguousAndDisabledContextsFailClosed()throws Exception{
        jdbc.update("UPDATE merchant_memberships SET active=false WHERE user_id=?",owner.userId());assertEquals(403,read(owner,"/profile").getResponse().getStatus());
        jdbc.update("UPDATE merchant_memberships SET active=true WHERE user_id=?",owner.userId());jdbc.update("UPDATE merchants SET active=false WHERE merchant_id=?",mid);assertEquals(403,read(owner,"/payments").getResponse().getStatus());
        var original=jdbc.queryForMap("SELECT verified_by,verified_at FROM merchants WHERE merchant_id=?",mid);jdbc.update("UPDATE merchants SET active=false,verified=false,verified_by=null,verified_at=null WHERE merchant_id=?",mid);assertEquals(403,read(owner,"/dashboard").getResponse().getStatus());
        jdbc.update("UPDATE merchants SET verified=true,active=true,verified_by=?,verified_at=? WHERE merchant_id=?",original.get("verified_by"),original.get("verified_at"),mid);String second="second-"+UUID.randomUUID();jdbc.update("INSERT INTO merchants(merchant_id) VALUES (?)",second);jdbc.update("INSERT INTO merchant_memberships(user_id,merchant_id,active) VALUES (?,?,true)",owner.userId(),second);assertEquals(403,read(owner,"/profile").getResponse().getStatus());
    }
    @Test void nonActiveMerchantCannotUseAnyPortalApiOrPasswordChange()throws Exception{
        for(String status:List.of("PENDING_APPROVAL","REJECTED","SUSPENDED")){
            jdbc.update("UPDATE app_users SET account_status=? WHERE user_id=?",status,owner.userId());String login=jdbc.queryForObject("SELECT login_normalized FROM app_users WHERE user_id=?",String.class,owner.userId());
            var response=mvc.perform(post("/api/v1/auth/login").contentType("application/json").content(json.writeValueAsBytes(Map.of("login",login,"password",OLD)))).andReturn();assertEquals(200,response.getResponse().getStatus());String token=body(response).get("accessToken").asText();
            assertEquals(403,mvc.perform(get("/api/v1/merchant/dashboard").header("Authorization","Bearer "+token)).andReturn().getResponse().getStatus());assertEquals(403,mvc.perform(post("/api/v1/merchant/profile/password").header("Authorization","Bearer "+token).contentType("application/json").content(json.writeValueAsBytes(Map.of("currentPassword",OLD,"newPassword",NEXT,"confirmPassword",NEXT)))).andReturn().getResponse().getStatus());
        }
    }
    @Test void queriesAreBoundedAndCannotSelectMerchantOrInjectSort()throws Exception{
        for(String q:List.of("merchantId=OTHER","userId=OTHER","size=101","page=-1","sort=amount","status=ACTIVE","currency=EUR","page=0&page=1","from=invalid","from=2026-02-01T00:00:00Z&to=2026-01-01T00:00:00Z"))assertEquals(400,read(owner,"/payments?"+q).getResponse().getStatus(),q);
        assertEquals(400,read(owner,"/profile?role=ADMIN").getResponse().getStatus());assertEquals(400,read(owner,"/refunds?status=FAILED").getResponse().getStatus());
    }
    @Test void passwordPolicyCurrentAndConfirmationFailureDoNotMutate()throws Exception{
        var before=snapshot("app_users");assertEquals(403,password("wrong-password-test",NEXT,NEXT).getResponse().getStatus());assertEquals(400,password(OLD,NEXT,"mismatch").getResponse().getStatus());assertEquals(400,password(OLD,"short","short").getResponse().getStatus());assertEquals(before,snapshot("app_users"));
    }
    @Test void passwordChangeAuditsSelfInvalidatesJwtAndPreservesFinancialRows()throws Exception{
        var before=new HashMap<String,List<Map<String,Object>>>();for(String t:List.of("payments","refunds","merchants","merchant_memberships","merchant_registrations","payment_gateway_transactions","idempotency_keys","simulated_gateway_outcomes","webhook_events","reconciliation_jobs","reconciliation_attempts"))before.put(t,snapshot(t));
        UUID family=UUID.randomUUID();jdbc.update("INSERT INTO auth_sessions(session_id,user_id,authorization_version,account_status,roles_snapshot,remember_me,created_at,absolute_expires_at,idle_expires_at) VALUES (?,?,0,'ACTIVE','MERCHANT',false,now(),now()+interval '1 hour',now()+interval '1 hour')",family,owner.userId());
        long version=jdbc.queryForObject("SELECT authorization_version FROM app_users WHERE user_id=?",Long.class,owner.userId());
        assertEquals(200,password(OLD,NEXT,NEXT).getResponse().getStatus());assertEquals(version+1,jdbc.queryForObject("SELECT authorization_version FROM app_users WHERE user_id=?",Long.class,owner.userId()));
        String hash=jdbc.queryForObject("SELECT password_hash FROM app_users WHERE user_id=?",String.class,owner.userId());assertTrue(passwordEncoder.matches(NEXT,hash));assertFalse(passwordEncoder.matches(OLD,hash));assertEquals(401,read(owner,"/profile").getResponse().getStatus());assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM auth_sessions WHERE session_id=? AND revoked_at IS NOT NULL",Integer.class,family));
        var audit=audits.findByEventTypeAndResourceId("MERCHANT_PASSWORD_CHANGED",owner.userId().toString());assertEquals(1,audit.size());assertEquals(owner.userId(),audit.getFirst().getActorUserId());assertTrue(audit.getFirst().getMetadata().isEmpty());for(var e:before.entrySet())assertEquals(e.getValue(),snapshot(e.getKey()));
    }
    @Test void auditFailureRollsBackPasswordAndVersion()throws Exception{
        var before=snapshot("app_users");doThrow(new IllegalStateException("test-only-failure")).when(audits).saveAndFlush(argThat(e->e!=null&&e.getEventType().equals("MERCHANT_PASSWORD_CHANGED")));
        try{assertEquals(503,password(OLD,NEXT,NEXT).getResponse().getStatus());assertEquals(before,snapshot("app_users"));}finally{reset(audits);}
    }
    @Test void disabledAccountAndRevokedTokenRejected()throws Exception{
        jdbc.update("UPDATE app_users SET enabled=false WHERE user_id=?",owner.userId());assertEquals(401,read(owner,"/profile").getResponse().getStatus());
        jdbc.update("UPDATE app_users SET enabled=true,authorization_version=authorization_version+1 WHERE user_id=?",owner.userId());assertEquals(401,read(owner,"/payments").getResponse().getStatus());
    }
    @Test void realRegisteredProfileUsesActualBusinessFields()throws Exception{
        var input=new MerchantRegistration.Input();input.email="profile-"+UUID.randomUUID()+"@example.test";input.firstName="Synthetic";input.lastName="Merchant";input.businessName="Actual registered business";input.mobile="9999999999";input.businessType="OTHER";input.country="IN";input.terms=true;input.password=OLD.toCharArray();input.confirmPassword=OLD.toCharArray();registration.register(input);
        UUID id=jdbc.queryForObject("SELECT user_id FROM app_users WHERE login_normalized=?",UUID.class,input.email);String m=jdbc.queryForObject("SELECT merchant_id FROM merchant_registrations WHERE user_id=?",String.class,id);
        var admin=identity("ADMIN",Set.of());as(admin,()->administration.transition(m,"approve",null,"ISOLATED-PROFILE-REVIEW",true));
        var data=body(read(refreshed(id,"MERCHANT"),"/profile"));assertEquals("Actual registered business",data.get("businessName").asText());assertTrue(data.get("registrationAvailable").asBoolean());assertEquals("IN",data.get("country").asText());assertTrue(data.hasNonNull("approvedAt"));assertFalse(data.has("reviewReference"));
    }
    @Test void expiredSignedJwtIsRejected()throws Exception{
        var now=java.time.Instant.now();var claims=new com.nimbusds.jwt.JWTClaimsSet.Builder().issuer(keys.issuer).audience(keys.audience).subject(owner.userId().toString()).jwtID(UUID.randomUUID().toString()).issueTime(Date.from(now.minusSeconds(1800))).notBeforeTime(Date.from(now.minusSeconds(1800))).expirationTime(Date.from(now.minusSeconds(900))).claim("roles",List.of("MERCHANT")).claim("authorization_version",0).claim("account_status","ACTIVE").build();
        var signed=new com.nimbusds.jwt.SignedJWT(new com.nimbusds.jose.JWSHeader(com.nimbusds.jose.JWSAlgorithm.RS256),claims);signed.sign(new com.nimbusds.jose.crypto.RSASSASigner(keys.privateKey));
        assertEquals(401,mvc.perform(get("/api/v1/merchant/payments").header("Authorization","Bearer "+signed.serialize())).andReturn().getResponse().getStatus());
    }
    @Test void bodyMassAssignmentAndLimitsFailSafely()throws Exception{
        assertEquals(400,mvc.perform(post("/api/v1/merchant/profile/password").with(jwt(owner)).contentType("application/json").content("{\"role\":\"ADMIN\"}")).andReturn().getResponse().getStatus());
        assertEquals(413,mvc.perform(post("/api/v1/merchant/profile/password").with(jwt(owner)).contentType("application/json").content("x".repeat(4097))).andReturn().getResponse().getStatus());
    }
}
