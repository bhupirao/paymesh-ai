package com.paymesh.backend.security.auth;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.*;
import java.io.IOException;
import org.springframework.http.HttpMethod;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;
import org.springframework.security.web.util.matcher.RequestMatcher;
import org.springframework.web.filter.OncePerRequestFilter;

final class LoginRateLimitFilter extends OncePerRequestFilter {
    private final RequestMatcher login = new org.springframework.security.web.util.matcher.OrRequestMatcher(
            PathPatternRequestMatcher.withDefaults().matcher(HttpMethod.POST, "/api/v1/auth/login"),
            PathPatternRequestMatcher.withDefaults().matcher(HttpMethod.POST, "/api/v1/auth/register"),
            PathPatternRequestMatcher.withDefaults().matcher(HttpMethod.POST, "/api/v1/auth/refresh"),
            PathPatternRequestMatcher.withDefaults().matcher(HttpMethod.POST, "/api/v1/auth/logout"),
            PathPatternRequestMatcher.withDefaults().matcher(HttpMethod.POST, "/api/v1/auth/logout-all"));
    private final LoginRateLimiter limiter;
    private final SecurityResponses responses;
    LoginRateLimitFilter(LoginRateLimiter limiter, SecurityResponses responses) { this.limiter = limiter; this.responses = responses; }
    @Override protected boolean shouldNotFilter(HttpServletRequest request) { return !login.matches(request); }
    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        var decision = limiter.acquire(request.getRemoteAddr());
        if (!decision.allowed()) {
            response.setHeader("Retry-After", Long.toString(decision.retryAfterSeconds()));
            responses.write(response, 429); return;
        }
        chain.doFilter(request, response);
    }
}
