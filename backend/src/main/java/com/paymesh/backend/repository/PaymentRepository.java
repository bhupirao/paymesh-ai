
package com.paymesh.backend.repository;

import com.paymesh.backend.entity.Payment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.Lock;
import jakarta.persistence.LockModeType;
import java.util.Optional;
import java.util.UUID;
import java.time.Instant;
import com.paymesh.backend.security.business.BusinessScopePredicate;

public interface PaymentRepository
        extends JpaRepository<Payment, UUID> {

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query(value = """
        UPDATE payments
        SET status = 'PROCESSING',
            updated_at = CURRENT_TIMESTAMP,
            version = version + 1
        WHERE payment_id = :paymentId
          AND status = 'CREATED'
        """, nativeQuery = true)
    int claimPaymentForProcessing(
            @Param("paymentId") UUID paymentId
    );

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from Payment p where p.paymentId = :paymentId")
    Optional<Payment> findByIdForRefund(@Param("paymentId") UUID paymentId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from Payment p where p.paymentId = :paymentId")
    Optional<Payment> findByIdForSettlement(@Param("paymentId") UUID paymentId);

    @Query("select p from Payment p where p.paymentId = :paymentId and " + BusinessScopePredicate.PAYMENT)
    Optional<Payment> findAccessibleById(@Param("paymentId") UUID paymentId, @Param("callerId") UUID callerId,
            @Param("authorizationVersion") long version, @Param("admin") boolean admin, @Param("merchant") boolean merchant);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from Payment p where p.paymentId = :paymentId and " + BusinessScopePredicate.PAYMENT)
    Optional<Payment> findAccessibleForUpdate(@Param("paymentId") UUID paymentId, @Param("callerId") UUID callerId,
            @Param("authorizationVersion") long version, @Param("admin") boolean admin, @Param("merchant") boolean merchant);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Payment p set p.status = com.paymesh.backend.enums.PaymentStatus.PROCESSING, "
            + "p.updatedAt = :updatedAt, p.version = p.version + 1 where p.paymentId = :paymentId "
            + "and p.status = com.paymesh.backend.enums.PaymentStatus.CREATED and " + BusinessScopePredicate.PAYMENT)
    int claimAccessiblePayment(@Param("paymentId") UUID paymentId, @Param("callerId") UUID callerId,
            @Param("authorizationVersion") long version, @Param("admin") boolean admin,
            @Param("merchant") boolean merchant, @Param("updatedAt") Instant updatedAt);
}
