package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jwt.*;
import com.paymesh.backend.security.accounts.*;
import java.nio.file.*;
import java.security.KeyPair;
import java.security.interfaces.RSAPrivateKey;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.*;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

@SpringBootTest(properties = {
    "spring.flyway.default-schema=admin_api_test", "spring.flyway.schemas=admin_api_test",
    "spring.jpa.properties.hibernate.default_schema=admin_api_test",
    "paymesh.jwt.issuer=https://admin-api.test", "paymesh.jwt.audience=admin-api",
    "paymesh.auth.login.max-attempts=100", "paymesh.sessions.origin=https://paymesh.invalid"})
@AutoConfigureMockMvc(print = MockMvcPrint.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class AdminAccountApiIntegrationTest {
    static final KeyPair KEYS;
    static final Path DIRECTORY;
    static {
        try {
            KEYS = JwtKeyMaterialTest.pair(2048);
            DIRECTORY = Files.createTempDirectory("paymesh-admin-api-");
            JwtKeyMaterialTest.pem(DIRECTORY.resolve("private.pem"), "PRIVATE KEY", KEYS.getPrivate().getEncoded());
            JwtKeyMaterialTest.pem(DIRECTORY.resolve("public.pem"), "PUBLIC KEY", KEYS.getPublic().getEncoded());
            Files.setPosixFilePermissions(DIRECTORY.resolve("private.pem"), java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
            DIRECTORY.resolve("private.pem").toFile().deleteOnExit(); DIRECTORY.resolve("public.pem").toFile().deleteOnExit(); DIRECTORY.toFile().deleteOnExit();
        } catch (Exception ex) { throw new ExceptionInInitializerError(ex); }
    }
    @DynamicPropertySource static void keys(DynamicPropertyRegistry r) {
        r.add("paymesh.jwt.private-key-file", () -> DIRECTORY.resolve("private.pem").toString());
        r.add("paymesh.jwt.public-key-file", () -> DIRECTORY.resolve("public.pem").toString());
    }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired org.springframework.security.crypto.password.PasswordEncoder passwordEncoder;
    @Autowired AccountCredentials credentials;
    @Autowired AccountAdministration administration;
    @MockitoSpyBean SecurityAuditEventRepository events;
    AccountCredentials.AuthenticatedAccount principal;
    AccountView root;
    String rootPassword;
    String token;
    static final String SCHEMA = "admin_api_test.";

    @BeforeAll void setup() {
        rootPassword = UUID.randomUUID().toString();
        // Isolated test fixture only; all endpoint actors authenticate through the real login API.
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO " + SCHEMA + "app_users(user_id,login_normalized,password_hash,enabled) VALUES (?, ?, ?, TRUE)", id, "api.admin", passwordEncoder.encode(rootPassword));
        jdbc.update("INSERT INTO " + SCHEMA + "user_roles(user_id,role_name) VALUES (?, 'ADMIN')", id);
        root = new AccountView(id, "api.admin", true, 0, Set.of(AccountRole.ADMIN));
        principal = credentials.authenticate(root.login(), rootPassword.toCharArray());
    }
    @BeforeEach void authenticate() throws Exception { token = login(root.login(), rootPassword); }
    String login(String name, String password) throws Exception {
        var response = mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
            .content(json.writeValueAsBytes(Map.of("login", name, "password", password)))).andReturn().getResponse();
        assertEquals(200, response.getStatus());
        return json.readTree(response.getContentAsByteArray()).get("accessToken").asText();
    }
    String name() { return "admin." + UUID.randomUUID(); }
    Map<String,Object> request(String name, String password) { return Map.of("login", name, "password", password, "confirmPassword", password); }
    MvcResult create(String bearer, Object request) throws Exception {
        var builder = post("/api/v1/admin/accounts").contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(request));
        if (bearer != null) builder.header("Authorization", "Bearer " + bearer);
        return mvc.perform(builder).andReturn();
    }
    int code(MvcResult result) { return result.getResponse().getStatus(); }
    long count(String table) { return jdbc.queryForObject("SELECT count(*) FROM " + SCHEMA + table, Long.class); }

    @Test void authenticatedAdminCreatesActiveSingleRoleHashedAccountAndNewLogin() throws Exception {
        String name = name(), password = UUID.randomUUID().toString();
        var response = create(token, request(" " + name.toUpperCase(Locale.ROOT) + " ", password));
        assertEquals(201, code(response));
        var body = json.readTree(response.getResponse().getContentAsByteArray());
        assertEquals(name, body.get("login").asText()); assertTrue(body.get("enabled").asBoolean());
        assertEquals("ACTIVE", body.get("accountStatus").asText());
        assertEquals(List.of("ADMIN"), json.convertValue(body.get("roles"), List.class));
        String hash = jdbc.queryForObject("SELECT password_hash FROM " + SCHEMA + "app_users WHERE login_normalized=?", String.class, name);
        assertNotEquals(password, hash); assertTrue(hash.startsWith("$2"));
        assertNotNull(credentials.authenticate(name, password.toCharArray())); assertNotNull(login(name, password));
        assertFalse(response.getResponse().getContentAsString().contains(password));
        assertFalse(response.getResponse().getContentAsString().contains(hash));
        assertEquals("no-store", response.getResponse().getHeader("Cache-Control"));
    }
    @Test void auditUsesActualAuthenticatedAdministratorAndNoAutomaticEligibility() throws Exception {
        var result = create(token, request(name(), UUID.randomUUID().toString())); assertEquals(201, code(result));
        String id = json.readTree(result.getResponse().getContentAsByteArray()).get("userId").asText();
        var audit = events.findByEventTypeAndResourceId("ACCOUNT_CREATED", id);
        assertEquals(1, audit.size()); assertEquals(root.userId(), audit.getFirst().getActorUserId());
        assertEquals(root.login(), audit.getFirst().getActorIdentifier()); assertEquals("SUCCESS", audit.getFirst().getOutcome());
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM " + SCHEMA + "demo_recovery_eligibility WHERE user_id=?", Integer.class, UUID.fromString(id)));
    }
    @Test void duplicateNormalizedLoginNeverOverwritesAccount() throws Exception {
        String name = name(); var body = request(name, UUID.randomUUID().toString()); assertEquals(201, code(create(token, body)));
        var before = jdbc.queryForMap("SELECT * FROM " + SCHEMA + "app_users WHERE login_normalized=?", name);
        assertEquals(409, code(create(token, request(name.toUpperCase(Locale.ROOT), UUID.randomUUID().toString()))));
        assertEquals(before, jdbc.queryForMap("SELECT * FROM " + SCHEMA + "app_users WHERE login_normalized=?", name));
    }
    @Test void mismatchAndInvalidPasswordsAndLoginRejectedWithoutWrites() throws Exception {
        long before = count("app_users");
        assertEquals(400, code(create(token, Map.of("login", name(), "password", "long-enough-test-password", "confirmPassword", "different-test-password"))));
        for (String password : List.of("short", "😀".repeat(20), "valid-password-with\0nul", "invalid-\uD800-password"))
            assertEquals(400, code(create(token, request(name(), password))));
        assertEquals(409, code(create(token, request("bad login", UUID.randomUUID().toString()))));
        assertEquals(before, count("app_users"));
    }
    @Test void clientSuppliedRolesAndUnknownFieldsAreRejected() throws Exception {
        var body = new HashMap<String,Object>(request(name(), UUID.randomUUID().toString()));
        for (String field : List.of("roles", "enabled", "userId", "accountStatus", "authority")) {
            body.put(field, "ADMIN"); assertEquals(400, code(create(token, body))); body.remove(field);
        }
    }
    @Test void missingAndInvalidBearerAndCookieOnlyAreRejected() throws Exception {
        var body = request(name(), UUID.randomUUID().toString());
        assertEquals(401, code(create(null, body))); assertEquals(401, code(create("invalid", body)));
        assertEquals(401, code(mvc.perform(post("/api/v1/admin/accounts").header("Cookie", "pm_refresh=ignored")
            .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(body))).andReturn()));
    }
    @Test void activeMerchantCannotCreateAdministrator() throws Exception {
        String password = UUID.randomUUID().toString(); var merchant = administration.createMerchantAccount(principal, name(), password.toCharArray());
        assertEquals(403, code(create(login(merchant.login(), password), request(name(), password))));
    }
    @Test void pendingMerchantCannotCreateAdministrator() throws Exception {
        String password = UUID.randomUUID().toString(); var merchant = administration.createMerchantAccount(principal, name(), password.toCharArray());
        jdbc.update("UPDATE " + SCHEMA + "app_users SET account_status='PENDING_APPROVAL' WHERE user_id=?", merchant.userId());
        assertEquals(403, code(create(login(merchant.login(), password), request(name(), password))));
    }
    @Test void disabledAdministratorAndRevokedVersionAreRejected() throws Exception {
        String password = UUID.randomUUID().toString(); var admin = administration.createAdminAccount(principal, name(), password.toCharArray());
        String old = login(admin.login(), password);
        administration.setAccountEnabled(principal, admin.userId(), false);
        assertEquals(401, code(create(old, request(name(), password))));
        administration.setAccountEnabled(principal, admin.userId(), true);
        assertEquals(401, code(create(old, request(name(), password))));
    }
    @Test void expiredSignedJwtIsRejected() throws Exception {
        SignedJWT parsed = SignedJWT.parse(token);
        var claims = new JWTClaimsSet.Builder(parsed.getJWTClaimsSet()).issueTime(Date.from(Instant.now().minusSeconds(1800)))
            .notBeforeTime(Date.from(Instant.now().minusSeconds(1800))).expirationTime(Date.from(Instant.now().minusSeconds(901)));
        var expired = new SignedJWT(parsed.getHeader(), claims.build()); expired.sign(new RSASSASigner((RSAPrivateKey)KEYS.getPrivate()));
        assertEquals(401, code(create(expired.serialize(), request(name(), UUID.randomUUID().toString()))));
    }
    @Test void revokedBrowserSessionAccessIsRejected() throws Exception {
        var result = mvc.perform(post("/api/v1/auth/login").header("Origin", "https://paymesh.invalid").header("X-PayMesh-CSRF", "1")
            .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsBytes(Map.of("login", root.login(), "password", rootPassword)))).andReturn();
        // Use the actual configured browser policy origin (default secure origin).
        assertEquals(200, code(result));
        String access = json.readTree(result.getResponse().getContentAsByteArray()).get("accessToken").asText();
        String sid = SignedJWT.parse(access).getJWTClaimsSet().getStringClaim("sid"); assertNotNull(sid);
        jdbc.update("UPDATE " + SCHEMA + "auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE session_id=?", UUID.fromString(sid));
        assertEquals(401, code(create(access, request(name(), UUID.randomUUID().toString()))));
    }
    @Test void requiredAuditFailureRollsBackUserAndRole() throws Exception {
        String name = name(); long beforeUsers = count("app_users"), beforeRoles = count("user_roles");
        doThrow(new IllegalStateException("test-only-audit-failure")).when(events).saveAndFlush(argThat(e -> e != null && "ACCOUNT_CREATED".equals(e.getEventType()) && "SUCCESS".equals(e.getOutcome())));
        var result = create(token, request(name, UUID.randomUUID().toString()));
        assertEquals(503, code(result)); assertEquals(beforeUsers, count("app_users")); assertEquals(beforeRoles, count("user_roles"));
        assertFalse(result.getResponse().getContentAsString().contains("test-only-audit-failure"));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM " + SCHEMA + "app_users WHERE login_normalized=?", Integer.class, name));
    }
    @Test void originalAccountAndFinancialRowsAreUnchanged() throws Exception {
        var original = jdbc.queryForList("SELECT * FROM " + SCHEMA + "app_users ORDER BY user_id");
        UUID payment = UUID.randomUUID();
        jdbc.update("INSERT INTO " + SCHEMA + "payments(payment_id,merchant_id,customer_id,amount,currency,payment_method,status) VALUES (?,'TEST_ONLY','TEST',25,'USD','CARD','SUCCESS')", payment);
        jdbc.update("INSERT INTO " + SCHEMA + "refunds(refund_id,payment_id,amount,status,idempotency_key) VALUES (?,?,5,'SUCCESS',?)", UUID.randomUUID(), payment, UUID.randomUUID().toString());
        Map<String,List<Map<String,Object>>> before = new HashMap<>();
        for (String table : List.of("payments", "refunds", "payment_gateway_transactions", "merchants", "merchant_memberships", "merchant_registrations")) before.put(table, jdbc.queryForList("SELECT * FROM " + SCHEMA + table));
        assertEquals(201, code(create(token, request(name(), UUID.randomUUID().toString()))));
        for (var row : original) assertEquals(row, jdbc.queryForMap("SELECT * FROM " + SCHEMA + "app_users WHERE user_id=?", row.get("user_id")));
        for (var table : before.keySet()) assertEquals(before.get(table), jdbc.queryForList("SELECT * FROM " + SCHEMA + table));
    }
    @Test void boundedBodiesMalformedJsonDuplicateKeysAndMethodsFailSafely() throws Exception {
        assertEquals(413, code(mvc.perform(post("/api/v1/admin/accounts").header("Authorization", "Bearer " + token)
            .contentType(MediaType.APPLICATION_JSON).content("x".repeat(4097))).andReturn()));
        for (String body : List.of("{", "null", "{}", "{} {}", "{\"login\":\"first\",\"login\":\"second\"}"))
            assertEquals(400, code(mvc.perform(post("/api/v1/admin/accounts").header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON).content(body)).andReturn()));
        assertEquals(200, code(mvc.perform(get("/api/v1/admin/accounts").header("Authorization", "Bearer " + token)).andReturn()));
    }
}
