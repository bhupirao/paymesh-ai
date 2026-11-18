package com.paymesh.backend.testing;

import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jwt.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.*;
import java.security.interfaces.RSAPrivateKey;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.Callable;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

/** Real signed test identities, confined to the script's verified database. No auth filter bypass. */
public abstract class BusinessJwtTestSupport {
    private static final KeyPair KEYS;
    private static final Path KEY_DIRECTORY;
    private static final String ISSUER = "https://business-tests.paymesh.invalid";
    private static final String AUDIENCE = "business-tests";
    static {
        try {
            KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA"); generator.initialize(2048); KEYS = generator.generateKeyPair();
            KEY_DIRECTORY = Files.createTempDirectory("paymesh-business-jwt-");
            pem(KEY_DIRECTORY.resolve("private.pem"), "PRIVATE KEY", KEYS.getPrivate().getEncoded());
            pem(KEY_DIRECTORY.resolve("public.pem"), "PUBLIC KEY", KEYS.getPublic().getEncoded());
            Files.setPosixFilePermissions(KEY_DIRECTORY.resolve("private.pem"), PosixFilePermissions.fromString("rw-------"));
            KEY_DIRECTORY.toFile().deleteOnExit(); KEY_DIRECTORY.resolve("public.pem").toFile().deleteOnExit(); KEY_DIRECTORY.resolve("private.pem").toFile().deleteOnExit();
        } catch (Exception ex) { throw new ExceptionInInitializerError(ex); }
    }
    private static void pem(Path path, String type, byte[] key) throws Exception {
        Files.writeString(path, "-----BEGIN " + type + "-----\n" + Base64.getMimeEncoder().encodeToString(key) + "\n-----END " + type + "-----\n");
    }
    @DynamicPropertySource static void jwtProperties(DynamicPropertyRegistry registry) {
        registry.add("paymesh.jwt.private-key-file", () -> KEY_DIRECTORY.resolve("private.pem").toString());
        registry.add("paymesh.jwt.public-key-file", () -> KEY_DIRECTORY.resolve("public.pem").toString());
        registry.add("paymesh.jwt.issuer", () -> ISSUER); registry.add("paymesh.jwt.audience", () -> AUDIENCE);
    }

    @Autowired protected JdbcTemplate jdbc;
    @Autowired protected PasswordEncoder passwordEncoder;
    @Autowired protected JwtDecoder jwtDecoder;
    protected Identity caller;
    private UUID reviewer;
    private String fixtureHash;
    protected record Identity(UUID userId, String token, String role) {}
    protected Set<String> allowedMerchants() { return Set.of(); }

    @BeforeEach
    void initializeBusinessCaller() throws Exception {
        caller = identity("MERCHANT", allowedMerchants());
        org.springframework.security.test.context.TestSecurityContextHolder.clearContext();
    }
    @AfterEach void clearBusinessCaller() { org.springframework.security.test.context.TestSecurityContextHolder.clearContext(); }

    protected Identity identity(String role, Set<String> merchantIds) throws Exception {
        if (fixtureHash == null) fixtureHash = passwordEncoder.encode(UUID.randomUUID().toString());
        if (reviewer == null) reviewer = user("ADMIN");
        UUID id = user(role);
        for (String merchant : merchantIds) {
            jdbc.update("INSERT INTO merchants(merchant_id, verified, active, verified_by, verified_at) VALUES (?, TRUE, TRUE, ?, CURRENT_TIMESTAMP) "
                    + "ON CONFLICT (merchant_id) DO NOTHING", merchant, reviewer);
            jdbc.update("INSERT INTO merchant_memberships(user_id, merchant_id, active, granted_by) VALUES (?, ?, TRUE, ?)", id, merchant, reviewer);
        }
        return refreshed(id, role);
    }
    private UUID user(String role) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO app_users(user_id, login_normalized, password_hash, enabled) VALUES (?, ?, ?, TRUE)", id, "fixture." + id, fixtureHash);
        jdbc.update("INSERT INTO user_roles(user_id, role_name) VALUES (?, ?)", id, role);
        return id;
    }
    protected Identity refreshed(UUID id, String role) throws Exception {
        long version = jdbc.queryForObject("SELECT authorization_version FROM app_users WHERE user_id = ?", Long.class, id);
        Instant now = Instant.now().truncatedTo(java.time.temporal.ChronoUnit.SECONDS);
        var claims = new JWTClaimsSet.Builder().issuer(ISSUER).audience(AUDIENCE).subject(id.toString())
                .jwtID(UUID.randomUUID().toString()).issueTime(Date.from(now)).notBeforeTime(Date.from(now))
                .expirationTime(Date.from(now.plusSeconds(900))).claim("authorization_version", version).claim("roles", List.of(role)).build();
        var token = new SignedJWT(new JWSHeader(JWSAlgorithm.RS256), claims);
        token.sign(new RSASSASigner((RSAPrivateKey) KEYS.getPrivate()));
        return new Identity(id, token.serialize(), role);
    }
    protected void activate(Identity identity) {
        var context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(new JwtAuthenticationToken(jwtDecoder.decode(identity.token()),
                List.of(new SimpleGrantedAuthority("ROLE_" + identity.role()))));
        SecurityContextHolder.setContext(context);
    }
    protected RequestPostProcessor businessJwt() { return jwt(caller); }
    protected RequestPostProcessor jwt(Identity identity) { return req -> { req.addHeader("Authorization", "Bearer " + identity.token()); return req; }; }
    protected <T> T asCaller(Callable<T> action) throws Exception { return as(caller, action); }
    protected <T> T as(Identity identity, Callable<T> action) throws Exception {
        var before = SecurityContextHolder.getContext();
        try { activate(identity); return action.call(); }
        finally { SecurityContextHolder.setContext(before); }
    }
}
