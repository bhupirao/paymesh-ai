
package com.paymesh.backend.integration;

import com.paymesh.backend.dto.PaymentCreationResult;
import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.repository.PaymentRepository;
import com.paymesh.backend.service.internal.InternalPaymentService;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.math.BigDecimal;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class PaymentLifecycleIntegrationTest {

    @Autowired
    private InternalPaymentService paymentService;

    @Autowired
    private PaymentRepository paymentRepository;

    @Test
    void shouldCompletePaymentLifecycle() {

        PaymentRequest request = new PaymentRequest(
                "MERCHANT_LIFECYCLE",
                new BigDecimal("2500.00"),
                "INR",
                "CUSTOMER_LIFECYCLE",
                "UPI"
        );

        PaymentCreationResult result =
                paymentService.createPayment(
                        request,
                        "LIFECYCLE-" + UUID.randomUUID()
                );

        UUID paymentId = result.payment().paymentId();

        // CREATED
        assertEquals(
                "CREATED",
                paymentService.getPaymentById(paymentId).status()
        );

        // CREATED -> PROCESSING
        PaymentResponse processing =
                paymentService.updatePaymentStatus(
                        paymentId,
                        PaymentStatus.PROCESSING
                );

        assertEquals("PROCESSING", processing.status());

        // PROCESSING -> SUCCESS
        PaymentResponse success =
                paymentService.updatePaymentStatus(
                        paymentId,
                        PaymentStatus.SUCCESS
                );

        assertEquals("SUCCESS", success.status());

        // Verify database persistence
        var savedPayment = paymentRepository
                .findById(paymentId)
                .orElseThrow();

        assertEquals(
                PaymentStatus.SUCCESS,
                savedPayment.getStatus()
        );
    }

    @Test
    void shouldRejectInvalidPaymentTransition() {

        PaymentRequest request = new PaymentRequest(
                "MERCHANT_INVALID",
                new BigDecimal("1000.00"),
                "INR",
                "CUSTOMER_INVALID",
                "UPI"
        );

        PaymentCreationResult result =
                paymentService.createPayment(
                        request,
                        "INVALID-" + UUID.randomUUID()
                );

        UUID paymentId = result.payment().paymentId();

        // CREATED -> SUCCESS is not allowed
        assertThrows(
                IllegalStateException.class,
                () -> paymentService.updatePaymentStatus(
                        paymentId,
                        PaymentStatus.SUCCESS
                )
        );

        // Verify the status remains unchanged
        assertEquals(
                "CREATED",
                paymentService.getPaymentById(paymentId).status()
        );
    }

    @Test
    void shouldMarkPaymentAsFailedAndRejectFurtherTransition() {

        PaymentRequest request = new PaymentRequest(
                "MERCHANT_FAILED",
                new BigDecimal("1750.00"),
                "INR",
                "CUSTOMER_FAILED",
                "UPI"
        );

        PaymentCreationResult result =
                paymentService.createPayment(
                        request,
                        "FAILED-" + UUID.randomUUID()
                );

        UUID paymentId = result.payment().paymentId();

        // Step 1: CREATED -> PROCESSING
        PaymentResponse processing =
                paymentService.updatePaymentStatus(
                        paymentId,
                        PaymentStatus.PROCESSING
                );

        assertEquals("PROCESSING", processing.status());

        // Step 2: PROCESSING -> FAILED
        PaymentResponse failed =
                paymentService.updatePaymentStatus(
                        paymentId,
                        PaymentStatus.FAILED
                );

        assertEquals("FAILED", failed.status());

        // Step 3: FAILED -> SUCCESS must be rejected
        assertThrows(
                IllegalStateException.class,
                () -> paymentService.updatePaymentStatus(
                        paymentId,
                        PaymentStatus.SUCCESS
                )
        );

        // Step 4: Verify the database still stores FAILED
        var savedPayment = paymentRepository
                .findById(paymentId)
                .orElseThrow();

        assertEquals(
                PaymentStatus.FAILED,
                savedPayment.getStatus()
        );
    }

}
