package com.paymesh.backend.security.accounts;

import java.util.Locale;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class AccountCredentials {
    private final AppUserRepository users;
    private final AccountPasswords passwords;
    private final AccountAudit audit;
    private final String dummyHash;
    private final TransactionTemplate verification;

    public AccountCredentials(AppUserRepository users, AccountPasswords passwords, AccountAudit audit,
                              PlatformTransactionManager transactionManager) {
        this.users = users; this.passwords = passwords; this.audit = audit;
        verification = new TransactionTemplate(transactionManager);
        verification.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        verification.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
        verification.setReadOnly(true);
        char[] random = UUID.randomUUID().toString().toCharArray();
        try { dummyHash = passwords.hash(random); }
        finally { java.util.Arrays.fill(random, '\0'); }
    }

    public AuthenticatedAccount authenticate(String login, char[] password) {
        String normalized;
        try { normalized = normalizeLogin(login); }
        catch (IllegalArgumentException ex) { normalized = null; }
        String lookup = normalized;
        UUID[] candidate = new UUID[1];
        try {
            return verification.execute(status -> {
                AppUser user = lookup == null ? null : users.findByLoginNormalized(lookup).orElse(null);
                candidate[0] = user == null ? null : user.getUserId();
                boolean matches = passwords.matches(password, user == null ? dummyHash : user.passwordHash());
                if (user == null || !matches || !user.isEnabled()) throw new AccountAccessDeniedException();
                return new AuthenticatedAccount(user.getUserId(), user.getAuthorizationVersion());
            });
        } catch (AccountAccessDeniedException ex) {
            audit.denied(candidate[0], "ACCOUNT_CREDENTIALS_REJECTED", null, "ACCOUNT", null);
            throw new AccountAccessDeniedException();
        }
    }

    /**
     * Adapter for an already verified bearer request, never a request-supplied user/role.
     * The administration transaction rechecks enabled/status/version/ADMIN under its lock.
     */
    public AuthenticatedAccount currentJwtAccount() {
        var authentication = org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
        if (!(authentication instanceof org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken token)
                || !token.isAuthenticated()) throw new AccountAccessDeniedException();
        try {
            var jwt = token.getToken();
            if (jwt.getExpiresAt() == null || !jwt.getExpiresAt().isAfter(java.time.Instant.now()))
                throw new AccountAccessDeniedException();
            UUID id = UUID.fromString(jwt.getSubject());
            Object raw = jwt.getClaim("authorization_version");
            if (!(raw instanceof Number)) throw new AccountAccessDeniedException();
            long version = new java.math.BigDecimal(raw.toString()).toBigIntegerExact().longValueExact();
            return new AuthenticatedAccount(id, version);
        } catch (RuntimeException ex) { throw new AccountAccessDeniedException(); }
    }

    static String normalizeLogin(String login) {
        if (login == null) throw new IllegalArgumentException("Login is required");
        String normalized = login.strip().toLowerCase(Locale.ROOT);
        // Explicit ASCII policy agrees with the V8 C-collation normalized login constraint.
        if (!normalized.matches("[a-z0-9][a-z0-9._@+\\-]{2,254}")) {
            throw new IllegalArgumentException("Login must contain 3 to 255 supported ASCII characters");
        }
        return normalized;
    }

    /** Unforgeable through public constructors; issued after credential verification or adapted from the verified Spring JWT context. Not an HTTP credential. */
    public static final class AuthenticatedAccount {
        private final UUID userId;
        private final long authorizationVersion;
        private AuthenticatedAccount(UUID userId, long version) { this.userId = userId; authorizationVersion = version; }
        public UUID userId() { return userId; }
        long authorizationVersion() { return authorizationVersion; }
    }
}
