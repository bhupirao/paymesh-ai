
package com.paymesh.backend.integration;

import com.paymesh.backend.dto.PaymentCreationResult;
import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.exception.InvalidPaymentStateException;
import com.paymesh.backend.gateway.GatewayResponse;
import com.paymesh.backend.gateway.GatewayStatus;
import com.paymesh.backend.gateway.PaymentGateway;
import com.paymesh.backend.service.PaymentOrchestrationService;
import com.paymesh.backend.service.internal.InternalPaymentService;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.math.BigDecimal;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@SpringBootTest
class PaymentOrchestrationConcurrencyIntegrationTest extends com.paymesh.backend.testing.BusinessJwtTestSupport {
    @Override protected java.util.Set<String> allowedMerchants() { return java.util.Set.of("MERCHANT_ORCHESTRATION_TEST"); }

    @Autowired
    private InternalPaymentService paymentService;

    @Autowired
    private PaymentOrchestrationService orchestrationService;

    @MockitoBean
    private PaymentGateway paymentGateway;

    @Test
    void shouldCallGatewayOnlyOnceForConcurrentRequests()
            throws Exception {

        PaymentRequest request = new PaymentRequest(
                "MERCHANT_ORCHESTRATION_TEST",
                new BigDecimal("500.00"),
                "INR",
                "CUSTOMER_ORCHESTRATION_TEST",
                "UPI"
        );

        PaymentCreationResult created =
                paymentService.createPayment(
                        request,
                        "ORCHESTRATION-" + UUID.randomUUID()
                );

        UUID paymentId = created.payment().paymentId();

        // NEW: Mock gateway name for transaction tracking.
        // Prevents null gateway_name database error.
        when(paymentGateway.getGatewayName())
                .thenReturn("MOCK_RAZORPAY");

        // Existing gateway processing mock.
        when(paymentGateway.processPayment(
                eq(paymentId),
                any(BigDecimal.class),
                eq("INR")
        )).thenAnswer(invocation -> {

            // Allow the competing request time
            // to attempt the same payment.
            Thread.sleep(200);

            return new GatewayResponse(
                    UUID.randomUUID(),
                    "MOCK_RAZORPAY",
                    GatewayStatus.SUCCESS,
                    null,
                    null
            );
        });

        ExecutorService executor =
                Executors.newFixedThreadPool(2);

        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);

        try {

            Callable<Boolean> task = () -> {

                ready.countDown();

                if (!start.await(10, TimeUnit.SECONDS)) {
                    throw new IllegalStateException(
                            "Start signal timed out"
                    );
                }

                try {

                    PaymentResponse response =
                            asCaller(() -> orchestrationService.processPayment(paymentId));

                    return "SUCCESS".equals(
                            response.status()
                    );

                } catch (InvalidPaymentStateException ex) {

                    return false;
                }
            };

            Future<Boolean> first = executor.submit(task);
            Future<Boolean> second = executor.submit(task);

            assertTrue(
                    ready.await(10, TimeUnit.SECONDS),
                    "Both threads should be ready"
            );

            start.countDown();

            boolean firstResult =
                    first.get(15, TimeUnit.SECONDS);

            boolean secondResult =
                    second.get(15, TimeUnit.SECONDS);

            int successfulRequests =
                    (firstResult ? 1 : 0)
                            + (secondResult ? 1 : 0);

            assertEquals(
                    1,
                    successfulRequests,
                    "Only one request should process the payment"
            );

            verify(paymentGateway, times(1))
                    .processPayment(
                            eq(paymentId),
                            any(BigDecimal.class),
                            eq("INR")
                    );

            PaymentResponse finalPayment =
                    paymentService.getPaymentById(paymentId);

            assertEquals(
                    "SUCCESS",
                    finalPayment.status()
            );

        } finally {

            start.countDown();
            executor.shutdownNow();
        }
    }
}
