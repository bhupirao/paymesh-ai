package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.databind.*;
import com.paymesh.backend.security.accounts.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

@SpringBootTest(properties={"spring.flyway.default-schema=signup_test","spring.flyway.schemas=signup_test",
    "spring.jpa.properties.hibernate.default_schema=signup_test","paymesh.auth.login.max-attempts=100","paymesh.jwt.issuer=https://issuer.paymesh.test","paymesh.jwt.audience=paymesh-api"})
@AutoConfigureMockMvc
class MerchantRegistrationIntegrationTest {
    static final Path DIR;
    static final AtomicInteger CLIENT = new AtomicInteger();
    static {
        try {
            DIR=Files.createTempDirectory("paymesh-signup-test-");
            var pair=JwtKeyMaterialTest.pair(2048);
            JwtKeyMaterialTest.pem(DIR.resolve("private.pem"),"PRIVATE KEY",pair.getPrivate().getEncoded());
            JwtKeyMaterialTest.pem(DIR.resolve("public.pem"),"PUBLIC KEY",pair.getPublic().getEncoded());
            Files.setPosixFilePermissions(DIR.resolve("private.pem"), java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
        } catch(Exception ex) { throw new ExceptionInInitializerError(ex); }
    }
    @DynamicPropertySource static void keys(DynamicPropertyRegistry r) {
        r.add("paymesh.jwt.private-key-file",()->DIR.resolve("private.pem").toString());
        r.add("paymesh.jwt.public-key-file",()->DIR.resolve("public.pem").toString());
    }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired PasswordEncoder encoder;
    @Autowired MerchantRegistration registration;
    @Autowired PlatformTransactionManager transactions;
    Map<String,Object> input() {
        return new HashMap<>(Map.of("firstName","Ada","lastName","Lovelace","businessName","Test Company",
            "email","signup."+UUID.randomUUID()+"@example.test","mobile","+919876543210","businessType","COMPANY",
            "country","IN","password","A-long-test-passphrase","confirmPassword","A-long-test-passphrase","terms",true));
    }
    org.springframework.test.web.servlet.MvcResult signup(Map<String,Object> body) throws Exception {
        return mvc.perform(post("/api/v1/auth/register").with(r->{r.setRemoteAddr("192.0.2."+CLIENT.incrementAndGet());return r;})
            .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(body))).andReturn();
    }
    String login(String name,String password) throws Exception {
        var result=mvc.perform(post("/api/v1/auth/login").with(r->{r.setRemoteAddr("198.51.100."+CLIENT.incrementAndGet());return r;})
            .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(Map.of("login",name,"password",password)))).andReturn();
        assertEquals(200,result.getResponse().getStatus());
        return json.readTree(result.getResponse().getContentAsString()).get("accessToken").asText();
    }
    @Test void registersHashesAndAuthenticatesPendingWithoutFinancialPrivileges() throws Exception {
        var body=input(); body.put("email",((String)body.get("email")).toUpperCase(Locale.ROOT));
        var result=signup(body); assertEquals(201,result.getResponse().getStatus());
        assertFalse(result.getResponse().getContentAsString().contains((String)body.get("password")));
        assertFalse(json.readTree(result.getResponse().getContentAsString()).has("password"));
        String email=((String)body.get("email")).toLowerCase(Locale.ROOT);
        var row=jdbc.queryForMap("select * from signup_test.app_users where login_normalized=?",email);
        assertEquals("PENDING_APPROVAL",row.get("account_status"));
        assertNotEquals(body.get("password"),row.get("password_hash"));
        assertTrue(encoder.matches((String)body.get("password"),(String)row.get("password_hash")));
        assertEquals(1,jdbc.queryForObject("select count(*) from signup_test.user_roles where user_id=? and role_name='MERCHANT'",Integer.class,row.get("user_id")));
        assertEquals(0,jdbc.queryForObject("select count(*) from signup_test.merchant_memberships where user_id=? and active",Integer.class,row.get("user_id")));
        String token=login(email,(String)body.get("password"));
        var claims=json.readTree(Base64.getUrlDecoder().decode(token.split("\\.")[1]));
        assertEquals("PENDING_APPROVAL",claims.get("account_status").asText());
        String id=UUID.randomUUID().toString();
        for(String suffix:List.of("","/gateway-transactions","/refunds","/refund")) {
            assertEquals(403,mvc.perform(get("/api/v1/payments/"+id+suffix).header("Authorization","Bearer "+token)).andReturn().getResponse().getStatus());
        }
        for(String path:List.of("/api/v1/payments","/api/v1/payments/"+id+"/process","/api/v1/payments/"+id+"/refund","/api/v1/payments/"+id+"/investigate")) {
            assertEquals(403,mvc.perform(post(path).header("Authorization","Bearer "+token).contentType(MediaType.APPLICATION_JSON).content("{}")).andReturn().getResponse().getStatus());
        }
    }
    @Test void duplicateAndConcurrentEmailCannotCreateTwoAccounts() throws Exception {
        var body=input(); var pool=Executors.newFixedThreadPool(2);
        try {
            var gate=new CountDownLatch(1);
            Callable<Integer> task=()->{gate.await();return signup(body).getResponse().getStatus();};
            var a=pool.submit(task);var b=pool.submit(task);gate.countDown();
            var statuses=new ArrayList<>(List.of(a.get(30,TimeUnit.SECONDS),b.get(30,TimeUnit.SECONDS)));Collections.sort(statuses);
            assertEquals(List.of(201,409),statuses);
            assertEquals(409,signup(body).getResponse().getStatus());
            assertEquals(1,jdbc.queryForObject("select count(*) from signup_test.app_users where login_normalized=?",Integer.class,body.get("email")));
        } finally {pool.shutdownNow();}
    }
    @Test void validatesFieldsMismatchAndUntrustedPrivileges() throws Exception {
        for(String field:List.of("firstName","lastName","businessName","email","mobile","businessType","country","password","confirmPassword")) {
            var body=input();body.put(field,""); assertEquals(400,signup(body).getResponse().getStatus(),field);
        }
        var body=input();body.put("terms",false);assertEquals(400,signup(body).getResponse().getStatus());
        body=input();body.put("confirmPassword","different-long-passphrase");assertEquals(400,signup(body).getResponse().getStatus());
        body=input();body.put("role","ADMIN");body.put("merchantId","ATTACKER");body.put("accountStatus","ACTIVE");
        var result=signup(body); // Jackson may reject unknown fields or ignore them; neither can grant privileges.
        assertTrue(Set.of(400,201).contains(result.getResponse().getStatus()));
        if(result.getResponse().getStatus()==201) {
            var row=jdbc.queryForMap("select user_id,account_status from signup_test.app_users where login_normalized=?",body.get("email"));
            assertEquals("PENDING_APPROVAL",row.get("account_status"));
            assertEquals(0,jdbc.queryForObject("select count(*) from signup_test.user_roles where user_id=? and role_name='ADMIN'",Integer.class,row.get("user_id")));
        }
    }
    @Test void transactionRollsBackAllRegistrationRecords() throws Exception {
        var body=input();var dto=json.convertValue(body,MerchantRegistration.Input.class);
        long before=jdbc.queryForObject("select count(*) from signup_test.merchants",Long.class);
        new TransactionTemplate(transactions).execute(status->{ registration.register(dto); status.setRollbackOnly();return null; });
        assertEquals(0,jdbc.queryForObject("select count(*) from signup_test.app_users where login_normalized=?",Integer.class,body.get("email")));
        assertEquals(before,jdbc.queryForObject("select count(*) from signup_test.merchants",Long.class));
        assertEquals(0,jdbc.queryForObject("select count(*) from signup_test.merchant_registrations where email=?",Integer.class,body.get("email")));
    }
    @Test void persistenceFailureRollsBackAndStatusChangeInvalidatesOldToken() throws Exception {
        var body=input(); var dto=json.convertValue(body,MerchantRegistration.Input.class);
        dto.firstName="x".repeat(81);
        assertThrows(RuntimeException.class,()->registration.register(dto));
        assertEquals(0,jdbc.queryForObject("select count(*) from signup_test.app_users where login_normalized=?",Integer.class,body.get("email")));
        body=input();assertEquals(201,signup(body).getResponse().getStatus());
        String token=login((String)body.get("email"),(String)body.get("password"));
        jdbc.update("update signup_test.app_users set account_status='ACTIVE' where login_normalized=?",body.get("email"));
        assertEquals(401,mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+token)).andReturn().getResponse().getStatus());
        // Test-only state transition does not grant verified membership or financial access.
    }

}
