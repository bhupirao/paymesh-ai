package com.paymesh.backend.security.accounts;

import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.SimpleTransactionStatus;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AccountAuthorizationTest {
    @Test
    void principalsRequirePasswordVerificationAndAreRecheckedAfterDisablement() {
        var users = mock(AppUserRepository.class);
        var passwords = mock(AccountPasswords.class);
        var audit = mock(AccountAudit.class);
        var roles = mock(UserRoleRepository.class);
        var merchants = mock(MerchantRepository.class);
        var memberships = mock(MerchantMembershipRepository.class);
        when(passwords.hash(any())).thenReturn("dummy-test-hash");
        AppUser user = new AppUser("verified.user", "test-hash");
        when(users.findByLoginNormalized("verified.user")).thenReturn(Optional.of(user));
        when(users.findById(user.getUserId())).thenReturn(Optional.of(user));
        when(passwords.matches(any(), eq("test-hash"))).thenReturn(true);
        when(roles.existsByIdUserIdAndIdRoleName(user.getUserId(), "MERCHANT")).thenReturn(true);
        var transactions = mock(PlatformTransactionManager.class);
        when(transactions.getTransaction(any())).thenAnswer(invocation -> new SimpleTransactionStatus());
        var credentials = new AccountCredentials(users, passwords, audit, transactions);
        var authorization = new AccountAuthorization(users, roles, merchants, memberships);
        var principal = credentials.authenticate("verified.user", UUID.randomUUID().toString().toCharArray());
        assertTrue(authorization.hasRole(principal, AccountRole.MERCHANT));
        assertFalse(authorization.hasRole(principal, AccountRole.ADMIN));
        assertThrows(AccountAccessDeniedException.class, () -> authorization.requireAdmin(principal));
        user.setEnabled(false);
        assertFalse(authorization.hasRole(principal, AccountRole.MERCHANT));
        assertThrows(AccountAccessDeniedException.class, () -> credentials.authenticate("verified.user", new char[12]));
        verify(audit).denied(user.getUserId(), "ACCOUNT_CREDENTIALS_REJECTED", null, "ACCOUNT", null);
        user.setEnabled(true);
        assertFalse(authorization.hasRole(principal, AccountRole.MERCHANT));
        assertFalse(authorization.hasVerifiedMembership(principal, "any-merchant"));
    }
}
