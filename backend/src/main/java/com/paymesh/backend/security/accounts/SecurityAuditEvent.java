package com.paymesh.backend.security.accounts;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity(name = "SecurityAuditEvent")
@Table(name = "security_audit_events")
public class SecurityAuditEvent {
    @Id @Column(name = "event_id") private UUID eventId;
    @Column(name = "actor_user_id") private UUID actorUserId;
    @Column(name = "actor_identifier", length = 255) private String actorIdentifier;
    @Column(name = "event_type", nullable = false, length = 100) private String eventType;
    @Column(name = "target_merchant_id", length = 100) private String targetMerchantId;
    @Column(name = "resource_type", length = 100) private String resourceType;
    @Column(name = "resource_id", length = 255) private String resourceId;
    @Column(nullable = false, length = 20) private String outcome;
    @Column(name = "correlation_id", length = 100) private String correlationId;
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb") private Map<String, Object> metadata;
    @Column(name = "occurred_at", nullable = false) private Instant occurredAt;
    protected SecurityAuditEvent() {}
    SecurityAuditEvent(UUID actor, String actorIdentifier, String operation, String merchantId,
                       String resourceType, String resourceId, String outcome, Map<String, Object> metadata) {
        eventId = UUID.randomUUID(); actorUserId = actor; this.actorIdentifier = actorIdentifier;
        eventType = operation; targetMerchantId = merchantId; this.resourceType = resourceType;
        this.resourceId = resourceId; this.outcome = outcome; this.metadata = Map.copyOf(metadata);
        occurredAt = Instant.now();
    }
    public UUID getEventId() { return eventId; }
    public UUID getActorUserId() { return actorUserId; }
    public String getActorIdentifier() { return actorIdentifier; }
    public String getEventType() { return eventType; }
    public String getTargetMerchantId() { return targetMerchantId; }
    public String getResourceType() { return resourceType; }
    public String getResourceId() { return resourceId; }
    public String getOutcome() { return outcome; }
    public String getCorrelationId() { return correlationId; }
    public Map<String, Object> getMetadata() { return Map.copyOf(metadata); }
    public Instant getOccurredAt() { return occurredAt; }
}
