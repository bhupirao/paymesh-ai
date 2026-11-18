package com.paymesh.backend.security.accounts;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity(name = "SecurityUser")
@Table(name = "app_users")
public class AppUser {
    @Id @Column(name = "user_id") private UUID userId;
    @Column(name = "login_normalized", nullable = false, length = 255) private String loginNormalized;
    @JsonIgnore
    @Column(name = "password_hash", nullable = false, length = 255) private String passwordHash;
    @Column(nullable = false) private boolean enabled;
    @Column(name = "authorization_version", nullable = false) private long authorizationVersion;
    @Column(name = "created_at", nullable = false) private Instant createdAt;
    @Column(name = "updated_at", nullable = false) private Instant updatedAt;

    @Column(name = "account_status", nullable = false) private String accountStatus = "ACTIVE";
    public String getAccountStatus() { return accountStatus; }
    void administrationStatus(String status) { accountStatus = status; invalidateAuthorization(); }
    void pendingApproval() { accountStatus = "PENDING_APPROVAL"; }

    protected AppUser() {}
    AppUser(String login, String hash) {
        userId = UUID.randomUUID(); loginNormalized = login; passwordHash = hash; enabled = true;
        createdAt = Instant.now(); updatedAt = createdAt;
    }
    public UUID getUserId() { return userId; }
    public String getLoginNormalized() { return loginNormalized; }
    @JsonIgnore
    String passwordHash() { return passwordHash; }
    public boolean isEnabled() { return enabled; }
    public long getAuthorizationVersion() { return authorizationVersion; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    void setEnabled(boolean value) {
        if (enabled != value) { enabled = value; invalidateAuthorization(); }
    }
    void replacePasswordForOfflineRecovery(String hash) {
        if (authorizationVersion == Long.MAX_VALUE) throw new IllegalStateException("Authorization version exhausted");
        passwordHash = hash; invalidateAuthorization();
    }
    void invalidateAuthorization() { authorizationVersion++; updatedAt = Instant.now(); }
}
