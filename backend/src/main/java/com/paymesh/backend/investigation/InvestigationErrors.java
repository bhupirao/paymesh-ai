package com.paymesh.backend.investigation;

import com.paymesh.backend.exception.ApiErrorResponse;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestControllerAdvice(assignableTypes = InvestigationController.class)
public class InvestigationErrors {
    @ExceptionHandler({org.springframework.dao.DataAccessException.class, org.springframework.transaction.TransactionException.class})
    public ResponseEntity<ApiErrorResponse> unavailable(RuntimeException ex, HttpServletRequest request) {
        return failure(new InvestigationFailure(503, "Investigation evidence is unavailable"), request);
    }
    @ExceptionHandler(InvestigationFailure.class)
    public ResponseEntity<ApiErrorResponse> failure(InvestigationFailure ex, HttpServletRequest request) {
        return ResponseEntity.status(ex.status()).body(new ApiErrorResponse(Instant.now(), ex.status(),
                HttpStatus.valueOf(ex.status()).getReasonPhrase(), ex.getMessage(), Map.of(), request.getRequestURI()));
    }
}
