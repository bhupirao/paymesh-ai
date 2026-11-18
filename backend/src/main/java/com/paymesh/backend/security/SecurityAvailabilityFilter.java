package com.paymesh.backend.security;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Maps fail-closed authentication-state outages to a generic availability response. */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public final class SecurityAvailabilityFilter extends OncePerRequestFilter {
    private static final Logger log = LoggerFactory.getLogger(SecurityAvailabilityFilter.class);
    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        try { chain.doFilter(request, response); }
        catch (SecurityStateUnavailableException ex) { unavailable(response); }
        catch (ServletException ex) {
            if (hasUnavailableCause(ex)) unavailable(response);
            else throw ex;
        }
    }

    private boolean hasUnavailableCause(Throwable error) {
        for (Throwable cause = error; cause != null; cause = cause.getCause())
            if (cause instanceof SecurityStateUnavailableException) return true;
        return false;
    }

    private void unavailable(HttpServletResponse response) throws IOException {
        log.warn("Authentication state unavailable; request rejected");
        if (response.isCommitted()) return;
        response.resetBuffer();
        response.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
        response.setContentType("application/json");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("Pragma", "no-cache");
        response.getWriter().write("{\"status\":503,\"message\":\"Authentication unavailable\"}");
    }
}
