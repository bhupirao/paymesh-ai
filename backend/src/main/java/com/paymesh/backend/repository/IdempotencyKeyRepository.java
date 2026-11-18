
package com.paymesh.backend.repository;

import com.paymesh.backend.entity.IdempotencyKey;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface IdempotencyKeyRepository
        extends JpaRepository<IdempotencyKey, UUID> {

    Optional<IdempotencyKey> findByMerchantIdAndIdempotencyKey(
            String merchantId,
            String idempotencyKey
    );
}
