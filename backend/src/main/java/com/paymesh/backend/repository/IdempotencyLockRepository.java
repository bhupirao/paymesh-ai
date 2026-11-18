
package com.paymesh.backend.repository;

import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

public interface IdempotencyLockRepository
        extends Repository<com.paymesh.backend.entity.IdempotencyKey, java.util.UUID> {

    @Query(value = """
            SELECT pg_advisory_xact_lock(
                hashtextextended(
                    CONCAT(:merchantId, ':', :idempotencyKey),
                    0
                )
            )
            """, nativeQuery = true)
    void lock(
            @Param("merchantId") String merchantId,
            @Param("idempotencyKey") String idempotencyKey
    );
}
