package com.paymesh.backend.security.accounts;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity(name = "SecurityMerchant")
@Table(name = "merchants")
public class Merchant {
    @Id @Column(name = "merchant_id", length = 100) private String merchantId;
    @Column(nullable = false) private boolean verified;
    @Column(nullable = false) private boolean active;
    @Column(name = "verified_by") private UUID verifiedBy;
    @Column(name = "verified_at") private Instant verifiedAt;
    @Column(name = "created_at", nullable = false) private Instant createdAt;
    @Column(name = "updated_at", nullable = false) private Instant updatedAt;
    protected Merchant() {}
    Merchant(String merchantId) { this.merchantId = merchantId; createdAt = Instant.now(); updatedAt = createdAt; }
    public String getMerchantId() { return merchantId; }
    public boolean isVerified() { return verified; }
    public boolean isActive() { return active; }
    public UUID getVerifiedBy() { return verifiedBy; }
    public Instant getVerifiedAt() { return verifiedAt; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    void administrationActive(boolean value) { active = value; updatedAt = Instant.now(); }
    void verify(UUID actor) {
        verified = true; active = true; verifiedBy = actor;
        verifiedAt = Instant.now(); updatedAt = verifiedAt;
    }
}
