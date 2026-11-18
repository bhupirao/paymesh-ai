package com.paymesh.backend.security.accounts;

import java.util.UUID;
import javax.sql.DataSource;
import org.springframework.transaction.annotation.*;

/** Registered only by the explicit offline context (or isolated tests), never component-scanned. */
class DisposableMerchantPasswordRecoveryTransaction {
    private final AccountAdministrationLock lock;
    private final AppUserRepository users;
    private final UserRoleRepository roles;
    private final AccountPasswords passwords;
    private final AccountAudit audit;
    private final AdminRecoveryDatabaseGuard guard;
    private final DataSource source;
    private final AuthStore store;
    static final String LOGIN="otp-merchant-demo@example.test";
    DisposableMerchantPasswordRecoveryTransaction(AccountAdministrationLock lock, AppUserRepository users, UserRoleRepository roles,
            AccountPasswords passwords, AccountAudit audit, AdminRecoveryDatabaseGuard guard, DataSource source, AuthStore store) {
        this.lock=lock;this.users=users;this.roles=roles;this.passwords=passwords;this.audit=audit;this.guard=guard;this.source=source;this.store=store;
    }
    @Transactional(propagation=Propagation.REQUIRES_NEW,isolation=Isolation.READ_COMMITTED)
    public UUID reset(String login, char[] password, char[] confirmation) {
        InitialAdminProvisioner.requireMatchingPasswords(password,confirmation);
        guard.verify(source);
        lock.acquire();
        if (!LOGIN.equals(AccountCredentials.normalizeLogin(login))) throw new AccountOperationException("Only the designated disposable account is supported");
        AppUser user=users.findByLoginNormalized(AccountCredentials.normalizeLogin(login))
                .orElseThrow(()->new AccountOperationException("Recovery account is unavailable"));
        if (!user.isEnabled() || !"PENDING_APPROVAL".equals(user.getAccountStatus())
                || !roles.roles(user.getUserId()).equals(java.util.List.of("MERCHANT")))
            throw new AccountOperationException("Recovery requires the enabled pending MERCHANT-only account");
        // Exactly one registered, unapproved ownership context; no lifecycle/financial writes.
        var rows=store.jdbc.queryForList("SELECT m.merchant_id FROM "+store.table("merchant_memberships")+" mm JOIN "+store.table("merchants")+" m USING(merchant_id) JOIN "+store.table("merchant_registrations")+" r ON r.user_id=mm.user_id AND r.merchant_id=mm.merchant_id JOIN "+store.table("merchant_administration")+" a ON a.merchant_id=m.merchant_id WHERE mm.user_id=? AND NOT mm.active AND NOT m.active AND NOT m.verified AND a.status='PENDING_APPROVAL' AND a.approved_at IS NULL AND r.email=?",user.getUserId(),LOGIN);
        if(rows.size()!=1 || store.jdbc.queryForObject("SELECT count(*) FROM "+store.table("merchant_memberships")+" WHERE user_id=?",Long.class,user.getUserId())!=1L)
            throw new AccountOperationException("Pending ownership context is inconsistent");
        if(store.jdbc.queryForObject("SELECT count(*) FROM "+store.table("demo_recovery_eligibility")+" WHERE enabled",Long.class)!=0L)
            throw new AccountOperationException("Demo recovery eligibility must remain disabled");
        // Fail closed if the required atomic revocation trigger is missing/disabled.
        if(store.jdbc.queryForObject("SELECT count(*) FROM pg_trigger WHERE tgrelid=?::regclass AND tgname='auth_account_security_change' AND tgenabled IN ('O','A') AND tgfoid=(?::regprocedure)",Long.class,store.table("app_users"),store.table("revoke_auth_state_for_account_change")+"()")!=1L)
            throw new AccountOperationException("Required session revocation trigger is unavailable");
        user.replacePasswordForOfflineRecovery(passwords.hash(password));
        users.saveAndFlush(user);
        audit.offlineDisposableMerchantPasswordRecovery(user.getUserId());
        return user.getUserId();
    }
}
