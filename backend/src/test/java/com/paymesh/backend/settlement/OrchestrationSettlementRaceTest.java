package com.paymesh.backend.settlement;

import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.gateway.*;
import com.paymesh.backend.service.*;
import com.paymesh.backend.service.internal.*;
import com.paymesh.backend.service.impl.PaymentOrchestrationServiceImpl;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import com.paymesh.backend.security.business.BusinessProcessingClaims;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class OrchestrationSettlementRaceTest {
    @ParameterizedTest
    @ValueSource(strings = {"SUCCESS", "FAILED", "CANCELLED", "REFUNDED"})
    void lateSynchronousSuccessReturnsCommittedTerminalState(String committed) {
        UUID id = UUID.randomUUID();
        var payments = mock(InternalPaymentService.class);
        var gateway = mock(PaymentGateway.class);
        var transactions = mock(InternalGatewayTransactionService.class);
        var claims = mock(BusinessProcessingClaims.class);
        when(claims.claim(id)).thenReturn(response(id, "PROCESSING"));
        var orchestration = new PaymentOrchestrationServiceImpl(payments, gateway, transactions, claims);
        when(payments.getPaymentById(id)).thenReturn(response(id, committed));
        when(gateway.getGatewayName()).thenReturn("MOCK_RAZORPAY");
        when(transactions.initiateTransaction(id, "MOCK_RAZORPAY")).thenReturn(new GatewayTransaction(id, "MOCK_RAZORPAY"));
        when(gateway.processPayment(id, BigDecimal.TEN, "INR"))
                .thenReturn(new GatewayResponse(UUID.randomUUID(), "MOCK_RAZORPAY", GatewayStatus.SUCCESS, null, null));
        when(payments.updatePaymentStatus(id, PaymentStatus.SUCCESS)).thenThrow(new IllegalStateException("Terminal state"));
        assertEquals(committed, orchestration.processPayment(id).status());
        verify(payments).updatePaymentStatus(id, PaymentStatus.SUCCESS);
    }

    private PaymentResponse response(UUID id, String status) {
        return new PaymentResponse(id, "M", BigDecimal.TEN, "INR", "C", "UPI", status, Instant.now());
    }
}
