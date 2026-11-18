package com.paymesh.backend.security.auth;

import com.paymesh.backend.security.accounts.*;
import org.springframework.security.authentication.*;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

final class AccountPasswordAuthenticationProvider implements AuthenticationProvider {
    private final AccountCredentials credentials;
    private final AccountTokenStateService accounts;
    AccountPasswordAuthenticationProvider(AccountCredentials credentials, AccountTokenStateService accounts) {
        this.credentials = credentials; this.accounts = accounts;
    }
    @Override public Authentication authenticate(Authentication authentication) {
        if (!(authentication.getCredentials() instanceof char[] password)) throw new BadCredentialsException("Invalid credentials");
        try {
            var principal = credentials.authenticate(authentication.getName(), password);
            var account = accounts.forAuthenticated(principal);
            return UsernamePasswordAuthenticationToken.authenticated(principal, null, account.roles().stream()
                    .map(r -> new SimpleGrantedAuthority("ROLE_" + r.name())).toList());
        } catch (AccountAccessDeniedException ex) { throw new BadCredentialsException("Invalid credentials"); }
    }
    @Override public boolean supports(Class<?> authentication) {
        return UsernamePasswordAuthenticationToken.class.isAssignableFrom(authentication);
    }
}
