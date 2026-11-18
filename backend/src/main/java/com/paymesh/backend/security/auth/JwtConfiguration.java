package com.paymesh.backend.security.auth;

import com.paymesh.backend.security.accounts.*;
import java.time.Clock;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.*;
import org.springframework.security.authentication.*;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.security.oauth2.jwt.*;

@Configuration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
public class JwtConfiguration {
    @Bean
    Clock jwtClock() { return Clock.systemUTC(); }

    @Bean
    JwtKeyMaterial jwtKeyMaterial(
            @Value("${paymesh.jwt.private-key-file:}") String privateFile,
            @Value("${paymesh.jwt.public-key-file:}") String publicFile,
            @Value("${paymesh.jwt.issuer:}") String issuer,
            @Value("${paymesh.jwt.audience:}") String audience) {
        return new JwtKeyMaterial(privateFile, publicFile, issuer, audience);
    }

    @Bean
    JwtAccountValidator jwtAccountValidator(AccountTokenStateService accounts, JwtKeyMaterial keys, Clock jwtClock, com.paymesh.backend.security.accounts.PersistentSessions sessions) {
        return new JwtAccountValidator(accounts, keys, jwtClock, sessions);
    }

    @Bean
    JwtDecoder jwtDecoder(JwtKeyMaterial keys, JwtAccountValidator validator) {
        if (!keys.configured()) return token -> { throw new BadJwtException("Authentication is not configured"); };
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withPublicKey(keys.publicKey).signatureAlgorithm(SignatureAlgorithm.RS256).build();
        // This validator requires exp/nbf/iat and also applies zero-skew expiry, issuer,
        // audience, lifetime, enabled/version checks and exact current role matching.
        decoder.setJwtValidator(validator);
        return decoder;
    }

    @Bean
    JwtTokenService jwtTokenService(JwtKeyMaterial keys, AccountTokenStateService accounts, Clock jwtClock) {
        return new JwtTokenService(keys, accounts, jwtClock);
    }

    @Bean
    AuthenticationManager accountAuthenticationManager(AccountCredentials credentials, AccountTokenStateService accounts) {
        return new ProviderManager(new AccountPasswordAuthenticationProvider(credentials, accounts));
    }

    @Bean
    LoginRateLimiter loginRateLimiter(@Value("${paymesh.auth.login.max-attempts:10}") int attempts,
                                      @Value("${paymesh.auth.login.window-seconds:60}") long seconds,
                                      @Value("${paymesh.auth.login.max-clients:10000}") int clients, Clock jwtClock) {
        return new LoginRateLimiter(attempts, seconds, clients, jwtClock);
    }
}
