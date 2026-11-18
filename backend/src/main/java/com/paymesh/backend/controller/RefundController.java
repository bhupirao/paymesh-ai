package com.paymesh.backend.controller;

import com.paymesh.backend.dto.RefundCreationResult;
import com.paymesh.backend.dto.RefundRequest;
import com.paymesh.backend.dto.RefundResponse;
import com.paymesh.backend.service.RefundService;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/payments/{paymentId}")
public class RefundController {
    private final RefundService service;

    public RefundController(RefundService service) {
        this.service = service;
    }

    @PostMapping("/refund")
    public ResponseEntity<RefundResponse> refund(
            @PathVariable("paymentId") UUID paymentId,
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @Valid @RequestBody RefundRequest request) {
        RefundCreationResult result = service.refund(paymentId, request, idempotencyKey);
        return ResponseEntity.status(result.created() ? HttpStatus.CREATED : HttpStatus.OK)
                .body(result.refund());
    }

    @GetMapping("/refund")
    public RefundResponse get(@PathVariable("paymentId") UUID paymentId) {
        return service.getRefund(paymentId);
    }

    @GetMapping("/refunds")
    public List<RefundResponse> history(@PathVariable("paymentId") UUID paymentId) {
        return service.getRefundHistory(paymentId);
    }
}
