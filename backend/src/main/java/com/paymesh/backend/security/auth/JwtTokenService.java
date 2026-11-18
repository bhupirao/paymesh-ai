package com.paymesh.backend.security.auth;

import com.nimbusds.jose.jwk.*;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import com.paymesh.backend.security.accounts.AccountTokenStateService;
import java.time.Clock;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.security.oauth2.jwt.*;

final class JwtTokenService {
    private final JwtKeyMaterial keys;
    private final AccountTokenStateService accounts;
    private final Clock clock;
    private final JwtEncoder encoder;

    JwtTokenService(JwtKeyMaterial keys, AccountTokenStateService accounts, Clock clock) {
        this.keys = keys; this.accounts = accounts; this.clock = clock;
        encoder = keys.configured() ? new NimbusJwtEncoder(new ImmutableJWKSet<>(new JWKSet(
                new RSAKey.Builder(keys.publicKey).privateKey(keys.privateKey).keyID(keys.keyId).build()))) : null;
    }

    TokenResponse issue(AuthenticatedAccount principal) {
        return issue(accounts.forAuthenticated(principal), null);
    }

    TokenResponse issue(com.paymesh.backend.security.accounts.AccountTokenStateService.TokenAccount account, UUID sessionId) {
        keys.requireConfigured();
        Instant issued = clock.instant().truncatedTo(ChronoUnit.SECONDS), expires = issued.plusSeconds(900);
        JwtClaimsSet claims = JwtClaimsSet.builder().issuer(keys.issuer).audience(List.of(keys.audience))
                .subject(account.userId().toString()).id(UUID.randomUUID().toString()).issuedAt(issued)
                .notBefore(issued).expiresAt(expires).claim("authorization_version", account.authorizationVersion())
                .claims(values -> { if(sessionId!=null)values.put("sid",sessionId.toString()); }).claim("account_status", account.accountStatus()).claim("roles", account.roles().stream().map(Enum::name).sorted().toList()).build();
        String token = encoder.encode(JwtEncoderParameters.from(
                JwsHeader.with(SignatureAlgorithm.RS256).keyId(keys.keyId).build(), claims)).getTokenValue();
        return new TokenResponse(token, "Bearer", 900, expires,account.login());
    }

    record TokenResponse(String accessToken, String tokenType, long expiresIn, Instant expiresAt,String login) {}
}
