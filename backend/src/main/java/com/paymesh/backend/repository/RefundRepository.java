package com.paymesh.backend.repository;
import com.paymesh.backend.entity.Refund;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
public interface RefundRepository extends JpaRepository<Refund,UUID> {
    Optional<Refund> findByPaymentIdAndIdempotencyKey(UUID paymentId, String idempotencyKey);

    List<Refund> findAllByPaymentIdOrderByCreatedAtAscRefundIdAsc(UUID paymentId);

    Optional<Refund> findFirstByPaymentIdOrderByCreatedAtDescRefundIdDesc(UUID paymentId);

    @Query("select coalesce(sum(r.amount), 0) from Refund r "
            + "where r.paymentId = :paymentId and r.status = 'SUCCESS'")
    BigDecimal totalSuccessfulAmount(@Param("paymentId") UUID paymentId);
}
