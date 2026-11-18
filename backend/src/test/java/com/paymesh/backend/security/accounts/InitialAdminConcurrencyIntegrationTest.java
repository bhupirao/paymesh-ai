package com.paymesh.backend.security.accounts;

import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties = {
        "spring.flyway.default-schema=initial_admin_phase2_test",
        "spring.flyway.schemas=initial_admin_phase2_test",
        "spring.jpa.properties.hibernate.default_schema=initial_admin_phase2_test"})
class InitialAdminConcurrencyIntegrationTest {
    @Autowired InitialAdminBootstrap bootstrap;
    @Autowired AccountAdministration administration;
    @Autowired AccountCredentials credentials;
    @Autowired AppUserRepository users;
    @Autowired UserRoleRepository assignments;
    @Autowired SecurityAuditEventRepository events;
    @Autowired JdbcTemplate jdbc;

    @Test
    void bootstrapAndLastAdminRulesHoldUnderConcurrentRequestsAndDisabledAccountsCannotRebootstrap() throws Exception {
        char[] firstPassword = UUID.randomUUID().toString().toCharArray();
        char[] secondPassword = UUID.randomUUID().toString().toCharArray();
        List<AccountView> attempts = concurrent(List.of(
                () -> bootstrap.provision("initial.first", firstPassword),
                () -> bootstrap.provision("initial.second", secondPassword)));
        assertEquals(1, attempts.stream().filter(Objects::nonNull).count());
        assertEquals(1, users.count());
        assertEquals(1, assignments.countEnabledAdmins());
        AccountView first = attempts.stream().filter(Objects::nonNull).findFirst().orElseThrow();
        char[] winnerPassword = first.login().equals("initial.first") ? firstPassword : secondPassword;
        var firstPrincipal = credentials.authenticate(first.login(), winnerPassword);
        assertThrows(AccountOperationException.class, () -> administration.setAccountEnabled(firstPrincipal, first.userId(), false));
        char[] otherPassword = UUID.randomUUID().toString().toCharArray();
        AccountView other = administration.createAdminAccount(firstPrincipal, "additional.admin", otherPassword);
        var otherPrincipal = credentials.authenticate(other.login(), otherPassword);
        List<Boolean> disabled = concurrent(List.of(
                () -> { administration.setAccountEnabled(firstPrincipal, other.userId(), false); return true; },
                () -> { administration.setAccountEnabled(otherPrincipal, first.userId(), false); return true; }));
        assertEquals(1, disabled.stream().filter(Objects::nonNull).count());
        assertEquals(1, assignments.countEnabledAdmins(), "Concurrent operations cannot disable both ADMINs");
        AppUser remaining = users.findAll().stream().filter(AppUser::isEnabled).findFirst().orElseThrow();
        char[] remainingPassword = remaining.getUserId().equals(first.userId()) ? winnerPassword : otherPassword;
        var principal = credentials.authenticate(remaining.getLoginNormalized(), remainingPassword);
        assertThrows(AccountOperationException.class, () -> administration.setAccountEnabled(principal, remaining.getUserId(), false));
        assertEquals(1, events.findByEventTypeAndResourceId("INITIAL_ADMIN_CREATED", first.userId().toString()).size());

        // Simulate an out-of-band administrative disable in this isolated fixture only.
        // Recovery must never fall back to creating a new initial administrator.
        jdbc.update("UPDATE initial_admin_phase2_test.app_users SET enabled = FALSE");
        assertThrows(AccountOperationException.class, () -> bootstrap.provision("recovery.disallowed", UUID.randomUUID().toString().toCharArray()));
        assertEquals(2, users.count());
        assertEquals(0, assignments.countEnabledAdmins());
        assertThrows(AccountAccessDeniedException.class, () -> credentials.authenticate(remaining.getLoginNormalized(), remainingPassword));
        Arrays.fill(firstPassword, '\0'); Arrays.fill(secondPassword, '\0'); Arrays.fill(otherPassword, '\0');
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
                try { return task.call(); }
                catch (AccountOperationException | AccountAccessDeniedException expectedDenial) { return null; }
            }));
            assertTrue(ready.await(10, TimeUnit.SECONDS)); start.countDown();
            List<T> results = new ArrayList<>();
            for (Future<T> future : futures) results.add(future.get(30, TimeUnit.SECONDS));
            return results;
        } finally {
            start.countDown(); pool.shutdownNow();
            assertTrue(pool.awaitTermination(10, TimeUnit.SECONDS));
        }
    }
}
