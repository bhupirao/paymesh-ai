package com.paymesh.backend.security.accounts;

import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import java.util.UUID;
import java.util.function.Supplier;
import org.springframework.stereotype.Service;

/** Public internal facade; transaction proxies finish rollback before rejection/failure auditing. */
@Service
public class AccountAdministration {
    private final AccountAdministrationTransactions transactions;
    private final AccountAudit audit;
    public AccountAdministration(AccountAdministrationTransactions transactions, AccountAudit audit) {
        this.transactions = transactions; this.audit = audit;
    }

    public AccountView createMerchantAccount(AuthenticatedAccount actor, String login, char[] password) {
        return execute(actor, "ACCOUNT_CREATED", null, "ACCOUNT", null,
                () -> transactions.createMerchantAccount(actor, login, password));
    }
    public AccountView createAdminAccount(AuthenticatedAccount actor, String login, char[] password) {
        return execute(actor, "ACCOUNT_CREATED", null, "ACCOUNT", null,
                () -> transactions.createAdminAccount(actor, login, password));
    }
    public AccountView provisionMerchant(AuthenticatedAccount actor, String merchantId, String reviewReference,
                                         String login, char[] password) {
        return execute(actor, "MERCHANT_PROVISIONING", merchantId, "MERCHANT", null,
                () -> transactions.provisionMerchant(actor, merchantId, reviewReference, login, password));
    }
    public void registerMerchant(AuthenticatedAccount actor, String merchantId) {
        execute(actor, "MERCHANT_REGISTERED", merchantId, "MERCHANT", null,
                () -> { transactions.registerMerchant(actor, merchantId); return null; });
    }
    public void verifyMerchantOwnership(AuthenticatedAccount actor, String merchantId, String reference) {
        execute(actor, "MERCHANT_OWNERSHIP_VERIFIED", merchantId, "MERCHANT", null,
                () -> { transactions.verifyMerchantOwnership(actor, merchantId, reference); return null; });
    }
    public void assignVerifiedMembership(AuthenticatedAccount actor, UUID userId, String merchantId) {
        execute(actor, "MEMBERSHIP_ASSIGNED", merchantId, "ACCOUNT", resource(userId),
                () -> { transactions.assignVerifiedMembership(actor, userId, merchantId); return null; });
    }
    public void revokeMembership(AuthenticatedAccount actor, UUID userId, String merchantId) {
        execute(actor, "MEMBERSHIP_REVOKED", merchantId, "ACCOUNT", resource(userId),
                () -> { transactions.revokeMembership(actor, userId, merchantId); return null; });
    }
    public AccountView setAccountEnabled(AuthenticatedAccount actor, UUID userId, boolean enabled) {
        return execute(actor, enabled ? "ACCOUNT_ENABLED" : "ACCOUNT_DISABLED", null, "ACCOUNT", resource(userId),
                () -> transactions.setAccountEnabled(actor, userId, enabled));
    }

    private <T> T execute(AuthenticatedAccount actor, String operation, String merchantId, String type,
                          String resource, Supplier<T> action) {
        UUID actorId = actor == null ? null : actor.userId();
        String boundedMerchant = merchantId != null && merchantId.codePointCount(0, merchantId.length()) <= 100 ? merchantId : null;
        try { return action.get(); }
        catch (AccountAccessDeniedException | AccountOperationException ex) {
            audit.denied(actorId, operation, boundedMerchant, type, resource);
            throw ex;
        } catch (RuntimeException ex) {
            try { audit.failure(actorId, operation, boundedMerchant, type, resource, ex.getClass().getSimpleName()); }
            catch (RuntimeException auditFailure) { ex.addSuppressed(auditFailure); }
            throw ex;
        }
    }
    private String resource(UUID id) { return id == null ? null : id.toString(); }
}
