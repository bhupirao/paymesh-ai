
package com.paymesh.backend.repository;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Repository;

@Repository
public class IdempotencyLockManager {

    @PersistenceContext
    private EntityManager entityManager;

    public void lock(String merchantId, String idempotencyKey) {

        String sql = """
                SELECT pg_advisory_xact_lock(
                    hashtextextended(
                        :lockKey,
                        0
                    )
                )
                """;

        String lockKey = merchantId.length() + ":" + merchantId
                + idempotencyKey.length() + ":" + idempotencyKey;

        entityManager
                .createNativeQuery(sql)
                .setParameter("lockKey", lockKey)
                .getSingleResult();
    }
}
