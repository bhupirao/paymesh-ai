package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Map;
import org.springframework.security.core.AuthenticationException;
import com.paymesh.backend.security.SecurityStateUnavailableException;

final class SecurityResponses {
    private final ObjectMapper json;
    SecurityResponses(ObjectMapper json) { this.json = json; }
    void write(HttpServletResponse response, int status) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json");
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("Pragma", "no-cache");
        if (status == 401) response.setHeader("WWW-Authenticate", "Bearer");
        String message = switch (status) {
            case 401 -> "Authentication failed";
            case 403 -> "Access denied";
            case 429 -> "Too many login attempts";
            case 413 -> "Request too large";
            default -> "Authentication unavailable";
        };
        json.writeValue(response.getOutputStream(), Map.of("status", status, "message", message));
    }
    void writeAuthenticationFailure(HttpServletResponse response, AuthenticationException failure) throws IOException {
        for (Throwable cause = failure; cause != null; cause = cause.getCause()) {
            if (cause instanceof SecurityStateUnavailableException) { write(response, 503); return; }
        }
        write(response, 401);
    }
}
