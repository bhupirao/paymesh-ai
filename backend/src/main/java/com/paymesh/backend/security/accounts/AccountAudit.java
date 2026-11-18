package com.paymesh.backend.security.accounts;

import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AccountAudit {
    private final SecurityAuditEventRepository events;
    private final AppUserRepository users;
    public AccountAudit(SecurityAuditEventRepository events, AppUserRepository users) { this.events = events; this.users = users; }

    // Successful mutations and their audit rows commit or roll back together.
    @Transactional(propagation = Propagation.MANDATORY)
    public void success(AppUser actor, String operation, String merchantId, String resourceType,
                        String resourceId, Map<String, Object> metadata) {
        events.saveAndFlush(new SecurityAuditEvent(actor.getUserId(), actor.getLoginNormalized(), operation,
                merchantId, resourceType, resourceId, "SUCCESS", metadata));
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void checkoutAccepted(String merchant, UUID attempt) {
        events.saveAndFlush(new SecurityAuditEvent(null,null,"CHECKOUT_ACCEPTED",merchant,"CHECKOUT_ATTEMPT",attempt.toString(),"SUCCESS",Map.of("source","public_link_capability")));
    }

    // Offline operator has database/OS custody, not an authenticated ADMIN identity.
    @Transactional(propagation = Propagation.MANDATORY)
    public void offlineAdminPasswordRecovery(UUID target) {
        events.saveAndFlush(new SecurityAuditEvent(null, null, "ADMIN_PASSWORD_RECOVERED", null,
                "ACCOUNT", target.toString(), "SUCCESS", Map.of("source", "offline_operator_recovery")));
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void offlineDisposableMerchantPasswordRecovery(UUID target) {
        events.saveAndFlush(new SecurityAuditEvent(null, null, "DISPOSABLE_MERCHANT_PASSWORD_RECOVERED", null,
                "ACCOUNT", target.toString(), "SUCCESS", Map.of("source", "offline_operator_recovery")));
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void localDemoPasswordRecovery(UUID target) {
        events.saveAndFlush(new SecurityAuditEvent(null,null,"LOCAL_DEMO_PASSWORD_RESET",null,"ACCOUNT",target.toString(),"SUCCESS",Map.of("source","insecure_local_demo_on_screen_otp")));
    }

    // Denials must survive rollback of the rejected privileged operation.
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void denied(UUID actor, String operation, String merchantId, String resourceType, String resourceId) {
        AppUser known = actor == null ? null : users.findById(actor).orElse(null);
        events.saveAndFlush(new SecurityAuditEvent(known == null ? null : known.getUserId(),
                known == null ? null : known.getLoginNormalized(), operation, merchantId,
                resourceType, resourceId, "DENIED", Map.of()));
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void failure(UUID actor, String operation, String merchantId, String resourceType, String resourceId, String failureType) {
        AppUser known = actor == null ? null : users.findById(actor).orElse(null);
        events.saveAndFlush(new SecurityAuditEvent(known == null ? null : known.getUserId(),
                known == null ? null : known.getLoginNormalized(), operation, merchantId,
                resourceType, resourceId, "FAILURE", Map.of("failureType", failureType)));
    }
}
