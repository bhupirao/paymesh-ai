package com.paymesh.backend.security.accounts;

import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SecurityAuditEventRepository extends JpaRepository<SecurityAuditEvent, UUID> {
    boolean existsByEventType(String eventType);
    List<SecurityAuditEvent> findByResourceIdOrderByOccurredAtAsc(String resourceId);
    List<SecurityAuditEvent> findByEventTypeAndResourceId(String eventType, String resourceId);
}
