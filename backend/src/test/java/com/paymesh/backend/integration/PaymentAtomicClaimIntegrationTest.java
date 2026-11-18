
package com.paymesh.backend.integration;

import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.dto.PaymentCreationResult;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.exception.InvalidPaymentStateException;
import com.paymesh.backend.service.internal.InternalPaymentService;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.math.BigDecimal;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class PaymentAtomicClaimIntegrationTest {

    @Autowired
    private InternalPaymentService paymentService;

    @Test
    void shouldAllowOnlyOneConcurrentPaymentClaim()
            throws Exception {

        // Create a unique payment for this test.
        PaymentRequest request = new PaymentRequest(
                "MERCHANT_CONCURRENCY_TEST",
                new BigDecimal("500.00"),
                "INR",
                "CUSTOMER_CONCURRENCY_TEST",
                "UPI"
        );

        PaymentCreationResult creationResult =
                paymentService.createPayment(
                        request,
                        "ATOMIC-CLAIM-" + UUID.randomUUID()
                );

        UUID paymentId =
                creationResult.payment().paymentId();

        ExecutorService executor =
                Executors.newFixedThreadPool(2);

        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);

        try {
            java.util.concurrent.Callable<Boolean> task = () -> {

                ready.countDown();

                if (!start.await(10, TimeUnit.SECONDS)) {
                    throw new IllegalStateException(
                            "Start signal timed out"
                    );
                }

                try {
                    paymentService.claimPaymentForProcessing(
                            paymentId
                    );

                    return true;

                } catch (InvalidPaymentStateException ex) {
                    return false;
                }
            };

            Future<Boolean> first = executor.submit(task);
            Future<Boolean> second = executor.submit(task);

            assertTrue(
                    ready.await(10, TimeUnit.SECONDS),
                    "Both threads must be ready"
            );

            start.countDown();

            boolean firstClaimed =
                    first.get(15, TimeUnit.SECONDS);

            boolean secondClaimed =
                    second.get(15, TimeUnit.SECONDS);

            int successfulClaims =
                    (firstClaimed ? 1 : 0)
                            + (secondClaimed ? 1 : 0);

            assertEquals(
                    1,
                    successfulClaims,
                    "Exactly one claim should succeed"
            );

            PaymentResponse payment =
                    paymentService.getPaymentById(paymentId);

            assertEquals(
                    PaymentStatus.PROCESSING.name(),
                    payment.status()
            );

        } finally {
            start.countDown();
            executor.shutdownNow();
        }
    }
}
