
package com.paymesh.backend.service;

import com.paymesh.backend.service.internal.InternalPaymentService;
import com.paymesh.backend.service.internal.InternalGatewayTransactionService;

import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.exception.InvalidPaymentStateException;
import com.paymesh.backend.exception.PaymentGatewayException;
import com.paymesh.backend.gateway.GatewayResponse;
import com.paymesh.backend.gateway.GatewayStatus;
import com.paymesh.backend.gateway.PaymentGateway;
import com.paymesh.backend.service.impl.PaymentOrchestrationServiceImpl;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import com.paymesh.backend.security.business.BusinessProcessingClaims;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class PaymentOrchestrationServiceImplTest {

    private InternalPaymentService paymentService;
    private PaymentGateway paymentGateway;
    private InternalGatewayTransactionService gatewayTransactionService;

    private PaymentOrchestrationServiceImpl orchestrationService;

    private BusinessProcessingClaims claims;
    private UUID paymentId;
    private GatewayTransaction gatewayTransaction;
    private PaymentResponse processingPayment;

    @BeforeEach
    void setUp() {

        claims = mock(BusinessProcessingClaims.class);
        paymentService = mock(InternalPaymentService.class);
        paymentGateway = mock(PaymentGateway.class);
        gatewayTransactionService =
                mock(InternalGatewayTransactionService.class);

        paymentId = UUID.randomUUID();

        orchestrationService =
                new PaymentOrchestrationServiceImpl(
                        paymentService,
                        paymentGateway,
                        gatewayTransactionService, claims
                );

        processingPayment =
                paymentWithStatus("PROCESSING");

        when(claims.claim(paymentId)).thenReturn(paymentWithStatus("PROCESSING"));
        when(paymentService.getPaymentById(paymentId))
                .thenReturn(processingPayment);

        when(paymentGateway.getGatewayName())
                .thenReturn("MOCK_RAZORPAY");

        gatewayTransaction = new GatewayTransaction(
                paymentId,
                "MOCK_RAZORPAY"
        );

        when(gatewayTransactionService.initiateTransaction(
                eq(paymentId),
                eq("MOCK_RAZORPAY")
        )).thenReturn(gatewayTransaction);
    }

    private PaymentResponse paymentWithStatus(String status) {

        return new PaymentResponse(
                paymentId,
                "MERCHANT_TEST",
                new BigDecimal("500.00"),
                "INR",
                "CUSTOMER_TEST",
                "UPI",
                status,
                Instant.now()
        );
    }

    @Test
    void shouldProcessPaymentSuccessfully() {

        PaymentResponse successPayment =
                paymentWithStatus("SUCCESS");

        UUID gatewayReference = UUID.randomUUID();

        GatewayResponse gatewayResponse =
                new GatewayResponse(
                        gatewayReference,
                        "MOCK_RAZORPAY",
                        GatewayStatus.SUCCESS,
                        null,
                        null
                );

        when(paymentGateway.processPayment(
                eq(paymentId),
                eq(new BigDecimal("500.00")),
                eq("INR")
        )).thenReturn(gatewayResponse);

        when(paymentService.updatePaymentStatus(
                paymentId,
                PaymentStatus.SUCCESS
        )).thenReturn(successPayment);

        PaymentResponse response =
                orchestrationService.processPayment(paymentId);

        assertEquals("SUCCESS", response.status());

        verify(claims, times(1))
                .claim(paymentId);

        verify(gatewayTransactionService, times(1))
                .initiateTransaction(
                        paymentId,
                        "MOCK_RAZORPAY"
                );

        verify(paymentGateway, times(1))
                .processPayment(
                        paymentId,
                        new BigDecimal("500.00"),
                        "INR"
                );

        verify(gatewayTransactionService, times(1))
                .completeTransaction(
                        gatewayTransaction.getId(),
                        gatewayResponse
                );

        verify(paymentService, times(1))
                .updatePaymentStatus(
                        paymentId,
                        PaymentStatus.SUCCESS
                );

        verify(paymentService, never())
                .updatePaymentStatus(
                        paymentId,
                        PaymentStatus.PROCESSING
                );

        verify(gatewayTransactionService, never())
                .markTransactionUnknown(
                        any(UUID.class),
                        anyString()
                );

        var order = inOrder(
                claims, paymentService,
                gatewayTransactionService,
                paymentGateway
        );

        order.verify(claims)
                .claim(paymentId);

        order.verify(gatewayTransactionService)
                .initiateTransaction(
                        paymentId,
                        "MOCK_RAZORPAY"
                );

        order.verify(paymentGateway)
                .processPayment(
                        paymentId,
                        new BigDecimal("500.00"),
                        "INR"
                );

        order.verify(gatewayTransactionService)
                .completeTransaction(
                        gatewayTransaction.getId(),
                        gatewayResponse
                );

        order.verify(paymentService)
                .updatePaymentStatus(
                        paymentId,
                        PaymentStatus.SUCCESS
                );
    }

    @Test
    void shouldMarkPaymentFailedWhenGatewayFails() {

        GatewayResponse gatewayResponse =
                new GatewayResponse(
                        null,
                        "MOCK_RAZORPAY",
                        GatewayStatus.FAILED,
                        "DECLINED",
                        "Payment declined"
                );

        when(paymentGateway.processPayment(
                eq(paymentId),
                any(BigDecimal.class),
                eq("INR")
        )).thenReturn(gatewayResponse);

        when(paymentService.updatePaymentStatus(
                paymentId,
                PaymentStatus.FAILED
        )).thenReturn(paymentWithStatus("FAILED"));

        PaymentResponse response =
                orchestrationService.processPayment(paymentId);

        assertEquals("FAILED", response.status());

        verify(claims, times(1))
                .claim(paymentId);

        verify(gatewayTransactionService, times(1))
                .initiateTransaction(
                        paymentId,
                        "MOCK_RAZORPAY"
                );

        verify(paymentGateway, times(1))
                .processPayment(
                        eq(paymentId),
                        any(BigDecimal.class),
                        eq("INR")
                );

        verify(gatewayTransactionService, times(1))
                .completeTransaction(
                        gatewayTransaction.getId(),
                        gatewayResponse
                );

        verify(paymentService, times(1))
                .updatePaymentStatus(
                        paymentId,
                        PaymentStatus.FAILED
                );

        verify(paymentService, never())
                .updatePaymentStatus(
                        paymentId,
                        PaymentStatus.PROCESSING
                );

        verify(gatewayTransactionService, never())
                .markTransactionUnknown(
                        any(UUID.class),
                        anyString()
                );
    }

    @Test
    void shouldKeepProcessingWhenGatewayTimesOut() {

        GatewayResponse gatewayResponse =
                new GatewayResponse(
                        null,
                        "MOCK_RAZORPAY",
                        GatewayStatus.TIMEOUT,
                        "TIMEOUT",
                        "Gateway did not respond"
                );

        when(paymentGateway.processPayment(
                eq(paymentId),
                any(BigDecimal.class),
                eq("INR")
        )).thenReturn(gatewayResponse);

        PaymentResponse response =
                orchestrationService.processPayment(paymentId);

        assertEquals("PROCESSING", response.status());

        verify(claims, times(1))
                .claim(paymentId);

        verify(gatewayTransactionService, times(1))
                .initiateTransaction(
                        paymentId,
                        "MOCK_RAZORPAY"
                );

        verify(paymentGateway, times(1))
                .processPayment(
                        eq(paymentId),
                        any(BigDecimal.class),
                        eq("INR")
                );

        verify(gatewayTransactionService, times(1))
                .completeTransaction(
                        gatewayTransaction.getId(),
                        gatewayResponse
                );

        verify(paymentService, never())
                .updatePaymentStatus(
                        eq(paymentId),
                        any(PaymentStatus.class)
                );

        verify(gatewayTransactionService, never())
                .markTransactionUnknown(
                        any(UUID.class),
                        anyString()
                );
    }

    @Test
    void shouldRejectAlreadyProcessedPayment() {

        doThrow(new InvalidPaymentStateException(
                "Payment cannot be claimed"
        )).when(claims)
                .claim(paymentId);

        InvalidPaymentStateException exception =
                assertThrows(
                        InvalidPaymentStateException.class,
                        () -> orchestrationService.processPayment(paymentId)
                );

        assertEquals(
                "Payment cannot be claimed",
                exception.getMessage()
        );

        verify(claims, times(1))
                .claim(paymentId);

        verify(paymentService, never())
                .getPaymentById(any(UUID.class));

        verify(paymentService, never())
                .updatePaymentStatus(
                        any(UUID.class),
                        any(PaymentStatus.class)
                );

        verifyNoInteractions(
                paymentGateway,
                gatewayTransactionService
        );
    }

    @Test
    void shouldMarkTransactionUnknownWhenGatewayThrowsException() {

        when(paymentGateway.processPayment(
                eq(paymentId),
                any(BigDecimal.class),
                eq("INR")
        )).thenThrow(
                new RuntimeException("Gateway connection lost")
        );

        PaymentGatewayException exception =
                assertThrows(
                        PaymentGatewayException.class,
                        () -> orchestrationService.processPayment(paymentId)
                );

        assertTrue(
                exception.getMessage()
                        .contains("requires reconciliation")
        );

        verify(claims, times(1))
                .claim(paymentId);

        verify(gatewayTransactionService, times(1))
                .initiateTransaction(
                        paymentId,
                        "MOCK_RAZORPAY"
                );

        verify(paymentGateway, times(1))
                .processPayment(
                        eq(paymentId),
                        any(BigDecimal.class),
                        eq("INR")
                );

        verify(gatewayTransactionService, times(1))
                .markTransactionUnknown(
                        gatewayTransaction.getId(),
                        "Gateway connection lost"
                );

        verify(gatewayTransactionService, never())
                .completeTransaction(
                        any(UUID.class),
                        any(GatewayResponse.class)
                );

        verify(paymentService, never())
                .updatePaymentStatus(
                        eq(paymentId),
                        any(PaymentStatus.class)
                );
    }
}
