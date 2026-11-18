package com.paymesh.backend.security.accounts;

import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/** Read-only bridge: token issuance still requires a password-verified principal. */
@Service
@Transactional(readOnly = true, propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED)
public class AccountTokenStateService {
    private final AppUserRepository users;
    private final UserRoleRepository roles;
    private final AccountAuthorization authorization;

    public AccountTokenStateService(AppUserRepository users, UserRoleRepository roles, AccountAuthorization authorization) {
        this.users = users; this.roles = roles; this.authorization = authorization;
    }

    public TokenAccount forAuthenticated(AuthenticatedAccount principal) {
        return snapshot(authorization.current(principal));
    }

    public TokenAccount forToken(UUID userId) {
        AppUser user = users.findById(userId).filter(AppUser::isEnabled).orElseThrow(AccountAccessDeniedException::new);
        return snapshot(user);
    }

    private TokenAccount snapshot(AppUser user) {
        Set<AccountRole> current = roles.roles(user.getUserId()).stream().map(AccountRole::valueOf).collect(Collectors.toUnmodifiableSet());
        if (current.isEmpty()) throw new AccountAccessDeniedException();
        return new TokenAccount(user.getUserId(), user.getAuthorizationVersion(), current, user.getAccountStatus(),user.getLoginNormalized());
    }

    public record TokenAccount(UUID userId, long authorizationVersion, Set<AccountRole> roles, String accountStatus,String login) {
        public Set<AccountRole> financialRoles() { return "ACTIVE".equals(accountStatus) ? roles : Set.of(); }
    }
}
