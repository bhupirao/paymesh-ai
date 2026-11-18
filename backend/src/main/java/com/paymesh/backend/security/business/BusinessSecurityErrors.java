package com.paymesh.backend.security.business;

import com.paymesh.backend.controller.*;
import com.paymesh.backend.security.SecurityStateUnavailableException;
import java.util.Map;
import org.springframework.http.*;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.*;

@RestControllerAdvice(assignableTypes = {PaymentController.class, RefundController.class, GatewayTransactionController.class})
public class BusinessSecurityErrors {
    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<?> unauthenticated() { return response(401, "Authentication failed"); }
    @ExceptionHandler(SecurityStateUnavailableException.class)
    public ResponseEntity<?> authenticationUnavailable() { return response(503, "Authentication unavailable"); }
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<?> forbidden() { return response(403, "Access denied"); }
    @ExceptionHandler(BusinessResourceNotFoundException.class)
    public ResponseEntity<?> missing() { return response(404, "Resource not found"); }
    private ResponseEntity<?> response(int status, String message) {
        return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).body(Map.of("status", status, "message", message));
    }
}
