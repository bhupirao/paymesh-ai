package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.paymesh.backend.security.accounts.AccountAccessDeniedException;
import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.Arrays;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.http.*;
import org.springframework.security.authentication.*;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.bind.annotation.*;

@RestController
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/auth")
public class AuthController {
    private final AuthenticationManager authentication;
    private final JwtTokenService tokens;
    private final JwtKeyMaterial keys;
    private final com.paymesh.backend.security.accounts.PersistentSessions sessions;
    private final AuthBrowserPolicy browser;
    public AuthController(AuthenticationManager authentication, JwtTokenService tokens, JwtKeyMaterial keys, com.paymesh.backend.security.accounts.PersistentSessions sessions, AuthBrowserPolicy browser) {
        this.authentication = authentication; this.tokens = tokens; this.keys = keys; this.sessions=sessions; this.browser=browser;
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@Valid @RequestBody LoginRequest request, jakarta.servlet.http.HttpServletRequest http) {
        try {
            if(browser.browserRequest(http)&&!browser.allowed(http))return ResponseEntity.status(403).cacheControl(CacheControl.noStore()).body(Map.of("status",403,"message","Request denied"));
            keys.requireConfigured();
            var result = authentication.authenticate(new UsernamePasswordAuthenticationToken(request.login, request.password));
            var principal=(AuthenticatedAccount)result.getPrincipal();
            if(browser.browserRequest(http)) {
                sessions.logout(browser.token(http));
                var grant=sessions.create(principal,Boolean.TRUE.equals(request.rememberMe));
                return ResponseEntity.ok().cacheControl(CacheControl.noStore()).header("Pragma","no-cache")
                    .header("Set-Cookie",browser.cookie(grant.refreshToken(),grant.rememberMe(),grant.expiresAt()))
                    .body(tokens.issue(grant.account(),grant.sessionId()));
            }
            return ResponseEntity.ok().cacheControl(CacheControl.noStore()).header("Pragma", "no-cache")
                    .body(tokens.issue((AuthenticatedAccount) result.getPrincipal()));
        } catch (AuthenticationException | AccountAccessDeniedException ex) {
            return ResponseEntity.status(401).cacheControl(CacheControl.noStore()).header("Pragma", "no-cache")
                    .body(Map.of("status", 401, "message", "Authentication failed"));
        } finally {
            if (request.password != null) Arrays.fill(request.password, '\0');
        }
    }

    public static class LoginRequest {
        public Boolean rememberMe = false;
        @NotBlank @Size(max = 255) public String login;
        @NotNull @Size(max = 72)
        @JsonProperty(access = JsonProperty.Access.WRITE_ONLY) public char[] password;
    }
}
