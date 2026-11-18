package com.paymesh.backend.security.accounts;

import jakarta.persistence.EntityManager;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Component
class AccountAdministrationLock {
    private final EntityManager entityManager;
    AccountAdministrationLock(EntityManager entityManager) { this.entityManager = entityManager; }
    @Transactional(propagation = Propagation.MANDATORY)
    public void acquire() {
        // Low-volume privileged changes are serialized across application instances.
        // Prevents duplicate bootstrap, lost authorization versions and last-admin races.
        entityManager.createNativeQuery("SELECT pg_advisory_xact_lock(hashtextextended('paymesh:account-administration', 0))")
                .getSingleResult();
    }
}
