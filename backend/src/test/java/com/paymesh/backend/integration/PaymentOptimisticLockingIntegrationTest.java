
package com.paymesh.backend.integration;

import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.service.internal.InternalPaymentService;
import jakarta.persistence.EntityManager;
import jakarta.persistence.EntityManagerFactory;
import jakarta.persistence.OptimisticLockException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import jakarta.persistence.RollbackException;
import java.math.BigDecimal;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class PaymentOptimisticLockingIntegrationTest {

    @Autowired
    private InternalPaymentService paymentService;

    @Autowired
    private EntityManagerFactory entityManagerFactory;

    @Test
    void shouldPreventLostUpdateWhenTwoTransactionsModifySamePayment() {

        PaymentRequest request = new PaymentRequest(
                "MERCHANT_LOCK_TEST",
                new BigDecimal("500.00"),
                "INR",
                "CUSTOMER_LOCK_TEST",
                "UPI"
        );

        UUID paymentId = paymentService.createPayment(
                request,
                "LOCK-" + UUID.randomUUID()
        ).payment().paymentId();

        // Move payment into PROCESSING first
        paymentService.updatePaymentStatus(
                paymentId,
                PaymentStatus.PROCESSING
        );

        EntityManager em1 = entityManagerFactory.createEntityManager();
        EntityManager em2 = entityManagerFactory.createEntityManager();

        try {
            // Both transactions read the same payment version
            em1.getTransaction().begin();
            em2.getTransaction().begin();

            Payment payment1 = em1.find(Payment.class, paymentId);
            Payment payment2 = em2.find(Payment.class, paymentId);

            assertNotNull(payment1);
            assertNotNull(payment2);
            assertEquals(PaymentStatus.PROCESSING, payment1.getStatus());
            assertEquals(PaymentStatus.PROCESSING, payment2.getStatus());

            // Transaction 1 marks SUCCESS and commits
            payment1.updateStatus(PaymentStatus.SUCCESS);
            em1.getTransaction().commit();

            // Transaction 2 attempts to overwrite SUCCESS with FAILED
            payment2.updateStatus(PaymentStatus.FAILED);

            // Version conflict must prevent the second commit
            RollbackException exception = assertThrows(
                    RollbackException.class,
                    () -> em2.getTransaction().commit()
            );

            assertInstanceOf(
                    OptimisticLockException.class,
                    exception.getCause()
            );

        } finally {
            if (em1.getTransaction().isActive()) {
                em1.getTransaction().rollback();
            }

            if (em2.getTransaction().isActive()) {
                em2.getTransaction().rollback();
            }

            em1.close();
            em2.close();
        }

        // Verify first transaction's result remains intact
        assertEquals(
                "SUCCESS",
                paymentService.getPaymentById(paymentId).status()
        );
    }
}
