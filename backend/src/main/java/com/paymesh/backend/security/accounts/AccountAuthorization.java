package com.paymesh.backend.security.accounts;

import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;

@Service
public class AccountAuthorization {
    private final AppUserRepository users;
    private final UserRoleRepository roles;
    private final MerchantRepository merchants;
    private final MerchantMembershipRepository memberships;

    public AccountAuthorization(AppUserRepository users, UserRoleRepository roles, MerchantRepository merchants,
                                MerchantMembershipRepository memberships) {
        this.users = users; this.roles = roles; this.merchants = merchants; this.memberships = memberships;
    }

    AppUser current(AuthenticatedAccount actor) {
        if (actor == null) throw new AccountAccessDeniedException();
        AppUser user = users.findById(actor.userId()).orElseThrow(AccountAccessDeniedException::new);
        if (!user.isEnabled() || user.getAuthorizationVersion() != actor.authorizationVersion()) {
            throw new AccountAccessDeniedException();
        }
        return user;
    }

    AppUser requireAdmin(AuthenticatedAccount actor) {
        AppUser user = current(actor);
        if (!"ACTIVE".equals(user.getAccountStatus()) || !roles.existsByIdUserIdAndIdRoleName(user.getUserId(), AccountRole.ADMIN.name())) throw new AccountAccessDeniedException();
        return user;
    }

    @Transactional(readOnly = true, propagation = Propagation.REQUIRES_NEW)
    public boolean hasRole(AuthenticatedAccount actor, AccountRole role) {
        try { return role != null && "ACTIVE".equals(current(actor).getAccountStatus()) && roles.existsByIdUserIdAndIdRoleName(current(actor).getUserId(), role.name()); }
        catch (AccountAccessDeniedException ex) { return false; }
    }

    @Transactional(readOnly = true, propagation = Propagation.REQUIRES_NEW)
    public boolean isEnabled(UUID userId) {
        return userId != null && users.findById(userId).map(AppUser::isEnabled).orElse(false);
    }

    @Transactional(readOnly = true, propagation = Propagation.REQUIRES_NEW)
    public boolean hasVerifiedMembership(AuthenticatedAccount actor, String merchantId) {
        if (merchantId == null || !hasRole(actor, AccountRole.MERCHANT)) return false;
        return merchants.findById(merchantId).filter(m -> m.isVerified() && m.isActive()).isPresent()
                && memberships.findById(new MerchantMembership.Id(actor.userId(), merchantId))
                .map(MerchantMembership::isActive).orElse(false);
    }
}
