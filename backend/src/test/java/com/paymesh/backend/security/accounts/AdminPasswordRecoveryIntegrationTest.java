package com.paymesh.backend.security.accounts;

import java.util.*;
import java.nio.file.*;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.MockMvcPrint;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@SpringBootTest(properties={"spring.flyway.default-schema=recovery_test","spring.flyway.schemas=recovery_test",
    "spring.jpa.properties.hibernate.default_schema=recovery_test"})
@AutoConfigureMockMvc(print=MockMvcPrint.NONE)
@Import({AdminPasswordRecoveryTransaction.class,DisposableMerchantPasswordRecoveryTransaction.class})
@ExtendWith(OutputCaptureExtension.class)
class AdminPasswordRecoveryIntegrationTest {
    private static final Path KEY_DIRECTORY;
    static {
        try {
            KEY_DIRECTORY=Files.createTempDirectory("paymesh-recovery-test-keys-");
            var generator=java.security.KeyPairGenerator.getInstance("RSA");generator.initialize(2048);var pair=generator.generateKeyPair();
            Files.writeString(KEY_DIRECTORY.resolve("private.pem"),"-----BEGIN PRIVATE KEY-----\n"+Base64.getMimeEncoder(64,new byte[]{10}).encodeToString(pair.getPrivate().getEncoded())+"\n-----END PRIVATE KEY-----\n");
            Files.setPosixFilePermissions(KEY_DIRECTORY.resolve("private.pem"),java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
            Files.writeString(KEY_DIRECTORY.resolve("public.pem"),"-----BEGIN PUBLIC KEY-----\n"+Base64.getMimeEncoder(64,new byte[]{10}).encodeToString(pair.getPublic().getEncoded())+"\n-----END PUBLIC KEY-----\n");
        } catch(Exception ex) {throw new ExceptionInInitializerError(ex);}
    }
    @DynamicPropertySource static void keys(DynamicPropertyRegistry registry) {
        registry.add("paymesh.jwt.private-key-file",()->KEY_DIRECTORY.resolve("private.pem").toString());
        registry.add("paymesh.jwt.public-key-file",()->KEY_DIRECTORY.resolve("public.pem").toString());
        registry.add("paymesh.jwt.issuer",()->"https://recovery.paymesh.test");registry.add("paymesh.jwt.audience",()->"paymesh-api");
    }
    @Autowired MockMvc mvc;
    @Autowired com.fasterxml.jackson.databind.ObjectMapper json;
    @Autowired AdminPasswordRecoveryTransaction recovery;
    @Autowired DisposableMerchantPasswordRecoveryTransaction merchantRecovery;
    @Autowired AppUserRepository users;
    @Autowired UserRoleRepository roles;
    @Autowired AccountPasswords passwords;
    @Autowired AccountCredentials credentials;
    @Autowired AccountTokenStateService tokens;
    @Autowired JdbcTemplate jdbc;
    @Autowired DataSource source;
    @MockitoBean AdminRecoveryDatabaseGuard guard; // Test only: real runner targets a fresh isolated cluster, never paymesh_demo.
    @MockitoSpyBean SecurityAuditEventRepository events;
    AppUser account(AccountRole role) {
        AppUser user=users.saveAndFlush(new AppUser("recovery."+UUID.randomUUID(), passwords.hash("old-test-passphrase".toCharArray())));
        roles.saveAndFlush(new UserRole(user.getUserId(),role,null));return user;
    }
    List<Map<String,Object>> snapshot(String table) {return jdbc.queryForList("select row_to_json(t)::text as record from recovery_test."+table+" t order by row_to_json(t)::text");}
    @Test void resetsExistingAdminPreservesIdentityInvalidatesPriorAuthorizationAndFinancialState(CapturedOutput output) throws Exception {
        AppUser original=account(AccountRole.ADMIN);
        var principal=credentials.authenticate(original.getLoginNormalized(),"old-test-passphrase".toCharArray());
        var old=tokens.forAuthenticated(principal);
        var response=mvc.perform(post("/api/v1/auth/login").contentType("application/json")
                .content(json.writeValueAsBytes(Map.of("login",original.getLoginNormalized(),"password","old-test-passphrase")))).andReturn().getResponse();
        assertEquals(200,response.getStatus());
        String jwt=json.readTree(response.getContentAsString()).get("accessToken").asText();
        String endpoint="/api/v1/payments/"+UUID.randomUUID();
        assertEquals(404,mvc.perform(get(endpoint).header("Authorization","Bearer "+jwt)).andReturn().getResponse().getStatus());
        // Existing synthetic records in the disposable cluster must survive byte-for-byte snapshots.
        var merchant=account(AccountRole.MERCHANT);String merchantId="recovery-merchant-"+UUID.randomUUID();UUID payment=UUID.randomUUID();
        jdbc.update("insert into recovery_test.merchants(merchant_id) values (?)",merchantId);
        jdbc.update("insert into recovery_test.merchant_memberships(user_id,merchant_id) values (?,?)",merchant.getUserId(),merchantId);
        jdbc.update("insert into recovery_test.merchant_registrations(user_id,merchant_id,first_name,last_name,business_name,email,mobile,business_type,country,terms_version) values (?,?,'Synthetic','Merchant','Test Business',?,'1234567890','COMPANY','IN','test')",merchant.getUserId(),merchantId,merchant.getLoginNormalized()+"@example.test");
        jdbc.update("insert into recovery_test.payments(payment_id,merchant_id,customer_id,amount,currency,payment_method,status) values (?,?,'synthetic-customer',100,'INR','UPI','SUCCESS')",payment,merchantId);
        jdbc.update("insert into recovery_test.refunds(refund_id,payment_id,amount,status) values (?,?,20,'SUCCESS')",UUID.randomUUID(),payment);
        jdbc.update("insert into recovery_test.payment_gateway_transactions(id,payment_id,gateway_name,status) values (?,?,'MOCK_RAZORPAY','SUCCESS')",UUID.randomUUID(),payment);
        var merchantBefore=users.findById(merchant.getUserId()).orElseThrow().passwordHash();
        var before=new HashMap<String,List<Map<String,Object>>>();
        for(String table:List.of("merchants","merchant_memberships","merchant_registrations","payments","refunds","payment_gateway_transactions","idempotency_keys","simulated_gateway_outcomes","webhook_events","reconciliation_jobs","reconciliation_attempts","roles","user_roles")) before.put(table,snapshot(table));
        char[] next="new-test-secret-passphrase".toCharArray();char[] confirm=next.clone();
        try {
            assertEquals(original.getUserId(),recovery.reset(original.getLoginNormalized().toUpperCase(Locale.ROOT),next,confirm));
            AppUser changed=users.findById(original.getUserId()).orElseThrow();
            assertEquals(original.getLoginNormalized(),changed.getLoginNormalized());assertTrue(changed.isEnabled());
            assertEquals("ACTIVE",changed.getAccountStatus());assertEquals(original.getCreatedAt().truncatedTo(java.time.temporal.ChronoUnit.MICROS),changed.getCreatedAt());
            assertEquals(old.authorizationVersion()+1,changed.getAuthorizationVersion());
            assertEquals(List.of("ADMIN"),roles.roles(original.getUserId()));
            assertDoesNotThrow(()->credentials.authenticate(changed.getLoginNormalized(),next));
            assertThrows(AccountAccessDeniedException.class,()->credentials.authenticate(changed.getLoginNormalized(),"old-test-passphrase".toCharArray()));
            assertThrows(AccountAccessDeniedException.class,()->tokens.forAuthenticated(principal));
            assertNotEquals(old.authorizationVersion(),tokens.forToken(changed.getUserId()).authorizationVersion());
            assertEquals(401,mvc.perform(get(endpoint).header("Authorization","Bearer "+jwt)).andReturn().getResponse().getStatus());
            var audit=events.findByEventTypeAndResourceId("ADMIN_PASSWORD_RECOVERED",changed.getUserId().toString());
            assertEquals(1,audit.size());assertNull(audit.getFirst().getActorUserId());assertNull(audit.getFirst().getActorIdentifier());
            assertEquals(Map.of("source","offline_operator_recovery"),audit.getFirst().getMetadata());
            assertEquals(merchantBefore,users.findById(merchant.getUserId()).orElseThrow().passwordHash());
            for(var entry:before.entrySet()) assertEquals(entry.getValue(),snapshot(entry.getKey()),entry.getKey());
            assertFalse(output.getAll().contains(new String(next)));assertFalse(output.getAll().contains(changed.passwordHash()));
        } finally {Arrays.fill(next,'\0');Arrays.fill(confirm,'\0');}
    }
    @Test void rejectsMissingMerchantDisabledPendingAndMixedRoleAccounts() {
        var merchant=account(AccountRole.MERCHANT);var disabled=account(AccountRole.ADMIN);var pending=account(AccountRole.ADMIN);var mixed=account(AccountRole.ADMIN);
        disabled.setEnabled(false);users.saveAndFlush(disabled);pending.pendingApproval();users.saveAndFlush(pending);
        roles.saveAndFlush(new UserRole(mixed.getUserId(),AccountRole.MERCHANT,null));
        for(String login:List.of("missing.account",merchant.getLoginNormalized(),disabled.getLoginNormalized(),pending.getLoginNormalized(),mixed.getLoginNormalized())) {
            var before=snapshot("app_users");
            assertThrows(AccountOperationException.class,()->recovery.reset(login,"new-test-passphrase".toCharArray(),"new-test-passphrase".toCharArray()));
            assertEquals(before,snapshot("app_users"));
        }
    }
    @Test void rejectsWeakPasswordsAndMismatchWithoutWrites() {
        var user=account(AccountRole.ADMIN);var before=snapshot("app_users");
        for(String value:List.of("short","x".repeat(73),"é".repeat(37),"valid-but-nul\0password")) {
            assertThrows(IllegalArgumentException.class,()->recovery.reset(user.getLoginNormalized(),value.toCharArray(),value.toCharArray()));
        }
        assertThrows(IllegalArgumentException.class,()->recovery.reset(user.getLoginNormalized(),"new-test-passphrase".toCharArray(),"different-passphrase".toCharArray()));
        assertEquals(before,snapshot("app_users"));
    }
    @Test void auditFailureRollsBackHashVersionAndSuccessAudit(CapturedOutput output) {
        var user=account(AccountRole.ADMIN);var before=snapshot("app_users");
        doThrow(new IllegalStateException("test-only-private-exception")).when(events).saveAndFlush(argThat(event->event!=null&&"ADMIN_PASSWORD_RECOVERED".equals(event.getEventType())));
        try {
            assertThrows(RuntimeException.class,()->recovery.reset(user.getLoginNormalized(),"new-test-passphrase".toCharArray(),"new-test-passphrase".toCharArray()));
            assertEquals(before,snapshot("app_users"));assertTrue(events.findByEventTypeAndResourceId("ADMIN_PASSWORD_RECOVERED",user.getUserId().toString()).isEmpty());
            assertFalse(output.getAll().contains("test-only-private-exception"));
        } finally {reset(events);}
    }
    @Test void failedIdentityGuardPreventsWrites() {
        var user=account(AccountRole.ADMIN);var before=snapshot("app_users");
        doThrow(new IllegalStateException("wrong target")).when(guard).verify(any());
        try {assertThrows(IllegalStateException.class,()->recovery.reset(user.getLoginNormalized(),"new-test-passphrase".toCharArray(),"new-test-passphrase".toCharArray()));assertEquals(before,snapshot("app_users"));}
        finally {reset(guard);}
    }
    @Test void minimalOfflineContextHasNoWebMigrationsOrFinancialRunners() {
        var application=InitialAdminProvisioner.offlineApplication(AdminPasswordRecovery.RecoveryConfiguration.class);
        application.addInitializers(context->context.getBeanFactory().registerSingleton("dataSource",source));
        try(var context=application.run("--spring.config.location=classpath:/application.properties","--spring.main.web-application-type=none",
                "--spring.flyway.enabled=false","--spring.sql.init.mode=never","--spring.jpa.hibernate.ddl-auto=validate",
                "--spring.jpa.properties.hibernate.default_schema=recovery_test","--logging.level.root=OFF")) {
            assertFalse(context instanceof org.springframework.boot.web.context.WebServerApplicationContext);
            assertEquals(0,context.getBeansOfType(org.flywaydb.core.Flyway.class).size());
            assertEquals(0,context.getBeansOfType(org.springframework.boot.ApplicationRunner.class).size());
            assertEquals(0,context.getBeansOfType(org.springframework.boot.CommandLineRunner.class).size());
            assertFalse(context.containsBean("settlementScheduler"));assertFalse(context.containsBean("initialAdminBootstrap"));
            assertNotNull(context.getBean(AdminPasswordRecoveryTransaction.class));
        }
    }
    @Test void realPostgresInetTextIncludesMaskButHostExtractionMatchesLiteralLoopback() throws Exception {
        try(var connection=source.getConnection()) {
            connection.setReadOnly(true);
            try(var statement=connection.createStatement()) {
                // Exercise the exact production SQL on the real isolated TCP server, without bypassing its target guard.
                try(var identity=statement.executeQuery(AdminRecoveryDatabaseGuard.IDENTITY_QUERY)) {
                    assertTrue(identity.next());assertTrue(identity.getString(1).startsWith("paymesh_isolated_"));
                    assertEquals("paymesh_test",identity.getString(2));assertEquals("127.0.0.1",identity.getString(3));
                    assertNotEquals(5432,identity.getInt(4));
                }
                try(var row=statement.executeQuery("SELECT inet_server_addr(), inet_server_addr()::text, host(inet_server_addr()), inet_server_addr()::text = '127.0.0.1', host(inet_server_addr()) = '127.0.0.1'")) {
                    assertTrue(row.next());assertEquals("127.0.0.1",row.getString(1));
                    assertEquals("127.0.0.1/32",row.getString(2));assertEquals("127.0.0.1",row.getString(3));
                    assertFalse(row.getBoolean(4));assertTrue(row.getBoolean(5));
                }
            }
        }
    }

    @Test void disposableMerchantResetGuardsRollbackRevocationAndPreservation(CapturedOutput output) {
        var u=new AppUser(DisposableMerchantPasswordRecoveryTransaction.LOGIN,passwords.hash("old-test-passphrase".toCharArray()));u.pendingApproval();users.saveAndFlush(u);
        roles.saveAndFlush(new UserRole(u.getUserId(),AccountRole.MERCHANT,null));
        String mid="offline-disposable-test",login=u.getLoginNormalized(),next="new-merchant-test-passphrase";
        jdbc.update("insert into recovery_test.merchants(merchant_id) values (?)",mid);
        jdbc.update("insert into recovery_test.merchant_memberships(user_id,merchant_id) values (?,?)",u.getUserId(),mid);
        jdbc.update("insert into recovery_test.merchant_registrations(user_id,merchant_id,first_name,last_name,business_name,email,mobile,business_type,country,terms_version) values (?,?,'Synthetic','Merchant','Test',?,'1234567890','COMPANY','IN','test')",u.getUserId(),mid,login);
        var before=new HashMap<String,List<Map<String,Object>>>();
        for(String table:List.of("merchants","merchant_memberships","merchant_registrations","merchant_administration","payments","refunds","payment_gateway_transactions","idempotency_keys","simulated_gateway_outcomes","webhook_events","reconciliation_jobs","reconciliation_attempts","user_roles","demo_recovery_eligibility"))before.put(table,snapshot(table));
        assertThrows(AccountOperationException.class,()->merchantRecovery.reset("other@example.test",next.toCharArray(),next.toCharArray()));
        assertThrows(IllegalArgumentException.class,()->merchantRecovery.reset(login,"short".toCharArray(),"short".toCharArray()));
        assertThrows(IllegalArgumentException.class,()->merchantRecovery.reset(login,next.toCharArray(),"mismatch".toCharArray()));
        for(String status:List.of("ACTIVE","REJECTED","SUSPENDED")) {
            jdbc.update("update recovery_test.app_users set account_status=? where user_id=?",status,u.getUserId());
            assertThrows(AccountOperationException.class,()->merchantRecovery.reset(login,next.toCharArray(),next.toCharArray()));
        }
        jdbc.update("update recovery_test.app_users set account_status='PENDING_APPROVAL',enabled=false where user_id=?",u.getUserId());
        assertThrows(AccountOperationException.class,()->merchantRecovery.reset(login,next.toCharArray(),next.toCharArray()));
        jdbc.update("update recovery_test.app_users set enabled=true where user_id=?",u.getUserId());
        roles.saveAndFlush(new UserRole(u.getUserId(),AccountRole.ADMIN,null));
        assertThrows(AccountOperationException.class,()->merchantRecovery.reset(login,next.toCharArray(),next.toCharArray()));
        roles.deleteById(new UserRole.Id(u.getUserId(),"ADMIN"));
        UUID sid=UUID.randomUUID(),cid=UUID.randomUUID();
        jdbc.update("insert into recovery_test.auth_sessions(session_id,user_id,authorization_version,account_status,roles_snapshot,remember_me,created_at,absolute_expires_at,idle_expires_at) values (?,?,0,'PENDING_APPROVAL','MERCHANT',false,now(),now()+interval '8 hours',now()+interval '1 hour')",sid,u.getUserId());
        jdbc.update("insert into recovery_test.password_recovery_challenges(challenge_id,user_id,portal,purpose,otp_digest,authorization_version,created_at,expires_at) values (?,?,'MERCHANT','LOCAL_DEMO_PASSWORD_RESET',?,0,now(),now()+interval '5 minutes')",cid,u.getUserId(),"a".repeat(64));
        jdbc.update("insert into recovery_test.password_reset_authorizations(authorization_id,challenge_id,token_digest,expires_at) values (?,?,?,now()+interval '5 minutes')",UUID.randomUUID(),cid,"b".repeat(64));
        doThrow(new IllegalStateException("private-test-failure")).when(events).saveAndFlush(argThat(e->e!=null&&"DISPOSABLE_MERCHANT_PASSWORD_RECOVERED".equals(e.getEventType())));
        try {assertThrows(RuntimeException.class,()->merchantRecovery.reset(login,next.toCharArray(),next.toCharArray()));
            assertEquals(u.passwordHash(),users.findById(u.getUserId()).orElseThrow().passwordHash());
            assertEquals(0,jdbc.queryForObject("select count(*) from recovery_test.auth_sessions where session_id=? and revoked_at is not null",Integer.class,sid));
            assertEquals(0,jdbc.queryForObject("select count(*) from recovery_test.password_reset_authorizations where challenge_id=? and consumed_at is not null",Integer.class,cid));
        }finally{reset(events);}
        assertEquals(u.getUserId(),merchantRecovery.reset(login,next.toCharArray(),next.toCharArray()));
        var changed=users.findById(u.getUserId()).orElseThrow();assertTrue(passwords.matches(next.toCharArray(),changed.passwordHash()));assertFalse(passwords.matches("old-test-passphrase".toCharArray(),changed.passwordHash()));
        assertEquals(u.getAuthorizationVersion()+1,changed.getAuthorizationVersion());assertEquals("PENDING_APPROVAL",changed.getAccountStatus());assertTrue(changed.isEnabled());
        assertEquals(1,jdbc.queryForObject("select count(*) from recovery_test.auth_sessions where session_id=? and revoked_at is not null",Integer.class,sid));
        assertEquals(1,jdbc.queryForObject("select count(*) from recovery_test.password_reset_authorizations where challenge_id=? and consumed_at is not null",Integer.class,cid));
        var event=events.findByEventTypeAndResourceId("DISPOSABLE_MERCHANT_PASSWORD_RECOVERED",u.getUserId().toString());assertEquals(1,event.size());assertNull(event.getFirst().getActorUserId());
        for(var e:before.entrySet())assertEquals(e.getValue(),snapshot(e.getKey()),e.getKey());
        assertFalse(output.getAll().contains(next));assertFalse(output.getAll().contains(changed.passwordHash()));
    }

}
