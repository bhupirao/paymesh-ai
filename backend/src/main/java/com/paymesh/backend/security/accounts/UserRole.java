package com.paymesh.backend.security.accounts;

import jakarta.persistence.*;
import java.io.Serializable;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

@Entity(name = "SecurityUserRole")
@Table(name = "user_roles")
public class UserRole {
    @EmbeddedId private Id id;
    @Column(name = "granted_by") private UUID grantedBy;
    @Column(name = "created_at", nullable = false) private Instant createdAt;
    protected UserRole() {}
    UserRole(UUID userId, AccountRole role, UUID actor) {
        id = new Id(userId, role.name()); grantedBy = actor; createdAt = Instant.now();
    }
    public Id getId() { return id; }
    public UUID getGrantedBy() { return grantedBy; }
    public Instant getCreatedAt() { return createdAt; }

    @Embeddable
    public static class Id implements Serializable {
        @Column(name = "user_id") private UUID userId;
        @Column(name = "role_name", length = 20) private String roleName;
        protected Id() {}
        public Id(UUID userId, String roleName) { this.userId = userId; this.roleName = roleName; }
        public UUID getUserId() { return userId; }
        public String getRoleName() { return roleName; }
        @Override public boolean equals(Object o) {
            return o instanceof Id other && Objects.equals(userId, other.userId) && Objects.equals(roleName, other.roleName);
        }
        @Override public int hashCode() { return Objects.hash(userId, roleName); }
    }
}
