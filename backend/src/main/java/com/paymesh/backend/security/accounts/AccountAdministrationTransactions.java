package com.paymesh.backend.security.accounts;

import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED)
class AccountAdministrationTransactions {
    private final AppUserRepository users;
    private final RoleRepository roles;
    private final UserRoleRepository assignments;
    private final MerchantRepository merchants;
    private final MerchantMembershipRepository memberships;
    private final AccountPasswords passwords;
    private final AccountAuthorization authorization;
    private final AccountAdministrationLock lock;
    private final AccountAudit audit;

    AccountAdministrationTransactions(AppUserRepository users, RoleRepository roles, UserRoleRepository assignments,
                                 MerchantRepository merchants, MerchantMembershipRepository memberships,
                                 AccountPasswords passwords, AccountAuthorization authorization,
                                 AccountAdministrationLock lock, AccountAudit audit) {
        this.users = users; this.roles = roles; this.assignments = assignments; this.merchants = merchants;
        this.memberships = memberships; this.passwords = passwords; this.authorization = authorization;
        this.lock = lock; this.audit = audit;
    }

    public AccountView createMerchantAccount(AuthenticatedAccount actor, String login, char[] password) {
        return createAccount(actor, login, password, AccountRole.MERCHANT);
    }

    public AccountView createAdminAccount(AuthenticatedAccount actor, String login, char[] password) {
        return createAccount(actor, login, password, AccountRole.ADMIN);
    }

    /**
     * Atomically performs the same audited account/merchant operations used by
     * the individual administrative methods. A retry after a rolled-back
     * attempt starts cleanly; a retry after a committed attempt is rejected by
     * the existing merchant/login uniqueness checks and never overwrites data.
     */
    public AccountView provisionMerchant(AuthenticatedAccount principal, String merchantId,
                                         String evidenceReference, String login, char[] password) {
        AppUser actor = authorize(principal);
        validateMerchantId(merchantId);
        Merchant existing = merchants.findById(merchantId).orElse(null);
        if (existing == null) {
            registerMerchant(actor, merchantId);
        } else if (existing.isVerified() || existing.isActive()) {
            // Existing verified/active ownership is never replaced. An
            // unverified inactive row is the intentionally unclaimed V8
            // historical-merchant case and requires the explicit review below.
            throw new AccountOperationException("Merchant already has ownership or active state");
        }
        verifyMerchantOwnership(actor, merchantId, evidenceReference);
        AccountView account = createAccount(actor, login, password, AccountRole.MERCHANT);
        assignVerifiedMembership(actor, account.userId(), merchantId);
        return account;
    }

    private AccountView createAccount(AuthenticatedAccount principal, String login, char[] password, AccountRole role) {
        AppUser actor = authorize(principal);
        return createAccount(actor, login, password, role);
    }

    private AccountView createAccount(AppUser actor, String login, char[] password, AccountRole role) {
        String operation = "ACCOUNT_CREATED";
        String normalized;
        String hash;
        try {
            normalized = AccountCredentials.normalizeLogin(login);
            if (users.existsByLoginNormalized(normalized)) throw new IllegalArgumentException("Login is already registered");
            hash = passwords.hash(password);
        } catch (IllegalArgumentException ex) {
            throw new AccountOperationException("Account input is invalid or login is already registered");
        }
        if (!roles.existsById(role.name())) throw new AccountOperationException("Required role reference is missing");
        AppUser user = users.saveAndFlush(new AppUser(normalized, hash));
        assignments.saveAndFlush(new UserRole(user.getUserId(), role, actor.getUserId()));
        audit.success(actor, operation, null, "ACCOUNT", user.getUserId().toString(), Map.of("role", role.name()));
        return view(user);
    }

    public void registerMerchant(AuthenticatedAccount principal, String merchantId) {
        AppUser actor = authorize(principal);
        registerMerchant(actor, merchantId);
    }

    private void registerMerchant(AppUser actor, String merchantId) {
        String operation = "MERCHANT_REGISTERED";
        validateMerchantId(merchantId);
        if (merchants.existsById(merchantId)) throw new AccountOperationException("Merchant already registered");
        merchants.saveAndFlush(new Merchant(merchantId));
        audit.success(actor, operation, merchantId, "MERCHANT", merchantId, Map.of());
    }

    /** Administrative attestation after an external business review, not automatic ownership discovery. */
    public void verifyMerchantOwnership(AuthenticatedAccount principal, String merchantId, String evidenceReference) {
        AppUser actor = authorize(principal);
        verifyMerchantOwnership(actor, merchantId, evidenceReference);
    }

    private void verifyMerchantOwnership(AppUser actor, String merchantId, String evidenceReference) {
        String operation = "MERCHANT_OWNERSHIP_VERIFIED";
        validateMerchantId(merchantId);
        if (evidenceReference == null || !evidenceReference.matches("[A-Za-z0-9][A-Za-z0-9._/\\-]{2,99}")) {
            throw new AccountOperationException("A review reference of 3 to 100 supported characters is required");
        }
        Merchant merchant = merchants.findById(merchantId).orElseThrow(() ->
                new AccountOperationException("Merchant is not registered"));
        if (merchant.isVerified()) throw new AccountOperationException("Merchant is already verified");
        merchant.verify(actor.getUserId());
        audit.success(actor, operation, merchantId, "MERCHANT", merchantId, Map.of("reviewReference", evidenceReference));
    }

    public void assignVerifiedMembership(AuthenticatedAccount principal, UUID userId, String merchantId) {
        AppUser actor = authorize(principal);
        assignVerifiedMembership(actor, userId, merchantId);
    }

    private void assignVerifiedMembership(AppUser actor, UUID userId, String merchantId) {
        String operation = "MEMBERSHIP_ASSIGNED";
        String resource = userId == null ? null : userId.toString();
        validateMerchantId(merchantId);
        AppUser target = target(userId);
        if (!target.isEnabled() || !assignments.existsByIdUserIdAndIdRoleName(userId, AccountRole.MERCHANT.name())) {
            throw new AccountOperationException("An enabled MERCHANT account is required");
        }
        Merchant merchant = merchants.findById(merchantId).orElseThrow(() ->
                new AccountOperationException("Merchant is not registered"));
        if (!merchant.isVerified() || !merchant.isActive()) {
            throw new AccountOperationException("Merchant ownership must be verified first");
        }
        var id = new MerchantMembership.Id(userId, merchantId);
        var existing = memberships.findById(id);
        if (existing.isPresent() && existing.get().isActive()) {
            throw new AccountOperationException("Membership is already active");
        }
        if (existing.isPresent()) existing.get().activate(actor.getUserId());
        else memberships.save(new MerchantMembership(userId, merchantId, actor.getUserId()));
        target.invalidateAuthorization();
        audit.success(actor, operation, merchantId, "ACCOUNT", resource, Map.of());
    }

    public void revokeMembership(AuthenticatedAccount principal, UUID userId, String merchantId) {
        String operation = "MEMBERSHIP_REVOKED";
        String resource = userId == null ? null : userId.toString();
        AppUser actor = authorize(principal);
        validateMerchantId(merchantId);
        AppUser target = target(userId);
        MerchantMembership membership = memberships.findById(new MerchantMembership.Id(userId, merchantId))
                .orElseThrow(() -> new AccountOperationException("Membership does not exist"));
        if (membership.isActive()) { membership.revoke(); target.invalidateAuthorization(); }
        audit.success(actor, operation, merchantId, "ACCOUNT", resource, Map.of());
    }

    public AccountView setAccountEnabled(AuthenticatedAccount principal, UUID userId, boolean enabled) {
        String operation = enabled ? "ACCOUNT_ENABLED" : "ACCOUNT_DISABLED";
        String resource = userId == null ? null : userId.toString();
        AppUser actor = authorize(principal);
        AppUser target = target(userId);
        if (!enabled && target.isEnabled() && assignments.existsByIdUserIdAndIdRoleName(userId, AccountRole.ADMIN.name())
                && assignments.countEnabledAdmins() <= 1) {
            throw new AccountOperationException("Cannot disable the last enabled ADMIN");
        }
        target.setEnabled(enabled);
        audit.success(actor, operation, null, "ACCOUNT", resource, Map.of("enabled", enabled));
        return view(target);
    }

    private AppUser authorize(AuthenticatedAccount principal) {
        lock.acquire();
        return authorization.requireAdmin(principal);
    }

    private AppUser target(UUID userId) {
        if (userId == null) throw new AccountOperationException("Account is required");
        return users.findById(userId).orElseThrow(() ->
                new AccountOperationException("Account does not exist"));
    }

    private void validateMerchantId(String merchantId) {
        if (merchantId == null || merchantId.isBlank() || merchantId.codePointCount(0, merchantId.length()) > 100) {
            throw new AccountOperationException("A nonblank merchant identifier of at most 100 characters is required");
        }
    }

    private AccountView view(AppUser user) {
        Set<AccountRole> assigned = assignments.roles(user.getUserId()).stream().map(AccountRole::valueOf).collect(Collectors.toUnmodifiableSet());
        return new AccountView(user.getUserId(), user.getLoginNormalized(), user.isEnabled(), user.getAuthorizationVersion(), assigned);
    }
}
