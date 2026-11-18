package com.paymesh.backend.controller;
import com.paymesh.backend.dto.GatewayTransactionResponse;
import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.service.GatewayTransactionService;
import com.paymesh.backend.service.PaymentService;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.UUID;
@RestController
@RequestMapping("/api/v1/payments")
public class GatewayTransactionController {
    private final GatewayTransactionService transactions;
    private final PaymentService payments;
    public GatewayTransactionController(GatewayTransactionService transactions, PaymentService payments) {
        this.transactions=transactions; this.payments=payments;
    }
    @GetMapping("/{paymentId}/gateway-transactions")
    public List<GatewayTransactionResponse> history(@PathVariable("paymentId") UUID paymentId) {
        payments.getPaymentById(paymentId);
        return transactions.getTransactionsByPaymentId(paymentId).stream().map(this::map).toList();
    }
    private GatewayTransactionResponse map(GatewayTransaction t) {
        return new GatewayTransactionResponse(t.getId(),t.getPaymentId(),t.getGatewayName(),
            t.getGatewayTransactionId(),t.getStatus(),t.getErrorCode(),t.getErrorMessage(),
            t.getCreatedAt(),t.getUpdatedAt());
    }
}
