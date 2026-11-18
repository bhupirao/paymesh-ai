package com.paymesh.backend.security.accounts;

import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;

/** Package-private bootstrap path: only the offline console entry point calls it in production. */
@Service
class InitialAdminBootstrapTransaction {
    private final AccountAdministrationLock lock;
    private final AppUserRepository users;
    private final RoleRepository roles;
    private final UserRoleRepository assignments;
    private final AccountPasswords passwords;
    private final AccountAudit audit;
    private final SecurityAuditEventRepository events;

    InitialAdminBootstrapTransaction(AccountAdministrationLock lock, AppUserRepository users, RoleRepository roles,
                          UserRoleRepository assignments, AccountPasswords passwords, AccountAudit audit,
                          SecurityAuditEventRepository events) {
        this.lock = lock; this.users = users; this.roles = roles; this.assignments = assignments;
        this.passwords = passwords; this.audit = audit;
        this.events = events;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED)
    AccountView provision(String login, char[] password) {
        lock.acquire();
        // Disabled ADMINs count too: bootstrap is not an account-recovery bypass.
        if (assignments.existsByIdRoleName(AccountRole.ADMIN.name()) || events.existsByEventType("INITIAL_ADMIN_CREATED")) {
            throw new AccountOperationException("Initial ADMIN already exists");
        }
        if (!roles.existsById(AccountRole.ADMIN.name())) throw new AccountOperationException("V8 role reference data is required");
        String normalized = AccountCredentials.normalizeLogin(login);
        if (users.existsByLoginNormalized(normalized)) throw new AccountOperationException("Login is already registered");
        AppUser user = users.saveAndFlush(new AppUser(normalized, passwords.hash(password)));
        assignments.saveAndFlush(new UserRole(user.getUserId(), AccountRole.ADMIN, null));
        audit.success(user, "INITIAL_ADMIN_CREATED", null, "ACCOUNT", user.getUserId().toString(),
                Map.of("source", "offline_bootstrap"));
        return new AccountView(user.getUserId(), user.getLoginNormalized(), true, 0, Set.of(AccountRole.ADMIN));
    }
}
