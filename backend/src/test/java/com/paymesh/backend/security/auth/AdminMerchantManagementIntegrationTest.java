package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.databind.*;
import com.paymesh.backend.testing.BusinessJwtTestSupport;
import com.paymesh.backend.security.accounts.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.*;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

@SpringBootTest(properties={"paymesh.auth.login.max-attempts=100","paymesh.sessions.origin=https://admin.paymesh.test"})
@AutoConfigureMockMvc(print=MockMvcPrint.NONE)
class AdminMerchantManagementIntegrationTest extends BusinessJwtTestSupport {
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired MerchantRegistration registration;
    @MockitoSpyBean SecurityAuditEventRepository audits;
    @MockitoSpyBean MerchantRepository registry;
    Identity admin;
    static final String PASSWORD="test-only-strong-merchant-password";
    record Pending(String merchantId,UUID id,String email){}
    @BeforeEach void adminIdentity()throws Exception{admin=identity("ADMIN",Set.of());}
    Pending pending(){
        MerchantRegistration.Input p=new MerchantRegistration.Input();p.email="admin-mgmt-"+UUID.randomUUID()+"@example.test";
        p.firstName="Synthetic";p.lastName="Test";p.businessName="Test business";p.mobile="9999999999";p.businessType="OTHER";p.country="IN";p.terms=true;p.password=PASSWORD.toCharArray();p.confirmPassword=PASSWORD.toCharArray();registration.register(p);
        var row=jdbc.queryForMap("SELECT u.user_id,r.merchant_id FROM app_users u JOIN merchant_registrations r ON r.user_id=u.user_id WHERE u.login_normalized=?",p.email);
        return new Pending((String)row.get("merchant_id"),(UUID)row.get("user_id"),p.email);
    }
    MvcResult getAdmin(String path)throws Exception{return mvc.perform(get("/api/v1/admin"+path).with(jwt(admin))).andReturn();}
    MvcResult action(Identity actor,Pending p,String action,Map<String,Object> fields)throws Exception{
        var body=new HashMap<>(fields);body.put("merchantId",p.merchantId());
        return mvc.perform(post("/api/v1/admin/merchant/"+action).with(jwt(actor)).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(body))).andReturn();
    }
    int code(MvcResult r){return r.getResponse().getStatus();}
    Map<String,Object> approve(){return Map.of("reviewReference","ISOLATED-OWNERSHIP-REVIEW","ownershipAttested",true);}
    JsonNode body(MvcResult r)throws Exception{return json.readTree(r.getResponse().getContentAsByteArray());}
    String login(String name,String password,boolean browser)throws Exception{
        var request=post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(Map.of("login",name,"password",password)));
        if(browser)request.header("Origin","https://admin.paymesh.test").header("X-PayMesh-CSRF","1");
        var response=mvc.perform(request).andReturn();assertEquals(200,code(response));return body(response).get("accessToken").asText();
    }
    @Test void adminOnlyEndpointsAndUnmatchedMethodsFailClosed()throws Exception{
        for(String path:List.of("/dashboard","/merchants","/payments","/refunds","/audit","/accounts","/profile")){
            assertEquals(401,code(mvc.perform(get("/api/v1/admin"+path)).andReturn()));
            assertEquals(403,code(mvc.perform(get("/api/v1/admin"+path).with(jwt(caller))).andReturn()));
            assertEquals(200,code(getAdmin(path)));
        }
        assertEquals(403,code(mvc.perform(post("/api/v1/admin/unknown").with(jwt(admin))).andReturn()));
    }
    @Test void pendingAccountCanSignInButCannotReadAdminOrFinancialData()throws Exception{
        var p=pending();String token=login(p.email(),PASSWORD,false);
        assertEquals(403,code(mvc.perform(get("/api/v1/admin/merchants").header("Authorization","Bearer "+token)).andReturn()));
        assertEquals(403,code(mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+token)).andReturn()));
    }
    @Test void approvalIsAtomicAndAuditsRealAdminOwnershipAttestation()throws Exception{
        var p=pending();assertEquals(200,code(action(admin,p,"approve",approve())));
        var account=jdbc.queryForMap("SELECT * FROM app_users WHERE user_id=?",p.id());assertEquals("ACTIVE",account.get("account_status"));assertEquals(1L,((Number)account.get("authorization_version")).longValue());
        var m=jdbc.queryForMap("SELECT * FROM merchants WHERE merchant_id=?",p.merchantId());assertEquals(true,m.get("active"));assertEquals(true,m.get("verified"));assertEquals(admin.userId(),m.get("verified_by"));
        assertTrue(jdbc.queryForObject("SELECT active FROM merchant_memberships WHERE user_id=?",Boolean.class,p.id()));
        var a=audits.findByEventTypeAndResourceId("MERCHANT_APPROVE",p.merchantId());assertEquals(1,a.size());assertEquals(admin.userId(),a.getFirst().getActorUserId());assertEquals("ISOLATED-OWNERSHIP-REVIEW",a.getFirst().getMetadata().get("reviewReference"));
    }
    @Test void approvalNeedsAttestationAndRepeatedApprovalHasNoDuplicateSuccess()throws Exception{
        var p=pending();assertEquals(400,code(action(admin,p,"approve",Map.of("ownershipAttested",false,"reviewReference","REVIEW"))));
        assertEquals(200,code(action(admin,p,"approve",approve())));assertEquals(409,code(action(admin,p,"approve",approve())));
        assertEquals(1,audits.findByEventTypeAndResourceId("MERCHANT_APPROVE",p.merchantId()).size());
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM merchant_memberships WHERE user_id=?",Integer.class,p.id()));
    }
    @Test void disposableApprovalReferenceRejectsSpacesAndAcceptsBoundedIdentifier()throws Exception{
        var p=pending();
        assertEquals(400,code(action(admin,p,"approve",Map.of("ownershipAttested",true,"reviewReference","CI disposable fixture ownership"))));
        assertEquals("PENDING_APPROVAL",jdbc.queryForObject("SELECT account_status FROM app_users WHERE user_id=?",String.class,p.id()));
        assertFalse(jdbc.queryForObject("SELECT verified FROM merchants WHERE merchant_id=?",Boolean.class,p.merchantId()));
        assertFalse(jdbc.queryForObject("SELECT active FROM merchant_memberships WHERE user_id=?",Boolean.class,p.id()));
        assertEquals(0,audits.findByEventTypeAndResourceId("MERCHANT_APPROVE",p.merchantId()).size());
        assertEquals(200,code(action(admin,p,"approve",Map.of("ownershipAttested",true,"reviewReference","CI-DISPOSABLE-FIXTURE-OWNERSHIP"))));
        assertEquals("ACTIVE",jdbc.queryForObject("SELECT account_status FROM app_users WHERE user_id=?",String.class,p.id()));
        assertEquals("CI-DISPOSABLE-FIXTURE-OWNERSHIP",jdbc.queryForObject("SELECT review_reference FROM merchant_administration WHERE merchant_id=?",String.class,p.merchantId()));
        assertEquals(1,audits.findByEventTypeAndResourceId("MERCHANT_APPROVE",p.merchantId()).size());
    }
    @Test void rejectionRequiresBoundedReasonAndIsTerminal()throws Exception{
        var p=pending();assertEquals(400,code(action(admin,p,"reject",Map.of("reason"," "))));
        assertEquals(400,code(action(admin,p,"reject",Map.of("reason","x".repeat(501)))));
        assertEquals(200,code(action(admin,p,"reject",Map.of("reason","Synthetic review declined"))));
        assertEquals("REJECTED",jdbc.queryForObject("SELECT account_status FROM app_users WHERE user_id=?",String.class,p.id()));
        assertEquals(409,code(action(admin,p,"approve",approve())));assertEquals(409,code(action(admin,p,"reactivate",Map.of("reason","Try again"))));
    }
    @Test void suspendAndReactivatePreservePreviouslyApprovedAttestation()throws Exception{
        var p=pending();assertEquals(409,code(action(admin,p,"reactivate",Map.of("reason","Cannot bypass approval"))));
        assertEquals(200,code(action(admin,p,"approve",approve())));Object approved=jdbc.queryForObject("SELECT approved_at FROM merchant_administration WHERE merchant_id=?",Object.class,p.merchantId());
        assertEquals(200,code(action(admin,p,"suspend",Map.of("reason","Review pause"))));
        assertFalse(jdbc.queryForObject("SELECT active FROM merchants WHERE merchant_id=?",Boolean.class,p.merchantId()));
        assertEquals("SUSPENDED",jdbc.queryForObject("SELECT account_status FROM app_users WHERE user_id=?",String.class,p.id()));
        assertEquals(200,code(action(admin,p,"reactivate",Map.of("reason","Review completed"))));
        assertEquals("ACTIVE",jdbc.queryForObject("SELECT account_status FROM app_users WHERE user_id=?",String.class,p.id()));assertEquals(approved,jdbc.queryForObject("SELECT approved_at FROM merchant_administration WHERE merchant_id=?",Object.class,p.merchantId()));
    }
    @Test void statusTransitionsRevokeBrowserFamiliesAndOldSignedTokens()throws Exception{
        var p=pending();String pendingToken=login(p.email(),PASSWORD,true);
        assertEquals(200,code(action(admin,p,"approve",approve())));
        assertEquals(401,code(mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+pendingToken)).andReturn()));
        String activeToken=login(p.email(),PASSWORD,true);assertEquals(200,code(action(admin,p,"suspend",Map.of("reason","Security review"))));
        assertEquals(401,code(mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+activeToken)).andReturn()));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM auth_sessions WHERE user_id=? AND revoked_at IS NULL",Integer.class,p.id()));
        String limited=login(p.email(),PASSWORD,false);assertEquals(403,code(mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+limited)).andReturn()));
    }
    @Test void concurrentApprovalHasOneWinnerAndOneAudit()throws Exception{
        var p=pending();var pool=Executors.newFixedThreadPool(2);var start=new CountDownLatch(1);
        try{Callable<Integer> job=()->{start.await();return code(action(admin,p,"approve",approve()));};var a=pool.submit(job);var b=pool.submit(job);start.countDown();var results=new ArrayList<>(List.of(a.get(30,TimeUnit.SECONDS),b.get(30,TimeUnit.SECONDS)));Collections.sort(results);assertEquals(List.of(200,409),results);}
        finally{pool.shutdownNow();}
        assertEquals(1,audits.findByEventTypeAndResourceId("MERCHANT_APPROVE",p.merchantId()).size());
    }
    @Test void auditFailureRollsBackAllApprovalAndRevocationWrites()throws Exception{
        var p=pending();login(p.email(),PASSWORD,true);
        doThrow(new IllegalStateException("test-only-audit-failure")).when(audits).saveAndFlush(argThat(e->e!=null&&e.getEventType().equals("MERCHANT_APPROVE")));
        assertEquals(503,code(action(admin,p,"approve",approve())));
        assertEquals("PENDING_APPROVAL",jdbc.queryForObject("SELECT account_status FROM app_users WHERE user_id=?",String.class,p.id()));
        assertFalse(jdbc.queryForObject("SELECT verified FROM merchants WHERE merchant_id=?",Boolean.class,p.merchantId()));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM auth_sessions WHERE user_id=? AND revoked_at IS NULL",Integer.class,p.id()));
    }
    @Test void registryFailureRollsBackAccountUpdate()throws Exception{
        var p=pending();doThrow(new IllegalStateException("test-only-update-failure")).when(registry).saveAndFlush(argThat(m->m!=null&&m.getMerchantId().equals(p.merchantId())));
        assertEquals(503,code(action(admin,p,"approve",approve())));assertEquals(0L,jdbc.queryForObject("SELECT authorization_version FROM app_users WHERE user_id=?",Long.class,p.id()));
        assertEquals("PENDING_APPROVAL",jdbc.queryForObject("SELECT status FROM merchant_administration WHERE merchant_id=?",String.class,p.merchantId()));
    }
    @Test void paginationFiltersAndAllowlistedSortAreBounded()throws Exception{
        var p=pending();var response=getAdmin("/merchants?page=0&size=1&status=PENDING_APPROVAL&search="+p.email());assertEquals(200,code(response));assertEquals(1,body(response).get("items").size());
        for(String query:List.of("size=101","page=-1","sort=created_at%20DESC","currency=EUR","status=NOT_A_STATUS","unknown=bad","from=not-a-date","from=2026-12-01T00:00:00Z&to=2026-01-01T00:00:00Z"))assertEquals(400,code(getAdmin("/payments?"+query)));
        assertEquals(400,code(getAdmin("/accounts?currency=USD")));
        assertEquals(400,code(mvc.perform(get("/api/v1/admin/payments").param("size","1","2").with(jwt(admin))).andReturn()));
    }
    @Test void dashboardUsesSeparateExactCurrencyStatusAmountsAndActualRecentRecords()throws Exception{
        String merchant="stats-"+UUID.randomUUID();identity("MERCHANT",Set.of(merchant));
        for(String currency:List.of("INR","USD"))jdbc.update("INSERT INTO payments(payment_id,merchant_id,customer_id,amount,currency,payment_method,status) VALUES (?,?,?,?::numeric,?,'CARD','SUCCESS')",UUID.randomUUID(),merchant,"test-stats",currency.equals("INR")?"999999999999.99":"25.01",currency);
        var response=getAdmin("/dashboard?merchantId="+merchant);assertEquals(200,code(response));var totals=body(response).get("paymentAmounts");assertEquals(2,totals.size());
        assertEquals("999999999999.99",totals.get(0).get("amount").asText());assertEquals("INR",totals.get(0).get("currency").asText());assertEquals("25.01",totals.get(1).get("amount").asText());
    }
    @Test void detailsAndListsExcludeCredentialsAndInternalAuditMetadata()throws Exception{
        for(String path:List.of("/merchants","/accounts","/profile","/audit")){
            var r=getAdmin(path);assertEquals(200,code(r));String text=r.getResponse().getContentAsString();
            for(String forbidden:List.of("password_hash","passwordHash","token_digest","refreshToken","otp_digest","metadata","$2a$","$2b$"))assertFalse(text.contains(forbidden));
            assertEquals("no-store",r.getResponse().getHeader("Cache-Control"));
        }
        assertEquals(404,code(getAdmin("/refunds/"+UUID.randomUUID())));
    }
    @Test void massAssignmentAndOversizedAdminBodiesAreRejected()throws Exception{
        var p=pending();assertEquals(400,code(action(admin,p,"approve",Map.of("ownershipAttested",true,"reviewReference","REVIEW","role","ADMIN"))));
        assertEquals(413,code(mvc.perform(post("/api/v1/admin/merchant/reject").with(jwt(admin)).contentType(MediaType.APPLICATION_JSON).content("x".repeat(4097))).andReturn()));
    }
    @Test void passwordChangeRequiresCurrentMatchingPasswordAndInvalidatesSessions()throws Exception{
        String old="isolated-old-admin-password",next="isolated-new-admin-password";
        jdbc.update("UPDATE app_users SET password_hash=? WHERE user_id=?",passwordEncoder.encode(old),admin.userId());
        String token=login("fixture."+admin.userId(),old,true);
        var request=post("/api/v1/admin/profile/password").header("Authorization","Bearer "+token).contentType(MediaType.APPLICATION_JSON);
        assertEquals(400,code(mvc.perform(request.content(json.writeValueAsBytes(Map.of("currentPassword",old,"newPassword",next,"confirmPassword","different-password")))).andReturn()));
        assertEquals(403,code(mvc.perform(post("/api/v1/admin/profile/password").header("Authorization","Bearer "+token).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(Map.of("currentPassword","wrong-password-test","newPassword",next,"confirmPassword",next)))).andReturn()));
        assertEquals(200,code(mvc.perform(post("/api/v1/admin/profile/password").header("Authorization","Bearer "+token).contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(Map.of("currentPassword",old,"newPassword",next,"confirmPassword",next)))).andReturn()));
        assertEquals(401,code(mvc.perform(get("/api/v1/admin/profile").header("Authorization","Bearer "+token)).andReturn()));
        assertNotNull(login("fixture."+admin.userId(),next,false));
        var oldLogin=mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(Map.of("login","fixture."+admin.userId(),"password",old)))).andReturn();assertEquals(401,code(oldLogin));
        assertEquals(1,audits.findByEventTypeAndResourceId("ADMIN_PASSWORD_CHANGED",admin.userId().toString()).size());
    }
    @Test void lifecycleActionsPreserveFinancialRowsAndMerchantIsolation()throws Exception{
        var p=pending();assertEquals(200,code(action(admin,p,"approve",approve())));UUID payment=UUID.randomUUID();
        jdbc.update("INSERT INTO payments(payment_id,merchant_id,customer_id,amount,currency,payment_method,status) VALUES (?,?,'test-only',25,'USD','CARD','SUCCESS')",payment,p.merchantId());
        jdbc.update("INSERT INTO refunds(refund_id,payment_id,amount,status) VALUES (?,?,5,'SUCCESS')",UUID.randomUUID(),payment);
        var before=jdbc.queryForList("SELECT row_to_json(p)::text AS row FROM payments p WHERE payment_id=?",payment);
        var refunds=jdbc.queryForList("SELECT row_to_json(f)::text AS row FROM refunds f WHERE payment_id=?",payment);
        String owner=login(p.email(),PASSWORD,false);assertEquals(200,code(mvc.perform(get("/api/v1/payments/"+payment).header("Authorization","Bearer "+owner)).andReturn()));
        assertEquals(404,code(mvc.perform(get("/api/v1/payments/"+payment).with(jwt(caller))).andReturn()));
        assertEquals(200,code(getAdmin("/payments/"+payment)));
        assertEquals(200,code(action(admin,p,"suspend",Map.of("reason","Test pause"))));assertEquals(200,code(action(admin,p,"reactivate",Map.of("reason","Test resume"))));
        assertEquals(before,jdbc.queryForList("SELECT row_to_json(p)::text AS row FROM payments p WHERE payment_id=?",payment));assertEquals(refunds,jdbc.queryForList("SELECT row_to_json(f)::text AS row FROM refunds f WHERE payment_id=?",payment));
    }
}
