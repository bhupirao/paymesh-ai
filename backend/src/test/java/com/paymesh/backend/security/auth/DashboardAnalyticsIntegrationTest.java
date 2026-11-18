package com.paymesh.backend.security.auth;

import com.paymesh.backend.testing.BusinessJwtTestSupport;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.*;
import org.springframework.test.web.servlet.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest @AutoConfigureMockMvc(print=MockMvcPrint.NONE)
class DashboardAnalyticsIntegrationTest extends BusinessJwtTestSupport {
    @org.springframework.test.context.bean.override.mockito.MockitoBean com.paymesh.backend.security.accounts.AuthenticationClock analyticsClock;@Autowired MockMvc mvc;@Autowired com.fasterxml.jackson.databind.ObjectMapper json;
    Identity owner,other,admin;String mid;final String range="?from=2026-01-01T00:00:00Z&to=2026-01-03T00:00:00Z";
    @BeforeEach void setup()throws Exception{org.mockito.Mockito.when(analyticsClock.now()).thenReturn(java.time.Instant.parse("2026-11-15T12:00:00Z"));mid="analytics-"+UUID.randomUUID();owner=identity("MERCHANT",Set.of(mid));other=identity("MERCHANT",Set.of("analytics-other-"+UUID.randomUUID()));admin=identity("ADMIN",Set.of());}
    UUID payment(String merchant,String currency,String method,String at){UUID id=UUID.randomUUID();jdbc.update("INSERT INTO merchants(merchant_id) VALUES (?) ON CONFLICT DO NOTHING",merchant);jdbc.update("INSERT INTO payments(payment_id,merchant_id,customer_id,amount,currency,payment_method,status,created_at) VALUES (?,?,'synthetic',12.01,?,?,'SUCCESS',?::timestamptz)",id,merchant,currency,method,at);return id;}
    MvcResult call(Identity who,String prefix,String query)throws Exception{return mvc.perform(get("/api/v1/"+prefix+"/analytics"+query).with(jwt(who))).andReturn();}
    com.fasterxml.jackson.databind.JsonNode body(MvcResult r)throws Exception{return json.readTree(r.getResponse().getContentAsByteArray());}
    @Test void merchantOwnershipAndCurrencyGroups()throws Exception{
        payment(mid,"INR","UPI","2026-01-01T01:00:00Z");payment(mid,"USD","CARD","2026-01-02T01:00:00Z");payment("analytics-unowned","INR","UPI","2026-01-01T01:00:00Z");
        var r=call(owner,"merchant",range);assertEquals(200,r.getResponse().getStatus());var d=body(r);assertEquals(2,d.get("paymentCounts").size());assertEquals("12.01",d.get("amountComparison").get(0).get("paymentAmount").asText());assertEquals(2,d.get("paymentMethods").size());assertEquals(4,d.get("dailyPayments").size());
        assertTrue(body(call(other,"merchant",range)).get("paymentCounts").isEmpty());assertEquals(1,body(call(owner,"merchant",range+"&currency=USD")).get("paymentMethods").size());
    }
    @Test void utcHalfOpenBoundariesAndRefundOwnTime()throws Exception{
        UUID p=payment(mid,"INR","CARD","2026-01-01T00:00:00Z");payment(mid,"INR","UPI","2026-01-02T23:59:59.999999Z");payment(mid,"INR","CARD","2026-01-03T00:00:00Z");payment(mid,"INR","CARD","2025-12-31T23:59:59.999999Z");
        jdbc.update("INSERT INTO refunds(refund_id,payment_id,amount,status,created_at) VALUES (?,?,0.01,'SUCCESS','2026-01-02T00:00:00Z'::timestamptz)",UUID.randomUUID(),p);
        var d=body(call(owner,"merchant",range+"&currency=INR"));assertEquals(2,d.get("paymentCounts").get(0).get("count").asInt());assertEquals(1,d.get("dailyPayments").get(0).get("count").asInt());assertEquals(1,d.get("dailyPayments").get(1).get("count").asInt());assertEquals("24.02",d.get("amountComparison").get(0).get("paymentAmount").asText());assertEquals("0.01",d.get("amountComparison").get(0).get("refundAmount").asText());
        assertTrue(d.get("range").get("endExclusive").asBoolean());assertEquals("UTC",d.get("range").get("timezone").asText());
    }
    @Test void adminAuthorizationAndMerchantFilter()throws Exception{
        payment(mid,"INR","UPI","2026-01-01T00:00:00Z");assertEquals(403,call(owner,"admin",range).getResponse().getStatus());assertEquals(403,call(admin,"merchant",range).getResponse().getStatus());assertEquals(401,mvc.perform(get("/api/v1/admin/analytics")).andReturn().getResponse().getStatus());
        var d=body(call(admin,"admin",range+"&merchantId="+mid));assertEquals(1,d.get("paymentCounts").get(0).get("count").asInt());assertTrue(d.has("merchantCounts"));
    }
    @Test void emptyDatasetsHaveBoundedZeroDaysNoFakeMoney()throws Exception{
        var d=body(call(owner,"merchant",range+"&currency=INR"));assertTrue(d.get("paymentCounts").isEmpty());assertTrue(d.get("amountComparison").isEmpty());assertEquals(2,d.get("dailyPayments").size());assertEquals(0,d.get("dailyPayments").get(0).get("count").asInt());
    }
    @Test void rangesAndIdentitySelectorsAreBounded()throws Exception{
        for(String p:List.of("?from=2026-01-01T00:00:00Z","?from=2026-01-01T00:01:00Z&to=2026-01-02T00:00:00Z","?from=2026-01-02T00:00:00Z&to=2026-01-01T00:00:00Z","?from=2026-01-01T00:00:00Z&to=2026-05-01T00:00:00Z","?currency=EUR","?merchantId=OTHER","?from=bad&to=bad","?currency=INR&currency=USD"))assertEquals(400,call(owner,"merchant",p).getResponse().getStatus(),p);
    }
    @Test void loginIncludesSafeOwnIdentityWithoutChangingTokenLifetime()throws Exception{
        String password="synthetic-account-menu-password";jdbc.update("UPDATE app_users SET password_hash=? WHERE user_id=?",passwordEncoder.encode(password),owner.userId());String login=jdbc.queryForObject("SELECT login_normalized FROM app_users WHERE user_id=?",String.class,owner.userId());
        var response=mvc.perform(post("/api/v1/auth/login").contentType("application/json").content(json.writeValueAsBytes(Map.of("login",login,"password",password)))).andReturn();assertEquals(200,response.getResponse().getStatus());assertEquals(login,body(response).get("login").asText());assertEquals(900,body(response).get("expiresIn").asInt());assertFalse(body(response).has("password"));
    }
    @Test void existingFinancialRowsUnchangedByAnalytics()throws Exception{
        var before=jdbc.queryForList("SELECT row_to_json(t)::text FROM payments t ORDER BY payment_id");call(owner,"merchant",range);call(admin,"admin",range);assertEquals(before,jdbc.queryForList("SELECT row_to_json(t)::text FROM payments t ORDER BY payment_id"));
    }
}
