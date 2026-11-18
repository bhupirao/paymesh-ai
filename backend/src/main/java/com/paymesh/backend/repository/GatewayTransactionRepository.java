
package com.paymesh.backend.repository;

import com.paymesh.backend.entity.GatewayTransaction;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import com.paymesh.backend.security.business.BusinessScopePredicate;

@Repository
public interface GatewayTransactionRepository
        extends JpaRepository<GatewayTransaction, UUID> {


    List<GatewayTransaction> findByPaymentIdOrderByCreatedAtDesc(
            UUID paymentId
    );


    Optional<GatewayTransaction>
    findFirstByPaymentIdOrderByCreatedAtDesc(
            UUID paymentId
    );


    List<GatewayTransaction> findByStatus(
            String status
    );


    long countByPaymentId(UUID paymentId);

    @Query("select t from GatewayTransaction t, Payment p where t.paymentId = p.paymentId "
            + "and t.id = :transactionId and " + BusinessScopePredicate.PAYMENT)
    Optional<GatewayTransaction> findAccessibleById(@Param("transactionId") UUID transactionId, @Param("callerId") UUID callerId,
            @Param("authorizationVersion") long version, @Param("admin") boolean admin, @Param("merchant") boolean merchant);
}
