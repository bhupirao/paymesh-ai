package com.paymesh.backend.security.accounts;

import java.util.*;
import java.time.*;
import java.nio.file.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import javax.sql.DataSource;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.*;
import org.springframework.test.context.*;
import org.springframework.test.context.bean.override.mockito.*;
import org.springframework.test.web.servlet.*;
import org.springframework.jdbc.core.JdbcTemplate;
import com.fasterxml.jackson.databind.*;
import jakarta.servlet.http.Cookie;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

@SpringBootTest(properties={"spring.flyway.default-schema=phase673_test","spring.flyway.schemas=phase673_test","spring.jpa.properties.hibernate.default_schema=phase673_test","paymesh.sessions.origin=https://paymesh.test","paymesh.auth.login.max-attempts=100"})
@AutoConfigureMockMvc(print=MockMvcPrint.NONE)
class SessionRecoveryIntegrationTest {
 static final Path KEYS;
 static {try{KEYS=Files.createTempDirectory("paymesh-673-keys-");var g=java.security.KeyPairGenerator.getInstance("RSA");g.initialize(2048);var pair=g.generateKeyPair();
  Files.writeString(KEYS.resolve("private.pem"),"-----BEGIN PRIVATE KEY-----\n"+Base64.getMimeEncoder(64,new byte[]{10}).encodeToString(pair.getPrivate().getEncoded())+"\n-----END PRIVATE KEY-----\n");
  Files.setPosixFilePermissions(KEYS.resolve("private.pem"),java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
  Files.writeString(KEYS.resolve("public.pem"),"-----BEGIN PUBLIC KEY-----\n"+Base64.getMimeEncoder(64,new byte[]{10}).encodeToString(pair.getPublic().getEncoded())+"\n-----END PUBLIC KEY-----\n");
 }catch(Exception ex){throw new ExceptionInInitializerError(ex);}}
 @DynamicPropertySource static void keys(DynamicPropertyRegistry r){r.add("paymesh.jwt.private-key-file",()->KEYS.resolve("private.pem").toString());r.add("paymesh.jwt.public-key-file",()->KEYS.resolve("public.pem").toString());r.add("paymesh.jwt.issuer",()->"https://paymesh.test");r.add("paymesh.jwt.audience",()->"paymesh-api");}
 @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired JdbcTemplate jdbc;@Autowired AppUserRepository users;@Autowired UserRoleRepository roles;@Autowired AccountPasswords passwords;
 @Autowired AccountCredentials credentials;@Autowired PersistentSessions sessions;@Autowired LocalPasswordRecovery recovery;
 @MockitoBean LocalDemoRecoveryGate gate;@MockitoSpyBean AuthenticationClock clock;@MockitoSpyBean SecurityAuditEventRepository auditEvents;
 final AtomicReference<Instant> now=new AtomicReference<>();
 @BeforeEach void setup(){now.set(Instant.now());doAnswer(i->now.get()).when(clock).now();when(gate.enabled()).thenReturn(true);when(gate.key()).thenReturn("test-only-random-key-"+"x".repeat(64));}
 AppUser account(String role,boolean pending){var u=new AppUser("test673."+UUID.randomUUID(),passwords.hash("test-only-old-passphrase".toCharArray()));if(pending)u.pendingApproval();users.saveAndFlush(u);roles.saveAndFlush(new UserRole(u.getUserId(),AccountRole.valueOf(role),null));return u;}
 void designate(AppUser u,String portal){jdbc.update("INSERT INTO phase673_test.demo_recovery_eligibility(user_id,portal,enabled,designated_by,review_reference) VALUES (?,?,true,?,'isolated-test')",u.getUserId(),portal,u.getUserId());}
 PersistentSessions.Grant session(AppUser u,boolean remember){return sessions.create(credentials.authenticate(u.getLoginNormalized(),"test-only-old-passphrase".toCharArray()),remember);}
 MvcResult postJson(String path,Object body,Cookie cookie)throws Exception {var request=post("/api/v1/auth"+path).header("Origin","https://paymesh.test").header("X-PayMesh-CSRF","1").with(r->{r.setRemoteAddr("127.0.0.1");r.setLocalAddr("127.0.0.1");r.setLocalPort(18080);return r;});if(body!=null)request.contentType("application/json").content(json.writeValueAsBytes(body));if(cookie!=null)request.cookie(cookie);return mvc.perform(request).andReturn();}
 Cookie cookie(String raw){return new Cookie("pm_refresh",raw);}
 @Test void legacyLoginAndRememberCookieContracts()throws Exception {
  var u=account("ADMIN",false);var input=Map.of("login",u.getLoginNormalized(),"password","test-only-old-passphrase");
  var legacy=mvc.perform(post("/api/v1/auth/login").contentType("application/json").content(json.writeValueAsBytes(input))).andReturn().getResponse();assertEquals(200,legacy.getStatus());assertNull(legacy.getHeader("Set-Cookie"));
  for(boolean remember:List.of(false,true)){var body=new HashMap<String,Object>(input);body.put("rememberMe",remember);var response=postJson("/login",body,null).getResponse();assertEquals(200,response.getStatus());String c=response.getHeader("Set-Cookie");assertNotNull(c);assertTrue(c.contains("HttpOnly"));assertTrue(c.contains("Secure"));assertTrue(c.contains("SameSite=Strict"));assertTrue(c.contains("Path=/api/v1/auth"));assertEquals(remember,c.contains("Max-Age="));assertEquals(900,json.readTree(response.getContentAsString()).get("expiresIn").asInt());}
 }
 @Test void refreshRotationReplayRevokesFamilyAndAccessJwt()throws Exception {
  var u=account("ADMIN",false);var response=postJson("/login",Map.of("login",u.getLoginNormalized(),"password","test-only-old-passphrase"),null).getResponse();
  String raw=response.getHeader("Set-Cookie").split(";",2)[0].split("=",2)[1];String access=json.readTree(response.getContentAsString()).get("accessToken").asText();
  var rotated=postJson("/refresh",null,cookie(raw)).getResponse();assertEquals(200,rotated.getStatus());assertNotEquals(raw,rotated.getHeader("Set-Cookie").split(";",2)[0].split("=",2)[1]);
  assertEquals(401,postJson("/refresh",null,cookie(raw)).getResponse().getStatus());assertEquals(401,mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+access)).andReturn().getResponse().getStatus());
 }
 @Test void concurrentRefreshIsSerializedAndReplayFailsClosed()throws Exception {
  var u=account("MERCHANT",false);var g=session(u,true);var pool=Executors.newFixedThreadPool(2);try{var start=new CountDownLatch(1);Callable<PersistentSessions.Grant> task=()->{start.await();return sessions.refresh(g.refreshToken());};var a=pool.submit(task);var b=pool.submit(task);start.countDown();var results=Arrays.asList(a.get(20,TimeUnit.SECONDS),b.get(20,TimeUnit.SECONDS));assertEquals(1,results.stream().filter(Objects::nonNull).count());var winner=results.stream().filter(Objects::nonNull).findFirst().orElseThrow();assertNull(sessions.refresh(winner.refreshToken()));}finally{pool.shutdownNow();}
 }
 @Test void idleAndAbsoluteExpiryAndDigestOnlyStorage(){
  var u=account("ADMIN",false);var g=session(u,false);assertEquals(now.get().plusSeconds(28800),g.expiresAt());assertNull(sessions.refresh("not-a-token"));
  String digest=jdbc.queryForObject("SELECT token_digest FROM phase673_test.auth_refresh_tokens WHERE session_id=?",String.class,g.sessionId());assertEquals(AuthStore.digest(g.refreshToken()),digest);assertNotEquals(g.refreshToken(),digest);
  now.set(now.get().plusSeconds(28801));assertNull(sessions.refresh(g.refreshToken()));var longer=session(u,true);assertEquals(now.get().plusSeconds(2592000),longer.expiresAt());
  jdbc.update("UPDATE phase673_test.auth_sessions SET idle_expires_at=absolute_expires_at WHERE session_id=?",longer.sessionId());now.set(longer.expiresAt().plusSeconds(1));assertNull(sessions.refresh(longer.refreshToken()));
 }
 @Test void logoutCurrentAndAllDevicesInvalidateServerState()throws Exception {
  var u=account("ADMIN",false);var a=session(u,false);var b=session(u,true);sessions.logout(a.refreshToken());assertNull(sessions.refresh(a.refreshToken()));assertTrue(sessions.logoutAll(b.refreshToken()));assertNull(sessions.refresh(b.refreshToken()));assertTrue(users.findById(u.getUserId()).orElseThrow().getAuthorizationVersion()>u.getAuthorizationVersion());
 }
 @Test void logoutEndpointRejectsMissingOriginAndCsrf()throws Exception {
  assertEquals(403,mvc.perform(post("/api/v1/auth/refresh")).andReturn().getResponse().getStatus());assertEquals(403,mvc.perform(post("/api/v1/auth/logout").header("Origin","https://evil.test").header("X-PayMesh-CSRF","1")).andReturn().getResponse().getStatus());
  assertEquals(200,postJson("/logout",null,null).getResponse().getStatus());
 }
 @Test void disabledVersionRolesAndStatusChangesRejectRefresh(){
  for(String change:List.of("disabled","version","status","role")){var u=account("MERCHANT",false);var g=session(u,false);switch(change){case "disabled"->u.setEnabled(false);case "version"->u.invalidateAuthorization();case "status"->u.pendingApproval();case "role"->roles.saveAndFlush(new UserRole(u.getUserId(),AccountRole.ADMIN,null));}users.saveAndFlush(u);assertNull(sessions.refresh(g.refreshToken()));}
 }
 @Test void pendingSessionRestoresButFinancialApisRemainDenied()throws Exception {
  var u=account("MERCHANT",true);var result=postJson("/login",Map.of("login",u.getLoginNormalized(),"password","test-only-old-passphrase","rememberMe",true),null).getResponse();String access=json.readTree(result.getContentAsString()).get("accessToken").asText();
  assertEquals(403,mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+access)).andReturn().getResponse().getStatus());
  String raw=result.getHeader("Set-Cookie").split(";",2)[0].split("=",2)[1];assertEquals(200,postJson("/refresh",null,cookie(raw)).getResponse().getStatus());
 }
 @Test void featureDisabledDoesNotRevealOtpOrAccount()throws Exception {when(gate.enabled()).thenReturn(false);assertEquals(404,postJson("/password/forgot",Map.of("identity","anything","portal","ADMIN"),null).getResponse().getStatus());assertFalse(json.readTree(mvc.perform(get("/api/v1/auth/password/capabilities")).andReturn().getResponse().getContentAsString()).get("localDemoEnabled").asBoolean());}
 @Test void onlyDesignatedExactPortalAndSingleRoleAccountsReceiveCodes(){
  var u=account("MERCHANT",false);assertNull(recovery.forgot(u.getLoginNormalized(),"MERCHANT","r1").otp());designate(u,"MERCHANT");assertNull(recovery.forgot(u.getLoginNormalized(),"ADMIN","r2").otp());
  roles.saveAndFlush(new UserRole(u.getUserId(),AccountRole.ADMIN,null));assertNull(recovery.forgot(u.getLoginNormalized(),"MERCHANT","r3").otp());assertNull(recovery.forgot("missing@example.test","MERCHANT","r4").otp());
 }
 @Test void validMerchantAdminAndPendingResetPreservesOwnershipAndRevokesSessions(){
  for(String kind:List.of("ADMIN","MERCHANT","PENDING")){
   var u=account(kind.equals("ADMIN")?"ADMIN":"MERCHANT",kind.equals("PENDING"));String portal=kind.equals("ADMIN")?"ADMIN":"MERCHANT";designate(u,portal);var g=session(u,true);
   var c=recovery.forgot(u.getLoginNormalized(),portal,"flow-"+kind);assertTrue(c.otp().matches("[0-9]{6}"));
   String stored=jdbc.queryForObject("SELECT otp_digest FROM phase673_test.password_recovery_challenges WHERE challenge_id=?",String.class,UUID.fromString(c.challengeId()));assertNotEquals(c.otp(),stored);
   String authorization=recovery.verify(UUID.fromString(c.challengeId()),portal,c.otp(),"verify-"+kind);assertNotNull(authorization);
   assertNull(recovery.verify(UUID.fromString(c.challengeId()),portal,c.otp(),"replay-"+kind));
   recovery.reset(UUID.fromString(c.challengeId()),portal,authorization,"test-only-new-passphrase".toCharArray(),"test-only-new-passphrase".toCharArray(),"reset-"+kind);
   assertNull(sessions.refresh(g.refreshToken()));assertThrows(AccountAccessDeniedException.class,()->credentials.authenticate(u.getLoginNormalized(),"test-only-old-passphrase".toCharArray()));assertNotNull(credentials.authenticate(u.getLoginNormalized(),"test-only-new-passphrase".toCharArray()));
   var after=users.findById(u.getUserId()).orElseThrow();assertEquals(u.getAccountStatus(),after.getAccountStatus());assertTrue(after.isEnabled());assertEquals(List.of(portal),roles.roles(u.getUserId()));assertEquals(u.getUserId(),after.getUserId());
   var events=auditEvents.findByEventTypeAndResourceId("LOCAL_DEMO_PASSWORD_RESET",u.getUserId().toString());assertEquals(1,events.size());assertNull(events.getFirst().getActorUserId());assertNull(events.getFirst().getActorIdentifier());
   assertThrows(LocalPasswordRecovery.Invalid.class,()->recovery.reset(UUID.fromString(c.challengeId()),portal,authorization,"test-only-new-passphrase".toCharArray(),"test-only-new-passphrase".toCharArray(),"reuse-"+kind));
  }
 }
 @Test void wrongOtpExpiryAndAttemptExhaustion(){
  var u=account("MERCHANT",false);designate(u,"MERCHANT");var c=recovery.forgot(u.getLoginNormalized(),"MERCHANT","attempts");String wrong=c.otp().equals("000000")?"111111":"000000";
  for(int i=0;i<5;i++)assertNull(recovery.verify(UUID.fromString(c.challengeId()),"MERCHANT",wrong,"guess-"+i));assertNull(recovery.verify(UUID.fromString(c.challengeId()),"MERCHANT",c.otp(),"exhausted"));
  now.set(now.get().plusSeconds(61));var next=recovery.forgot(u.getLoginNormalized(),"MERCHANT","expiry");now.set(now.get().plusSeconds(301));assertNull(recovery.verify(UUID.fromString(next.challengeId()),"MERCHANT",next.otp(),"expired"));
 }
 @Test void cooldownResendInvalidatesPreviousAndAccountBounded(){
  var u=account("ADMIN",false);designate(u,"ADMIN");var first=recovery.forgot(u.getLoginNormalized(),"ADMIN","cool1");assertThrows(LocalPasswordRecovery.Limited.class,()->recovery.forgot(u.getLoginNormalized(),"ADMIN","cool2"));
  now.set(now.get().plusSeconds(61));var next=recovery.forgot(u.getLoginNormalized(),"ADMIN","cool3");assertNull(recovery.verify(UUID.fromString(first.challengeId()),"ADMIN",first.otp(),"old"));assertNotNull(recovery.verify(UUID.fromString(next.challengeId()),"ADMIN",next.otp(),"new"));
  for(int i=0;i<3;i++){now.set(now.get().plusSeconds(61));recovery.forgot(u.getLoginNormalized(),"ADMIN","more"+i);}now.set(now.get().plusSeconds(61));assertThrows(LocalPasswordRecovery.Limited.class,()->recovery.forgot(u.getLoginNormalized(),"ADMIN","account-limit"));
 }
 @Test void requesterBudgetAndResetAuthorizationExpiryAndCrossPortal(){
  for(int i=0;i<20;i++)recovery.forgot("missing","ADMIN","same-requester");assertThrows(LocalPasswordRecovery.Limited.class,()->recovery.forgot("missing","ADMIN","same-requester"));
  var u=account("ADMIN",false);designate(u,"ADMIN");var c=recovery.forgot(u.getLoginNormalized(),"ADMIN","auth-exp");assertNull(recovery.verify(UUID.fromString(c.challengeId()),"MERCHANT",c.otp(),"wrong-portal"));String token=recovery.verify(UUID.fromString(c.challengeId()),"ADMIN",c.otp(),"correct");
  assertThrows(LocalPasswordRecovery.Invalid.class,()->recovery.reset(UUID.randomUUID(),"ADMIN",token,"valid-test-passphrase".toCharArray(),"valid-test-passphrase".toCharArray(),"wrong-account"));now.set(now.get().plusSeconds(301));assertThrows(LocalPasswordRecovery.Invalid.class,()->recovery.reset(UUID.fromString(c.challengeId()),"ADMIN",token,"valid-test-passphrase".toCharArray(),"valid-test-passphrase".toCharArray(),"expired-auth"));
 }
 @Test void concurrentResetHasOneWinner()throws Exception {
  var u=account("ADMIN",false);designate(u,"ADMIN");var c=recovery.forgot(u.getLoginNormalized(),"ADMIN","concurrent");String token=recovery.verify(UUID.fromString(c.challengeId()),"ADMIN",c.otp(),"concurrent-verify");var pool=Executors.newFixedThreadPool(2);try{var start=new CountDownLatch(1);Callable<Boolean> job=()->{start.await();try{recovery.reset(UUID.fromString(c.challengeId()),"ADMIN",token,"valid-new-test-password".toCharArray(),"valid-new-test-password".toCharArray(),UUID.randomUUID().toString());return true;}catch(LocalPasswordRecovery.Invalid ex){return false;}};var a=pool.submit(job);var b=pool.submit(job);start.countDown();assertNotEquals(a.get(30,TimeUnit.SECONDS),b.get(30,TimeUnit.SECONDS));}finally{pool.shutdownNow();}
 }
 @Test void passwordPolicyAndAuditFailureRollBackAllSecurityState(){
  var u=account("MERCHANT",false);designate(u,"MERCHANT");var family=session(u,false);var c=recovery.forgot(u.getLoginNormalized(),"MERCHANT","rollback");String token=recovery.verify(UUID.fromString(c.challengeId()),"MERCHANT",c.otp(),"rollback-verify");
  for(String pw:List.of("short","x".repeat(73),"nul\0password-password"))assertThrows(IllegalArgumentException.class,()->recovery.reset(UUID.fromString(c.challengeId()),"MERCHANT",token,pw.toCharArray(),pw.toCharArray(),"invalid"));
  assertThrows(IllegalArgumentException.class,()->recovery.reset(UUID.fromString(c.challengeId()),"MERCHANT",token,"different-password".toCharArray(),"not-the-same-password".toCharArray(),"mismatch"));
  doThrow(new IllegalStateException("synthetic audit failure")).when(auditEvents).saveAndFlush(argThat(e->e!=null&&e.getEventType().equals("LOCAL_DEMO_PASSWORD_RESET")));
  try{assertThrows(RuntimeException.class,()->recovery.reset(UUID.fromString(c.challengeId()),"MERCHANT",token,"valid-new-password".toCharArray(),"valid-new-password".toCharArray(),"audit-failure"));assertNotNull(credentials.authenticate(u.getLoginNormalized(),"test-only-old-passphrase".toCharArray()));assertNotNull(sessions.refresh(family.refreshToken()));assertEquals(u.getAuthorizationVersion(),users.findById(u.getUserId()).orElseThrow().getAuthorizationVersion());}finally{reset(auditEvents);}
 }
 @Test void currentAndAllLogoutRejectAssociatedSignedAccessTokens()throws Exception {
  var u=account("ADMIN",false);
  for(String endpoint:List.of("/logout","/logout-all")){
   var login=postJson("/login",Map.of("login",u.getLoginNormalized(),"password","test-only-old-passphrase"),null).getResponse();String access=json.readTree(login.getContentAsString()).get("accessToken").asText();String refresh=login.getHeader("Set-Cookie").split(";",2)[0].split("=",2)[1];
   assertEquals(200,postJson(endpoint,null,cookie(refresh)).getResponse().getStatus());
   assertEquals(401,mvc.perform(get("/api/v1/payments/"+UUID.randomUUID()).header("Authorization","Bearer "+access)).andReturn().getResponse().getStatus());
  }
 }
 @Test void enablingHttpControllerDoesNotTrustForwardedOrNonLoopbackRequests()throws Exception {
  var u=account("ADMIN",false);designate(u,"ADMIN");var body=json.writeValueAsBytes(Map.of("identity",u.getLoginNormalized(),"portal","ADMIN"));
  assertEquals(403,mvc.perform(post("/api/v1/auth/password/forgot").header("Origin","https://paymesh.test").header("X-PayMesh-CSRF","1").header("X-Forwarded-For","127.0.0.1").contentType("application/json").content(body)).andReturn().getResponse().getStatus());
 }

 @Test void resetPreservesSeededFinancialOwnershipAndRegistrationRecords(){
  var u=account("MERCHANT",true);designate(u,"MERCHANT");String merchant="phase673-"+UUID.randomUUID();UUID payment=UUID.randomUUID();
  jdbc.update("INSERT INTO phase673_test.merchants(merchant_id) VALUES (?)",merchant);
  jdbc.update("INSERT INTO phase673_test.merchant_memberships(user_id,merchant_id) VALUES (?,?)",u.getUserId(),merchant);
  jdbc.update("INSERT INTO phase673_test.merchant_registrations(user_id,merchant_id,first_name,last_name,business_name,email,mobile,business_type,country,terms_version) VALUES (?,?,'Synthetic','Test','Test Business',?,'1234567890','COMPANY','IN','test')",u.getUserId(),merchant,u.getLoginNormalized()+"@example.test");
  jdbc.update("INSERT INTO phase673_test.payments(payment_id,merchant_id,customer_id,amount,currency,payment_method,status) VALUES (?,?,'synthetic',100,'INR','UPI','SUCCESS')",payment,merchant);
  jdbc.update("INSERT INTO phase673_test.refunds(refund_id,payment_id,amount,status) VALUES (?,?,20,'SUCCESS')",UUID.randomUUID(),payment);
  jdbc.update("INSERT INTO phase673_test.payment_gateway_transactions(id,payment_id,gateway_name,status) VALUES (?,?,'MOCK_RAZORPAY','SUCCESS')",UUID.randomUUID(),payment);
  var before=new HashMap<String,List<Map<String,Object>>>();for(String table:List.of("merchants","merchant_memberships","merchant_registrations","payments","refunds","payment_gateway_transactions","idempotency_keys","webhook_events","reconciliation_jobs","reconciliation_attempts"))before.put(table,jdbc.queryForList("SELECT row_to_json(t)::text AS record FROM phase673_test."+table+" t ORDER BY row_to_json(t)::text"));
  var c=recovery.forgot(u.getLoginNormalized(),"MERCHANT","financial-preservation");String grant=recovery.verify(UUID.fromString(c.challengeId()),"MERCHANT",c.otp(),"financial-verify");recovery.reset(UUID.fromString(c.challengeId()),"MERCHANT",grant,"new-synthetic-password".toCharArray(),"new-synthetic-password".toCharArray(),"financial-reset");
  for(var entry:before.entrySet())assertEquals(entry.getValue(),jdbc.queryForList("SELECT row_to_json(t)::text AS record FROM phase673_test."+entry.getKey()+" t ORDER BY row_to_json(t)::text"),entry.getKey());assertEquals("PENDING_APPROVAL",users.findById(u.getUserId()).orElseThrow().getAccountStatus());
 }
 @Test void resendRevokesVerifiedAuthorizationAndEligibilityRevocationIsImmediate(){
  var u=account("ADMIN",false);designate(u,"ADMIN");var first=recovery.forgot(u.getLoginNormalized(),"ADMIN","resend-grant");String old=recovery.verify(UUID.fromString(first.challengeId()),"ADMIN",first.otp(),"first-grant");now.set(now.get().plusSeconds(61));var next=recovery.forgot(u.getLoginNormalized(),"ADMIN","next-grant");
  assertThrows(LocalPasswordRecovery.Invalid.class,()->recovery.reset(UUID.fromString(first.challengeId()),"ADMIN",old,"new-valid-passphrase".toCharArray(),"new-valid-passphrase".toCharArray(),"old-auth"));String current=recovery.verify(UUID.fromString(next.challengeId()),"ADMIN",next.otp(),"current-auth");jdbc.update("UPDATE phase673_test.demo_recovery_eligibility SET enabled=false WHERE user_id=?",u.getUserId());
  assertThrows(LocalPasswordRecovery.Invalid.class,()->recovery.reset(UUID.fromString(next.challengeId()),"ADMIN",current,"new-valid-passphrase".toCharArray(),"new-valid-passphrase".toCharArray(),"revoked-eligibility"));
 }

}
