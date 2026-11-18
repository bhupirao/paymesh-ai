package com.paymesh.backend.security.accounts;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@SpringBootTest(properties = {
        "spring.flyway.default-schema=accounts_phase2_test",
        "spring.flyway.schemas=accounts_phase2_test",
        "spring.datasource.hikari.maximum-pool-size=2",
        "spring.jpa.properties.hibernate.default_schema=accounts_phase2_test"})
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class AccountProvisioningIntegrationTest {
    @Autowired InitialAdminBootstrap bootstrap;
    @Autowired AccountAdministration administration;
    @Autowired AccountCredentials credentials;
    @Autowired AccountAuthorization authorization;
    @Autowired AppUserRepository users;
    @Autowired RoleRepository roles;
    @Autowired UserRoleRepository assignments;
    @Autowired MerchantRepository merchants;
    @Autowired MerchantMembershipRepository memberships;
    @MockitoSpyBean SecurityAuditEventRepository events;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper json;
    @Autowired ApplicationContext context;
    private AuthenticatedAccount admin;
    private AccountView adminView;

    record TestAccount(AccountView account, char[] password) {}

    @BeforeAll
    void provisionOneRuntimeAdminInIsolatedSchema() {
        assertEquals(0, users.count(), "Normal application startup must never auto-provision an account");
        char[] password = UUID.randomUUID().toString().toCharArray();
        adminView = bootstrap.provision("phase2.admin", password);
        admin = credentials.authenticate(adminView.login(), password);
        Arrays.fill(password, '\0');
    }

    private String uniqueLogin() { return "staff." + UUID.randomUUID(); }
    private String uniqueMerchant() { return "merchant-" + UUID.randomUUID(); }
    private TestAccount merchant() {
        char[] password = UUID.randomUUID().toString().toCharArray();
        return new TestAccount(administration.createMerchantAccount(admin, uniqueLogin(), password), password);
    }
    private AuthenticatedAccount authenticate(TestAccount account) {
        return credentials.authenticate(account.account().login(), account.password());
    }
    private String verifiedMerchant() {
        String id = uniqueMerchant();
        administration.registerMerchant(admin, id);
        administration.verifyMerchantOwnership(admin, id, "REVIEW-" + UUID.randomUUID());
        return id;
    }

    @Test
    void createsMerchantRoleWithoutMembershipOrPublicProvisioningEndpoint() {
        TestAccount account = merchant();
        AuthenticatedAccount principal = authenticate(account);
        assertEquals(Set.of(AccountRole.MERCHANT), account.account().roles());
        assertTrue(authorization.hasRole(principal, AccountRole.MERCHANT));
        assertFalse(authorization.hasRole(principal, AccountRole.ADMIN));
        assertFalse(authorization.hasRole(null, AccountRole.ADMIN));
        assertTrue(authorization.isEnabled(account.account().userId()));
        assertFalse(authorization.isEnabled(UUID.randomUUID()));
        assertFalse(authorization.hasVerifiedMembership(principal, uniqueMerchant()));
        assertEquals(2, roles.count());
        var mappings = context.getBean("requestMappingHandlerMapping",
                org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping.class);
        assertTrue(mappings.getHandlerMethods().values().stream().noneMatch(handler ->
                handler.getBeanType().getPackageName().equals("com.paymesh.backend.security.accounts")));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM accounts_phase2_test.merchant_memberships WHERE user_id = ?",
                Integer.class, account.account().userId()));
    }

    @Test
    void duplicateNormalizedLoginNeverCreatesSecondAccountOrRole() {
        char[] password = UUID.randomUUID().toString().toCharArray();
        String login = uniqueLogin();
        AccountView created = administration.createMerchantAccount(admin, " " + login.toUpperCase(Locale.ROOT) + " ", password);
        long before = users.count();
        assertThrows(AccountOperationException.class, () -> administration.createMerchantAccount(admin, login, password));
        assertEquals(before, users.count());
        assertEquals(created.userId(), users.findByLoginNormalized(login).orElseThrow().getUserId());
        assertEquals(List.of("MERCHANT"), assignments.roles(created.userId()));
        assertEquals(1, events.findByEventTypeAndResourceId("ACCOUNT_CREATED", created.userId().toString()).size());
    }

    @Test
    void disabledAccountsAndOldPrincipalsRemainRejectedAfterReenable() {
        TestAccount account = merchant();
        AuthenticatedAccount initial = authenticate(account);
        administration.setAccountEnabled(admin, account.account().userId(), false);
        assertFalse(authorization.isEnabled(account.account().userId()));
        assertFalse(authorization.hasRole(initial, AccountRole.MERCHANT));
        assertThrows(AccountAccessDeniedException.class, () -> authenticate(account));
        assertThrows(AccountAccessDeniedException.class, () -> administration.registerMerchant(initial, uniqueMerchant()));
        administration.setAccountEnabled(admin, account.account().userId(), true);
        assertFalse(authorization.hasRole(initial, AccountRole.MERCHANT), "Reenable must not revive an old principal");
        assertTrue(authorization.hasRole(authenticate(account), AccountRole.MERCHANT));
        assertEquals(2, users.findById(account.account().userId()).orElseThrow().getAuthorizationVersion());
    }

    @Test
    void merchantAndAnonymousCallersCannotPerformAnyPrivilegedOperation() {
        TestAccount account = merchant();
        AuthenticatedAccount principal = authenticate(account);
        UUID id = account.account().userId();
        String merchant = uniqueMerchant();
        long usersBefore = users.count();
        assertThrows(AccountAccessDeniedException.class, () -> administration.createMerchantAccount(principal, uniqueLogin(), account.password()));
        assertThrows(AccountAccessDeniedException.class, () -> administration.createAdminAccount(principal, uniqueLogin(), account.password()));
        assertThrows(AccountAccessDeniedException.class, () -> administration.registerMerchant(principal, merchant));
        assertThrows(AccountAccessDeniedException.class, () -> administration.verifyMerchantOwnership(principal, merchant, "REVIEW-123"));
        assertThrows(AccountAccessDeniedException.class, () -> administration.assignVerifiedMembership(principal, id, merchant));
        assertThrows(AccountAccessDeniedException.class, () -> administration.revokeMembership(principal, id, merchant));
        assertThrows(AccountAccessDeniedException.class, () -> administration.setAccountEnabled(principal, adminView.userId(), false));
        assertThrows(AccountAccessDeniedException.class, () -> administration.createMerchantAccount(null, uniqueLogin(), account.password()));
        assertEquals(usersBefore, users.count());
        assertFalse(merchants.existsById(merchant));
        assertTrue(authorization.isEnabled(adminView.userId()));
        assertEquals(7, jdbc.queryForObject("SELECT count(*) FROM accounts_phase2_test.security_audit_events "
                + "WHERE actor_user_id = ? AND outcome = 'DENIED'", Integer.class, id));
    }

    @Test
    void membershipNeedsVerifiedMerchantAndEnabledMerchantRole() {
        TestAccount account = merchant();
        String merchant = uniqueMerchant();
        administration.registerMerchant(admin, merchant);
        assertThrows(AccountOperationException.class, () -> administration.assignVerifiedMembership(admin, account.account().userId(), merchant));
        assertFalse(merchants.findById(merchant).orElseThrow().isVerified());
        assertThrows(AccountOperationException.class, () -> administration.verifyMerchantOwnership(admin, merchant, " "));
        administration.verifyMerchantOwnership(admin, merchant, "REVIEW-" + UUID.randomUUID());
        Merchant verified = merchants.findById(merchant).orElseThrow();
        assertEquals(adminView.userId(), verified.getVerifiedBy());
        assertNotNull(verified.getVerifiedAt());
        assertTrue(verified.isActive());
        assertThrows(AccountOperationException.class, () -> administration.assignVerifiedMembership(admin, adminView.userId(), merchant));
        administration.setAccountEnabled(admin, account.account().userId(), false);
        assertThrows(AccountOperationException.class, () -> administration.assignVerifiedMembership(admin, account.account().userId(), merchant));
        administration.setAccountEnabled(admin, account.account().userId(), true);
        AuthenticatedAccount beforeGrant = authenticate(account);
        administration.assignVerifiedMembership(admin, account.account().userId(), merchant);
        assertFalse(authorization.hasVerifiedMembership(beforeGrant, merchant));
        assertTrue(authorization.hasVerifiedMembership(authenticate(account), merchant));
        assertFalse(authorization.hasVerifiedMembership(authenticate(account), merchant.toUpperCase(Locale.ROOT)));
        assertThrows(AccountOperationException.class, () -> administration.assignVerifiedMembership(admin, account.account().userId(), merchant));
    }

    @Test
    void revocationKeepsHistoryAndCanBeExplicitlyReassigned() {
        TestAccount account = merchant();
        String merchant = verifiedMerchant();
        administration.assignVerifiedMembership(admin, account.account().userId(), merchant);
        AuthenticatedAccount granted = authenticate(account);
        var key = new MerchantMembership.Id(account.account().userId(), merchant);
        var createdAt = memberships.findById(key).orElseThrow().getCreatedAt();
        administration.revokeMembership(admin, account.account().userId(), merchant);
        assertFalse(authorization.hasVerifiedMembership(granted, merchant));
        assertFalse(authorization.hasVerifiedMembership(authenticate(account), merchant));
        assertFalse(memberships.findById(key).orElseThrow().isActive());
        administration.assignVerifiedMembership(admin, account.account().userId(), merchant);
        assertTrue(authorization.hasVerifiedMembership(authenticate(account), merchant));
        assertEquals(createdAt, memberships.findById(key).orElseThrow().getCreatedAt());
        assertEquals(3, users.findById(account.account().userId()).orElseThrow().getAuthorizationVersion());
        assertEquals(1, events.findByEventTypeAndResourceId("MEMBERSHIP_REVOKED", account.account().userId().toString()).size());
    }

    @Test
    void initialAdminCannotBeRecreatedEvenWithDifferentLogin() {
        long before = users.count();
        assertThrows(AccountOperationException.class, () -> bootstrap.provision(uniqueLogin(), UUID.randomUUID().toString().toCharArray()));
        assertEquals(before, users.count());
        assertEquals(1, events.findByEventTypeAndResourceId("INITIAL_ADMIN_CREATED", adminView.userId().toString()).size());
    }

    @Test
    void offlineWorkflowCreatesVerifiedMerchantAccountAndMembershipAtomically() {
        String merchantId = uniqueMerchant();
        String login = uniqueLogin();
        char[] password = UUID.randomUUID().toString().toCharArray();
        AccountView account = administration.provisionMerchant(admin, merchantId,
                "REVIEW-" + UUID.randomUUID(), login, password);

        assertEquals(Set.of(AccountRole.MERCHANT), account.roles());
        assertTrue(merchants.findById(merchantId).orElseThrow().isVerified());
        var principal = credentials.authenticate(login, password);
        assertTrue(authorization.hasRole(principal, AccountRole.MERCHANT));
        assertTrue(authorization.hasVerifiedMembership(principal, merchantId));
        assertEquals(1, events.findByEventTypeAndResourceId("MERCHANT_REGISTERED", merchantId).size());
        assertEquals(1, events.findByEventTypeAndResourceId("MERCHANT_OWNERSHIP_VERIFIED", merchantId).size());
        assertEquals(1, events.findByEventTypeAndResourceId("ACCOUNT_CREATED", account.userId().toString()).size());
        assertEquals(1, events.findByEventTypeAndResourceId("MEMBERSHIP_ASSIGNED", account.userId().toString()).size());
    }

    @Test
    void workflowRejectsInvalidAdminAndNonAdminWithoutCreatingMerchant() {
        String merchantId = uniqueMerchant();
        char[] wrongPassword = UUID.randomUUID().toString().toCharArray();
        assertThrows(AccountAccessDeniedException.class, () -> credentials.authenticate(adminView.login(), wrongPassword));
        TestAccount merchantActor = merchant();
        AuthenticatedAccount merchantPrincipal = authenticate(merchantActor);
        assertThrows(AccountAccessDeniedException.class, () -> administration.provisionMerchant(merchantPrincipal,
                merchantId, "REVIEW-" + UUID.randomUUID(), uniqueLogin(), merchantActor.password()));
        assertFalse(merchants.existsById(merchantId));

        char[] secondaryAdminPassword = UUID.randomUUID().toString().toCharArray();
        AccountView secondaryAdmin = administration.createAdminAccount(admin, uniqueLogin(), secondaryAdminPassword);
        AuthenticatedAccount staleAdmin = credentials.authenticate(secondaryAdmin.login(), secondaryAdminPassword);
        administration.setAccountEnabled(admin, secondaryAdmin.userId(), false);
        assertThrows(AccountAccessDeniedException.class, () -> administration.provisionMerchant(staleAdmin,
                merchantId, "REVIEW-" + UUID.randomUUID(), uniqueLogin(), secondaryAdminPassword));
        assertFalse(merchants.existsById(merchantId), "Disabled or stale ADMIN credentials cannot provision");
    }

    @Test
    void workflowRejectsMissingReviewReferenceAndDuplicateMerchantWithoutWrites() {
        String merchantId = uniqueMerchant();
        String login = uniqueLogin();
        char[] password = UUID.randomUUID().toString().toCharArray();
        assertThrows(AccountOperationException.class, () -> administration.provisionMerchant(
                admin, merchantId, " ", login, password));
        assertFalse(merchants.existsById(merchantId), "Invalid evidence must roll back registration");
        assertFalse(users.existsByLoginNormalized(login));

        administration.registerMerchant(admin, merchantId);
        administration.verifyMerchantOwnership(admin, merchantId, "EXISTING-REVIEW-" + UUID.randomUUID());
        long usersBefore = users.count();
        assertThrows(AccountOperationException.class, () -> administration.provisionMerchant(
                admin, merchantId, "REVIEW-" + UUID.randomUUID(), login, password));
        assertEquals(usersBefore, users.count());
        assertTrue(merchants.findById(merchantId).orElseThrow().isVerified());
    }

    @Test
    void workflowRequiresExplicitAdminReviewToClaimHistoricalMerchantWithoutChangingPayments() {
        String merchantId = uniqueMerchant();
        UUID paymentId = UUID.randomUUID();
        jdbc.update("INSERT INTO accounts_phase2_test.payments(payment_id, merchant_id, customer_id, amount, currency, payment_method, status) "
                + "VALUES (?, ?, 'DEMO-HISTORICAL', 500, 'INR', 'UPI', 'SUCCESS')", paymentId, merchantId);
        Merchant historical = merchants.saveAndFlush(new Merchant(merchantId));
        assertFalse(historical.isVerified());
        var before = jdbc.queryForMap("SELECT * FROM accounts_phase2_test.payments WHERE payment_id = ?", paymentId);

        char[] password = UUID.randomUUID().toString().toCharArray();
        AccountView account = administration.provisionMerchant(admin, merchantId,
                "OWNERSHIP-TICKET-" + UUID.randomUUID(), uniqueLogin(), password);

        Merchant claimed = merchants.findById(merchantId).orElseThrow();
        assertTrue(claimed.isVerified());
        assertEquals(adminView.userId(), claimed.getVerifiedBy());
        assertTrue(authorization.hasVerifiedMembership(credentials.authenticate(account.login(), password), merchantId));
        assertEquals(before, jdbc.queryForMap("SELECT * FROM accounts_phase2_test.payments WHERE payment_id = ?", paymentId));
    }

    @Test
    void duplicateAccountFailureRollsBackMerchantAndVerification() {
        TestAccount existing = merchant();
        String merchantId = uniqueMerchant();
        long usersBefore = users.count();
        assertThrows(AccountOperationException.class, () -> administration.provisionMerchant(admin, merchantId,
                "REVIEW-" + UUID.randomUUID(), existing.account().login(), UUID.randomUUID().toString().toCharArray()));
        assertEquals(usersBefore, users.count());
        assertFalse(merchants.existsById(merchantId));
        assertEquals(1, users.findByLoginNormalized(existing.account().login()).stream().count());
        assertTrue(authorization.hasRole(authenticate(existing), AccountRole.MERCHANT));
    }

    @Test
    void auditContainsNoPasswordsOrHashesAndAuditFailureRollsBackCreation() throws Exception {
        TestAccount account = merchant();
        String hash = users.findById(account.account().userId()).orElseThrow().passwordHash();
        String serialized = json.writeValueAsString(events.findByResourceIdOrderByOccurredAtAsc(account.account().userId().toString()));
        assertFalse(serialized.contains(new String(account.password())));
        assertFalse(serialized.contains(hash));
        String userJson = json.writeValueAsString(users.findById(account.account().userId()).orElseThrow());
        assertFalse(userJson.contains(hash));
        assertFalse(userJson.contains("password"));
        assertFalse(json.writeValueAsString(account.account()).contains(hash));
        String failedLogin = uniqueLogin();
        long usersBefore = users.count();
        long rolesBefore = assignments.count();
        doThrow(new IllegalStateException("Simulated audit storage failure")).when(events)
                .saveAndFlush(argThat((SecurityAuditEvent e) -> e != null
                        && e.getEventType().equals("ACCOUNT_CREATED") && e.getOutcome().equals("SUCCESS")));
        assertThrows(IllegalStateException.class, () -> administration.createMerchantAccount(admin, failedLogin, account.password()));
        assertFalse(users.existsByLoginNormalized(failedLogin));
        assertEquals(usersBefore, users.count());
        assertEquals(rolesBefore, assignments.count());
    }

    @Test
    void unknownAndIncorrectCredentialsUseSameGenericFailure() {
        TestAccount account = merchant();
        char[] wrong = UUID.randomUUID().toString().toCharArray();
        var unknown = assertThrows(AccountAccessDeniedException.class, () -> credentials.authenticate(uniqueLogin(), wrong));
        var incorrect = assertThrows(AccountAccessDeniedException.class, () -> credentials.authenticate(account.account().login(), wrong));
        assertEquals(unknown.getMessage(), incorrect.getMessage());
        assertTrue(events.findByEventTypeAndResourceId("ACCOUNT_CREDENTIALS_REJECTED", null).size() >= 2);
    }

    @Test
    void historicalFinancialOwnershipIsPreservedUntilExplicitAdminVerification() {
        String merchant = " Historic-" + UUID.randomUUID() + " ";
        UUID payment = UUID.randomUUID();
        jdbc.update("INSERT INTO accounts_phase2_test.payments(payment_id, merchant_id, customer_id, amount, currency, payment_method, status) "
                + "VALUES (?, ?, 'HISTORICAL', 1000, 'INR', 'UPI', 'SUCCESS')", payment, merchant);
        jdbc.update("INSERT INTO accounts_phase2_test.refunds(refund_id, payment_id, amount, status, idempotency_key) "
                + "VALUES (?, ?, 200, 'SUCCESS', 'historical-refund')", UUID.randomUUID(), payment);
        jdbc.update("INSERT INTO accounts_phase2_test.idempotency_keys(id, merchant_id, idempotency_key, request_hash, payment_id) "
                + "VALUES (?, ?, 'historical-key', ?, ?)", UUID.randomUUID(), merchant, "a".repeat(64), payment);
        merchants.saveAndFlush(new Merchant(merchant)); // Represents an unclaimed V8 registry row.
        var paymentBefore = jdbc.queryForMap("SELECT * FROM accounts_phase2_test.payments WHERE payment_id = ?", payment);
        var refundBefore = jdbc.queryForList("SELECT * FROM accounts_phase2_test.refunds WHERE payment_id = ?", payment);
        var keyBefore = jdbc.queryForList("SELECT * FROM accounts_phase2_test.idempotency_keys WHERE payment_id = ?", payment);
        TestAccount account = merchant();
        AuthenticatedAccount principal = authenticate(account);
        assertFalse(merchants.findById(merchant).orElseThrow().isVerified());
        assertFalse(authorization.hasVerifiedMembership(principal, merchant));
        assertThrows(AccountAccessDeniedException.class, () -> administration.verifyMerchantOwnership(principal, merchant, "REVIEW-123"));
        assertThrows(AccountOperationException.class, () -> administration.assignVerifiedMembership(admin, account.account().userId(), merchant));
        administration.verifyMerchantOwnership(admin, merchant, "REVIEW-" + UUID.randomUUID());
        assertFalse(authorization.hasVerifiedMembership(principal, merchant), "Verification alone never grants membership");
        administration.assignVerifiedMembership(admin, account.account().userId(), merchant);
        assertTrue(authorization.hasVerifiedMembership(authenticate(account), merchant));
        assertFalse(authorization.hasVerifiedMembership(authenticate(account), merchant.strip()));
        assertEquals(paymentBefore, jdbc.queryForMap("SELECT * FROM accounts_phase2_test.payments WHERE payment_id = ?", payment));
        assertEquals(refundBefore, jdbc.queryForList("SELECT * FROM accounts_phase2_test.refunds WHERE payment_id = ?", payment));
        assertEquals(keyBefore, jdbc.queryForList("SELECT * FROM accounts_phase2_test.idempotency_keys WHERE payment_id = ?", payment));
    }

    @Test
    void concurrentDuplicateCreationProducesOneAccountAndOneSuccessAudit() throws Exception {
        String login = uniqueLogin();
        char[] password = UUID.randomUUID().toString().toCharArray();
        List<Callable<AccountView>> tasks = List.of(
                () -> administration.createMerchantAccount(admin, login, password),
                () -> administration.createMerchantAccount(admin, login, password));
        List<AccountView> results = concurrent(tasks);
        assertEquals(1, results.stream().filter(Objects::nonNull).count());
        AccountView created = results.stream().filter(Objects::nonNull).findFirst().orElseThrow();
        assertEquals(created.userId(), users.findByLoginNormalized(login).orElseThrow().getUserId());
        assertEquals(1, events.findByEventTypeAndResourceId("ACCOUNT_CREATED", created.userId().toString()).size());
    }

    @Test
    void adminCreationRequiresVerifiedAdminAndDisabledAdminCannotAdminister() {
        char[] password = UUID.randomUUID().toString().toCharArray();
        AccountView additional = administration.createAdminAccount(admin, uniqueLogin(), password);
        AuthenticatedAccount principal = credentials.authenticate(additional.login(), password);
        assertTrue(authorization.hasRole(principal, AccountRole.ADMIN));
        administration.setAccountEnabled(admin, additional.userId(), false);
        assertFalse(authorization.hasRole(principal, AccountRole.ADMIN));
        assertThrows(AccountAccessDeniedException.class, () -> administration.registerMerchant(principal, uniqueMerchant()));
    }

    @Test
    void concurrentDeniedOperationsReleaseTheirConnectionsBeforeAuditing() throws Exception {
        TestAccount account = merchant();
        AuthenticatedAccount principal = authenticate(account);
        List<Callable<Boolean>> tasks = List.of(
                () -> { assertThrows(AccountAccessDeniedException.class,
                        () -> administration.registerMerchant(principal, uniqueMerchant())); return true; },
                () -> { assertThrows(AccountAccessDeniedException.class,
                        () -> administration.registerMerchant(principal, uniqueMerchant())); return true; });
        assertEquals(List.of(true, true), concurrent(tasks));
        assertEquals(2, jdbc.queryForObject("SELECT count(*) FROM accounts_phase2_test.security_audit_events "
                + "WHERE actor_user_id = ? AND event_type = 'MERCHANT_REGISTERED' AND outcome = 'DENIED'",
                Integer.class, account.account().userId()));
    }

    private <T> List<T> concurrent(List<Callable<T>> tasks) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(tasks.size());
        CountDownLatch ready = new CountDownLatch(tasks.size());
        CountDownLatch start = new CountDownLatch(1);
        try {
            List<Future<T>> futures = new ArrayList<>();
            for (Callable<T> task : tasks) futures.add(pool.submit(() -> {
                ready.countDown();
                if (!start.await(10, TimeUnit.SECONDS)) throw new IllegalStateException("Start timed out");
                try { return task.call(); } catch (AccountOperationException expectedDuplicate) { return null; }
            }));
            assertTrue(ready.await(10, TimeUnit.SECONDS));
            start.countDown();
            List<T> results = new ArrayList<>();
            for (Future<T> future : futures) results.add(future.get(30, TimeUnit.SECONDS));
            return results;
        } finally {
            start.countDown(); pool.shutdownNow();
            assertTrue(pool.awaitTermination(10, TimeUnit.SECONDS));
        }
    }
}
