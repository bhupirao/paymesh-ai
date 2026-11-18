package com.paymesh.backend.security.accounts;

import java.util.UUID;
import javax.sql.DataSource;
import org.springframework.transaction.annotation.*;

/** Registered only by the explicit offline context (or isolated tests), never component-scanned. */
class AdminPasswordRecoveryTransaction {
    private final AccountAdministrationLock lock;
    private final AppUserRepository users;
    private final UserRoleRepository roles;
    private final AccountPasswords passwords;
    private final AccountAudit audit;
    private final AdminRecoveryDatabaseGuard guard;
    private final DataSource source;
    AdminPasswordRecoveryTransaction(AccountAdministrationLock lock, AppUserRepository users, UserRoleRepository roles,
            AccountPasswords passwords, AccountAudit audit, AdminRecoveryDatabaseGuard guard, DataSource source) {
        this.lock=lock;this.users=users;this.roles=roles;this.passwords=passwords;this.audit=audit;this.guard=guard;this.source=source;
    }
    @Transactional(propagation=Propagation.REQUIRES_NEW,isolation=Isolation.READ_COMMITTED)
    public UUID reset(String login, char[] password, char[] confirmation) {
        InitialAdminProvisioner.requireMatchingPasswords(password,confirmation);
        guard.verify(source);
        lock.acquire();
        AppUser user=users.findByLoginNormalized(AccountCredentials.normalizeLogin(login))
                .orElseThrow(()->new AccountOperationException("Recovery account is unavailable"));
        if (!user.isEnabled() || !"ACTIVE".equals(user.getAccountStatus())
                || !roles.existsByIdUserIdAndIdRoleName(user.getUserId(),AccountRole.ADMIN.name())
                || roles.existsByIdUserIdAndIdRoleName(user.getUserId(),AccountRole.MERCHANT.name()))
            throw new AccountOperationException("Recovery requires an enabled ACTIVE ADMIN-only account");
        user.replacePasswordForOfflineRecovery(passwords.hash(password));
        users.saveAndFlush(user);
        audit.offlineAdminPasswordRecovery(user.getUserId());
        return user.getUserId();
    }
}
