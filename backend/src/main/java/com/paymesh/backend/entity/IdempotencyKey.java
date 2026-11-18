
package com.paymesh.backend.entity;

import jakarta.persistence.*;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(
        name = "idempotency_keys",
        uniqueConstraints = {
                @UniqueConstraint(
                        name = "uq_idempotency_merchant_key",
                        columnNames = {"merchant_id", "idempotency_key"}
                )
        }
)
public class IdempotencyKey {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "merchant_id", nullable = false, length = 100)
    private String merchantId;

    @Column(name = "idempotency_key", nullable = false, length = 255)
    private String idempotencyKey;

    @Column(name = "request_hash", nullable = false, length = 64)
    private String requestHash;

    @Column(name = "payment_id", nullable = false)
    private UUID paymentId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected IdempotencyKey() {
        // Required by JPA
    }

    public IdempotencyKey(
            String merchantId,
            String idempotencyKey,
            String requestHash,
            UUID paymentId
    ) {
        this.id = UUID.randomUUID();
        this.merchantId = merchantId;
        this.idempotencyKey = idempotencyKey;
        this.requestHash = requestHash;
        this.paymentId = paymentId;
        this.createdAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public String getMerchantId() {
        return merchantId;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public String getRequestHash() {
        return requestHash;
    }

    public UUID getPaymentId() {
        return paymentId;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
