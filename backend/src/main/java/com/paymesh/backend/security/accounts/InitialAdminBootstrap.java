package com.paymesh.backend.security.accounts;

import org.springframework.stereotype.Service;

/** Package-private: production use is restricted to the explicit offline console entry point. */
@Service
class InitialAdminBootstrap {
    private final InitialAdminBootstrapTransaction transaction;
    private final AccountAudit audit;
    InitialAdminBootstrap(InitialAdminBootstrapTransaction transaction, AccountAudit audit) {
        this.transaction = transaction; this.audit = audit;
    }
    AccountView provision(String login, char[] password) {
        try { return transaction.provision(login, password); }
        catch (AccountOperationException | IllegalArgumentException ex) {
            audit.denied(null, "INITIAL_ADMIN_PROVISIONING_REJECTED", null, "ACCOUNT", null);
            throw ex;
        } catch (RuntimeException ex) {
            try { audit.failure(null, "INITIAL_ADMIN_PROVISIONING_FAILED", null, "ACCOUNT", null, ex.getClass().getSimpleName()); }
            catch (RuntimeException auditFailure) { ex.addSuppressed(auditFailure); }
            throw ex;
        }
    }
}
