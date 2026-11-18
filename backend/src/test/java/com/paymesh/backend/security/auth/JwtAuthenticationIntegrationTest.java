package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.*;
import com.nimbusds.jwt.*;
import com.paymesh.backend.security.accounts.AccountTokenStateService;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.KeyPair;
import java.security.interfaces.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.*;
import org.springframework.context.annotation.*;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.test.web.servlet.*;
import org.springframework.web.bind.annotation.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "spring.flyway.default-schema=jwt_phase3a_test", "spring.flyway.schemas=jwt_phase3a_test",
        "spring.jpa.properties.hibernate.default_schema=jwt_phase3a_test",
        "paymesh.jwt.issuer=https://issuer.paymesh.test", "paymesh.jwt.audience=paymesh-api",
        "paymesh.auth.login.max-attempts=3", "paymesh.auth.login.window-seconds=60"})
@AutoConfigureMockMvc
@Import(JwtAuthenticationIntegrationTest.ProbeConfiguration.class)
class JwtAuthenticationIntegrationTest {
    private static final KeyPair KEYS;
    private static final Path DIRECTORY;
    private static final AtomicInteger CLIENTS = new AtomicInteger();
    private static final String SETTLEMENT_TOKEN = UUID.randomUUID().toString() + UUID.randomUUID();
    private static final String WEBHOOK_SECRET = UUID.randomUUID().toString() + UUID.randomUUID();
    static {
        try {
            KEYS = JwtKeyMaterialTest.pair(2048);
            DIRECTORY = Files.createTempDirectory("paymesh-jwt-test-");
            JwtKeyMaterialTest.pem(DIRECTORY.resolve("private.pem"), "PRIVATE KEY", KEYS.getPrivate().getEncoded());
            JwtKeyMaterialTest.pem(DIRECTORY.resolve("public.pem"), "PUBLIC KEY", KEYS.getPublic().getEncoded());
            try { Files.setPosixFilePermissions(DIRECTORY.resolve("private.pem"), java.nio.file.attribute.PosixFilePermissions.fromString("rw-------")); }
            catch (UnsupportedOperationException ignored) { /* Non-POSIX CI filesystem. */ }
            DIRECTORY.resolve("private.pem").toFile().deleteOnExit(); DIRECTORY.resolve("public.pem").toFile().deleteOnExit(); DIRECTORY.toFile().deleteOnExit();
        } catch (Exception ex) { throw new ExceptionInInitializerError(ex); }
    }
    @DynamicPropertySource static void keys(DynamicPropertyRegistry registry) {
        registry.add("paymesh.jwt.private-key-file", () -> DIRECTORY.resolve("private.pem").toString());
        registry.add("paymesh.jwt.public-key-file", () -> DIRECTORY.resolve("public.pem").toString());
        registry.add("paymesh.settlement.admin-token", () -> SETTLEMENT_TOKEN);
        registry.add("paymesh.webhooks.razorpay-secret", () -> WEBHOOK_SECRET);
    }

    // Protected transport probe exists only in this test context, never in production.
    @TestConfiguration(proxyBeanMethods = false)
    static class ProbeConfiguration { @Bean Probe probe() { return new Probe(); } }
    @RestController
    @TestComponent
    static class Probe {
        @GetMapping("/api/v1/_test/probe")
        Map<String, Object> authenticated(Authentication auth) {
            return Map.of("userId", auth.getName(), "roles", auth.getAuthorities().stream().map(Object::toString).sorted().toList());
        }
    }

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired PasswordEncoder passwords;
    @Autowired JwtDecoder decoder;
    @MockitoSpyBean AccountTokenStateService tokenStates;
    record Account(UUID id, String login, String password) {}

    private Account account() {
        return account("MERCHANT");
    }
    private Account account(String role) {
        Account a = new Account(UUID.randomUUID(), "jwt." + UUID.randomUUID(), UUID.randomUUID().toString());
        jdbc.update("INSERT INTO jwt_phase3a_test.app_users(user_id, login_normalized, password_hash, enabled) VALUES (?, ?, ?, TRUE)",
                a.id(), a.login(), passwords.encode(a.password()));
        jdbc.update("INSERT INTO jwt_phase3a_test.user_roles(user_id, role_name) VALUES (?, ?)", a.id(), role);
        return a;
    }
    private String address() { return "192.0.2." + CLIENTS.incrementAndGet(); }
    private MvcResult login(Account account) throws Exception { return login(account, address()); }
    private MvcResult login(Account account, String address) throws Exception {
        return mvc.perform(post("/api/v1/auth/login").with(request -> { request.setRemoteAddr(address); return request; })
                .contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("login", account.login(), "password", account.password())))).andReturn();
    }
    private String token(Account account) throws Exception {
        var result = login(account); assertEquals(200, result.getResponse().getStatus());
        return json.readTree(result.getResponse().getContentAsString()).get("accessToken").asText();
    }
    private String signed(Account a, Consumer<JWTClaimsSet.Builder> change, JWSAlgorithm algorithm) throws Exception {
        Instant now = Instant.now().truncatedTo(java.time.temporal.ChronoUnit.SECONDS);
        JWTClaimsSet.Builder claims = new JWTClaimsSet.Builder().issuer("https://issuer.paymesh.test").audience("paymesh-api")
                .subject(a.id().toString()).jwtID(UUID.randomUUID().toString()).issueTime(Date.from(now))
                .notBeforeTime(Date.from(now)).expirationTime(Date.from(now.plusSeconds(900)))
                .claim("authorization_version", 0L).claim("roles", List.of("MERCHANT"));
        change.accept(claims);
        SignedJWT signed = new SignedJWT(new JWSHeader(algorithm), claims.build());
        signed.sign(new RSASSASigner((RSAPrivateKey) KEYS.getPrivate())); return signed.serialize();
    }
    private void rejected(String token) throws Exception {
        mvc.perform(get("/api/v1/auth/_test/probe").header("Authorization", "Bearer " + token))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.message").value("Authentication failed"));
    }

    @Test
    void validLoginIssuesRs256FifteenMinuteTokenAndUsesNoSession() throws Exception {
        Account a = account();
        MvcResult result = login(a);
        assertEquals(200, result.getResponse().getStatus());
        JsonNode response = json.readTree(result.getResponse().getContentAsString());
        assertEquals("Bearer", response.get("tokenType").asText());
        assertEquals(900, response.get("expiresIn").asInt());
        String token = response.get("accessToken").asText();
        var jwt = decoder.decode(token);
        assertEquals("RS256", jwt.getHeaders().get("alg"));
        assertEquals(900, Duration.between(jwt.getIssuedAt(), jwt.getExpiresAt()).getSeconds());
        assertEquals(a.id().toString(), jwt.getSubject());
        assertEquals(List.of("MERCHANT"), jwt.getClaimAsStringList("roles"));
        assertTrue(result.getResponse().getHeader("Cache-Control").contains("no-store"));
        assertNull(result.getRequest().getSession(false));
        assertNull(result.getResponse().getCookie("JSESSIONID"));
        mvc.perform(get("/api/v1/_test/probe").header("Authorization", "Bearer " + token))
                .andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/_test/probe")).andExpect(status().isUnauthorized());
    }

    @Test
    void wrongUnknownAndDisabledCredentialsReturnSameGeneric401() throws Exception {
        Account a = account();
        var wrong = login(new Account(a.id(), a.login(), UUID.randomUUID().toString()));
        var missing = login(new Account(UUID.randomUUID(), "missing." + UUID.randomUUID(), a.password()));
        jdbc.update("UPDATE jwt_phase3a_test.app_users SET enabled = FALSE WHERE user_id = ?", a.id());
        var disabled = login(a);
        assertEquals(401, wrong.getResponse().getStatus()); assertEquals(401, missing.getResponse().getStatus());
        assertEquals(401, disabled.getResponse().getStatus());
        assertEquals(wrong.getResponse().getContentAsString(), missing.getResponse().getContentAsString());
        assertEquals(wrong.getResponse().getContentAsString(), disabled.getResponse().getContentAsString());
    }

    @Test
    void expiredFutureAndMissingTemporalClaimsAreRejected() throws Exception {
        Account a = account();
        rejected(signed(a, c -> c.expirationTime(Date.from(Instant.now().minusSeconds(1))), JWSAlgorithm.RS256));
        rejected(signed(a, c -> c.notBeforeTime(Date.from(Instant.now().plusSeconds(60))), JWSAlgorithm.RS256));
        rejected(signed(a, c -> c.expirationTime(null), JWSAlgorithm.RS256));
        rejected(signed(a, c -> c.notBeforeTime(null), JWSAlgorithm.RS256));
        rejected(signed(a, c -> c.expirationTime(Date.from(Instant.now().plusSeconds(1800))), JWSAlgorithm.RS256));
    }

    @Test
    void wrongIssuerAudienceSignatureAndAlgorithmAreRejected() throws Exception {
        Account a = account();
        rejected(signed(a, c -> c.issuer("https://wrong.test"), JWSAlgorithm.RS256));
        rejected(signed(a, c -> c.audience("wrong-api"), JWSAlgorithm.RS256));
        rejected(signed(a, c -> {}, JWSAlgorithm.RS512));
        String valid = token(a);
        String[] parts = valid.split("\\.");
        parts[1] = Base64.getUrlEncoder().withoutPadding().encodeToString("{\"sub\":\"tampered\"}".getBytes(StandardCharsets.UTF_8));
        rejected(String.join(".", parts));
        var hmac = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), SignedJWT.parse(valid).getJWTClaimsSet());
        hmac.sign(new MACSigner(new byte[32])); rejected(hmac.serialize());
        rejected(new PlainJWT(SignedJWT.parse(valid).getJWTClaimsSet()).serialize());
        SignedJWT differentKey = new SignedJWT(new JWSHeader(JWSAlgorithm.RS256), SignedJWT.parse(valid).getJWTClaimsSet());
        differentKey.sign(new RSASSASigner((RSAPrivateKey) JwtKeyMaterialTest.pair(2048).getPrivate())); rejected(differentKey.serialize());
    }

    @Test
    void accountDisableAuthorizationRevocationAndServerRoleChangesInvalidateTokens() throws Exception {
        Account a = account(); String original = token(a);
        jdbc.update("UPDATE jwt_phase3a_test.app_users SET authorization_version = authorization_version + 1 WHERE user_id = ?", a.id());
        rejected(original);
        String fresh = token(a);
        jdbc.update("UPDATE jwt_phase3a_test.app_users SET enabled = FALSE WHERE user_id = ?", a.id()); rejected(fresh);
        jdbc.update("UPDATE jwt_phase3a_test.app_users SET enabled = TRUE WHERE user_id = ?", a.id());
        // Remove the server role without bumping version: role validation must still reject stale claims.
        jdbc.update("DELETE FROM jwt_phase3a_test.user_roles WHERE user_id = ?", a.id()); rejected(fresh);
        assertEquals(401, login(a).getResponse().getStatus());
        Account b = account();
        rejected(signed(b, c -> c.claim("roles", List.of("ADMIN")), JWSAlgorithm.RS256));
    }

    @Test
    void rateLimitReturns429AndSpoofedForwardedHeaderDoesNotResetBudget() throws Exception {
        Account a = account(); String address = address();
        for (int i = 0; i < 3; i++) assertEquals(200, login(a, address).getResponse().getStatus());
        mvc.perform(post("/api/v1/auth/login").with(req -> { req.setRemoteAddr(address); return req; })
                .header("X-Forwarded-For", "198.51.100.99").contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("login", a.login(), "password", a.password()))))
                .andExpect(status().isTooManyRequests()).andExpect(header().exists("Retry-After"));
        assertEquals(200, login(a, address()).getResponse().getStatus());
    }

    @Test
    void compatibilityPathsIgnoreJwtAndNewPathsAreNotPublic() throws Exception {
        mvc.perform(get("/api/v1/payments/health").header("Authorization", "Bearer not-a-jwt"))
                .andExpect(status().isOk());
        mvc.perform(get("/api/v1/payments/" + UUID.randomUUID())).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/settlement/payments/" + UUID.randomUUID() + "/reconcile")
                .header("Authorization", "Bearer not-the-settlement-token"))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/settlement/payments/" + UUID.randomUUID() + "/webhooks")
                .header("Authorization", "Bearer " + SETTLEMENT_TOKEN)).andExpect(status().isOk());
        String accessToken = token(account());
        mvc.perform(post("/api/v1/settlement/payments/" + UUID.randomUUID() + "/reconcile")
                .header("Authorization", "Bearer " + accessToken)).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/webhooks/mock-razorpay").header("Authorization", "Bearer " + accessToken)
                .header("X-Paymesh-Timestamp", Long.toString(Instant.now().getEpochSecond()))
                .header("X-Paymesh-Signature", "0".repeat(64)).contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest());
        mvc.perform(get("/api/v1/payments/new/unreviewed/route")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/webhooks/unreviewed-provider")).andExpect(status().isUnauthorized());
    }

    @Test
    void authNamespaceDeniesEveryRequestExceptPostLoginForAdminAndMerchantTokens() throws Exception {
        String merchant = token(account("MERCHANT"));
        String admin = token(account("ADMIN"));
        for (String bearer : List.of(merchant, admin)) {
            mvc.perform(get("/api/v1/auth/register").header("Authorization", "Bearer " + bearer))
                    .andExpect(status().isForbidden());
            mvc.perform(post("/api/v1/auth/unknown").header("Authorization", "Bearer " + bearer))
                    .andExpect(status().isForbidden());
            mvc.perform(get("/api/v1/auth/login").header("Authorization", "Bearer " + bearer))
                    .andExpect(status().isForbidden());
        }
        mvc.perform(get("/api/v1/auth/login")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/auth/unknown")).andExpect(status().isUnauthorized());
    }

    @Test
    void tokenStateDatabaseFailureReturnsUnavailableInsteadOfInvalidCredentials() throws Exception {
        String accessToken = token(account());
        org.mockito.Mockito.doThrow(new DataAccessResourceFailureException("simulated database outage"))
                .when(tokenStates).forToken(org.mockito.ArgumentMatchers.any());
        mvc.perform(get("/api/v1/_test/probe").header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.message").value("Authentication unavailable"));
    }

    @Test
    void untranslatedJpaPersistenceFailureAlsoReturnsUnavailable() throws Exception {
        String accessToken = token(account());
        org.mockito.Mockito.doThrow(new jakarta.persistence.PersistenceException("simulated persistence outage"))
                .when(tokenStates).forToken(org.mockito.ArgumentMatchers.any());
        mvc.perform(get("/api/v1/_test/probe").header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.message").value("Authentication unavailable"));
    }
}
