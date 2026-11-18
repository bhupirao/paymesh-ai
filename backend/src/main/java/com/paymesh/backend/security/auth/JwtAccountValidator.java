package com.paymesh.backend.security.auth;

import com.paymesh.backend.security.accounts.AccountRole;
import com.paymesh.backend.security.accounts.AccountTokenStateService;
import com.paymesh.backend.security.accounts.AccountTokenStateService.TokenAccount;
import com.paymesh.backend.security.SecurityStateUnavailableException;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;
import org.springframework.security.oauth2.core.*;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.dao.DataAccessException;
import jakarta.persistence.PersistenceException;
import org.springframework.transaction.TransactionSystemException;

final class JwtAccountValidator implements OAuth2TokenValidator<Jwt> {
    private final AccountTokenStateService accounts;
    private final JwtKeyMaterial keys;
    private final Clock clock;
    private final com.paymesh.backend.security.accounts.PersistentSessions sessions;
    JwtAccountValidator(AccountTokenStateService accounts, JwtKeyMaterial keys, Clock clock, com.paymesh.backend.security.accounts.PersistentSessions sessions) {
        this.accounts = accounts; this.keys = keys; this.clock = clock; this.sessions=sessions;
    }

    @Override public OAuth2TokenValidatorResult validate(Jwt jwt) {
        try { current(jwt); return OAuth2TokenValidatorResult.success(); }
        catch (DataAccessException ex) { throw new SecurityStateUnavailableException(); }
        catch (PersistenceException | TransactionSystemException ex) { throw new SecurityStateUnavailableException(); }
        catch (SecurityStateUnavailableException ex) { throw ex; }
        catch (RuntimeException ex) {
            return OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token", "Invalid access token", null));
        }
    }

    TokenAccount current(Jwt jwt) {
        Instant now = clock.instant(), issued = jwt.getIssuedAt(), expires = jwt.getExpiresAt(), notBefore = jwt.getNotBefore();
        if (!"RS256".equals(jwt.getHeaders().get("alg")) || !keys.issuer.equals(jwt.getClaimAsString("iss"))
                || jwt.getAudience() == null || !jwt.getAudience().contains(keys.audience)
                || issued == null || expires == null || notBefore == null || issued.isAfter(now)
                || !expires.isAfter(now) || notBefore.isAfter(now) || !notBefore.equals(issued)
                || !expires.isAfter(issued) || Duration.between(issued, expires).compareTo(Duration.ofMinutes(15)) > 0
                || jwt.getId() == null || jwt.getId().isBlank() || jwt.getId().length() > 128) throw new IllegalArgumentException();
        UUID userId = UUID.fromString(jwt.getSubject());
        if (!userId.toString().equals(jwt.getSubject())) throw new IllegalArgumentException();
        Object rawVersion = jwt.getClaim("authorization_version");
        if (!(rawVersion instanceof Number)) throw new IllegalArgumentException();
        long version = new BigDecimal(rawVersion.toString()).toBigIntegerExact().longValueExact();
        Object rawRoles = jwt.getClaim("roles");
        if (!(rawRoles instanceof List<?> values) || values.isEmpty() || values.stream().anyMatch(v -> !(v instanceof String))) {
            throw new IllegalArgumentException();
        }
        Set<AccountRole> claimed = values.stream().map(v -> AccountRole.valueOf((String) v)).collect(Collectors.toSet());
        if (claimed.size() != values.size()) throw new IllegalArgumentException();
        TokenAccount current = accounts.forToken(userId);
        if (!Objects.equals(current.accountStatus(), jwt.getClaimAsString("account_status") == null ? "ACTIVE" : jwt.getClaimAsString("account_status"))) throw new IllegalArgumentException();
        if (version < 0 || current.authorizationVersion() != version || !current.roles().equals(claimed)) throw new IllegalArgumentException();
        String sid=jwt.getClaimAsString("sid");
        if(sid!=null && (!UUID.fromString(sid).toString().equals(sid)||!sessions.validAccess(UUID.fromString(sid),current)))throw new IllegalArgumentException();
        return current;
    }
}
