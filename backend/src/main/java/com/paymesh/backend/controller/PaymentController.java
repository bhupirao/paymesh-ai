
package com.paymesh.backend.controller;

import com.paymesh.backend.dto.PaymentCreationResult;
import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.service.PaymentService;
import java.util.UUID;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import com.paymesh.backend.service.PaymentOrchestrationService;
import org.springframework.http.ResponseEntity;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/payments")
public class PaymentController {

    private final PaymentService paymentService;
    private final PaymentOrchestrationService paymentOrchestrationService;

    public PaymentController(PaymentService paymentService,PaymentOrchestrationService paymentOrchestrationService) {
        this.paymentService = paymentService;
        this.paymentOrchestrationService = paymentOrchestrationService;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(
                Map.of(
                        "service", "PayMesh AI Payment Service",
                        "status", "RUNNING"
                )
        );
    }



    @PostMapping
    public ResponseEntity<PaymentResponse> createPayment(
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @Valid @RequestBody PaymentRequest request
    ) {
        PaymentCreationResult result =
                paymentService.createPayment(request, idempotencyKey);

        HttpStatus status = result.created()
                ? HttpStatus.CREATED
                : HttpStatus.OK;

        return ResponseEntity
                .status(status)
                .body(result.payment());
    }



    @GetMapping("/{paymentId}")
    public ResponseEntity<PaymentResponse> getPaymentById(
            @PathVariable("paymentId") UUID paymentId
    ) {
        PaymentResponse response =
                paymentService.getPaymentById(paymentId);

        return ResponseEntity.ok(response);
    }

    @PostMapping("/{paymentId}/process")
    public ResponseEntity<PaymentResponse> processPayment(
            @PathVariable("paymentId") UUID paymentId
    ) {
        PaymentResponse response =
                paymentOrchestrationService.processPayment(paymentId);

        return ResponseEntity.ok(response);
    }


}
