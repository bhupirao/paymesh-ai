package com.paymesh.backend.security.accounts;

import jakarta.persistence.*;
import java.io.Serializable;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

@Entity(name = "SecurityMerchantMembership")
@Table(name = "merchant_memberships")
public class MerchantMembership {
    @EmbeddedId private Id id;
    @Column(nullable = false) private boolean active;
    @Column(name = "granted_by") private UUID grantedBy;
    @Column(name = "created_at", nullable = false) private Instant createdAt;
    @Column(name = "updated_at", nullable = false) private Instant updatedAt;
    protected MerchantMembership() {}
    MerchantMembership(UUID userId, String merchantId, UUID actor) {
        id = new Id(userId, merchantId); createdAt = Instant.now(); activate(actor);
    }
    public Id getId() { return id; }
    public boolean isActive() { return active; }
    public UUID getGrantedBy() { return grantedBy; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    void activate(UUID actor) { active = true; grantedBy = actor; updatedAt = Instant.now(); }
    void revoke() { active = false; updatedAt = Instant.now(); }

    @Embeddable
    public static class Id implements Serializable {
        @Column(name = "user_id") private UUID userId;
        @Column(name = "merchant_id", length = 100) private String merchantId;
        protected Id() {}
        public Id(UUID userId, String merchantId) { this.userId = userId; this.merchantId = merchantId; }
        public UUID getUserId() { return userId; }
        public String getMerchantId() { return merchantId; }
        @Override public boolean equals(Object o) {
            return o instanceof Id other && Objects.equals(userId, other.userId) && Objects.equals(merchantId, other.merchantId);
        }
        @Override public int hashCode() { return Objects.hash(userId, merchantId); }
    }
}
