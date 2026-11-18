package com.paymesh.backend.security;

import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class AuthenticationMigrationIntegrationTest {
    private static final List<String> LEGACY_TABLES = List.of(
            "payments", "idempotency_keys", "refunds", "payment_gateway_transactions",
            "simulated_gateway_outcomes", "webhook_events", "reconciliation_jobs", "reconciliation_attempts");
    private static final List<String> NEW_TABLES = List.of(
            "app_users", "roles", "user_roles", "merchants", "merchant_memberships", "security_audit_events");
    private static final List<String> EMPTY_AFTER_MIGRATION = List.of(
            "app_users", "user_roles", "merchant_memberships", "security_audit_events");

    @Autowired DataSource dataSource;
    private JdbcTemplate jdbc;
    private String schema;

    @BeforeEach
    void createV7SchemaInVerifiedIsolatedDatabase() {
        // The existing Spring initializer verifies isolation before any Flyway bean starts.
        // Every test gets a new schema; no cleanup SQL or deletion of legacy data is used.
        schema = "auth_upgrade_" + UUID.randomUUID().toString().replace("-", "");
        jdbc = new JdbcTemplate(dataSource);
        flyway("7").migrate();
    }

    private Flyway flyway(String target) {
        return Flyway.configure().dataSource(dataSource).schemas(schema).defaultSchema(schema)
                .target(target).load();
    }

    private void migrateV8() {
        assertEquals(1, flyway("8").migrate().migrationsExecuted);
    }

    private String table(String name) {
        // Schema names are generated UUIDs and table names are constants, never client input.
        return schema + "." + name;
    }

    private int count(String name) {
        return jdbc.queryForObject("SELECT count(*) FROM " + table(name), Integer.class);
    }

    private UUID payment(String merchant, String status) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO " + table("payments")
                + " (payment_id, merchant_id, customer_id, amount, currency, payment_method, status) "
                + "VALUES (?, ?, 'LEGACY_CUSTOMER', 1000.00, 'INR', 'UPI', ?)", id, merchant, status);
        return id;
    }

    private void idempotency(UUID paymentId, String merchant) {
        jdbc.update("INSERT INTO " + table("idempotency_keys")
                + " (id, merchant_id, idempotency_key, request_hash, payment_id) VALUES (?, ?, ?, ?, ?)",
                UUID.randomUUID(), merchant, "legacy-key-" + UUID.randomUUID(), "f".repeat(64), paymentId);
    }

    private void refund(UUID paymentId, int amount, String key) {
        jdbc.update("INSERT INTO " + table("refunds")
                + " (refund_id, payment_id, amount, status, idempotency_key) VALUES (?, ?, ?, 'SUCCESS', ?)",
                UUID.randomUUID(), paymentId, amount, key);
    }

    private Set<String> seedLegacyRecordsAndExactIdentifiers() {
        UUID full = payment("merchant-full", "REFUNDED");
        UUID partial = payment("merchant-partial", "SUCCESS");
        UUID uncertain = payment("merchant-uncertain", "PROCESSING");
        idempotency(full, "merchant-full");
        idempotency(partial, "merchant-partial");
        // Older schemas do not require idempotency.merchant_id to equal its payment's
        // merchant. Preserve such records and backfill both values without "repair".
        idempotency(partial, "idempotency-only");
        idempotency(partial, " ID_ONLY ");
        refund(full, 400, "legacy-full-1");
        refund(full, 600, "legacy-full-2");
        refund(partial, 200, "legacy-partial");
        UUID gatewayTransaction = UUID.randomUUID();
        jdbc.update("INSERT INTO " + table("payment_gateway_transactions")
                + " (id, payment_id, gateway_name, gateway_transaction_id, status) VALUES (?, ?, 'MOCK_RAZORPAY', ?, 'UNKNOWN')",
                UUID.randomUUID(), uncertain, gatewayTransaction);
        jdbc.update("INSERT INTO " + table("simulated_gateway_outcomes")
                + " (gateway, payment_id, gateway_transaction_id, outcome) VALUES ('MOCK_RAZORPAY', ?, ?, 'TIMEOUT')",
                uncertain, gatewayTransaction);
        jdbc.update("INSERT INTO " + table("webhook_events")
                + " (id, gateway, event_id, payment_id, payload, occurred_at, status, attempts, detail) "
                + "VALUES (?, 'MOCK_RAZORPAY', 'legacy-event', ?, ?, CURRENT_TIMESTAMP, 'DEFERRED', 1, 'Awaiting outcome')",
                UUID.randomUUID(), uncertain, "{\"legacy\":true,\"amount\":1000.00}");
        jdbc.update("INSERT INTO " + table("reconciliation_jobs")
                + " (payment_id, attempts, status) VALUES (?, 1, 'RETRY')", uncertain);
        jdbc.update("INSERT INTO " + table("reconciliation_attempts")
                + " (id, payment_id, attempt, gateway, outcome, status_before, status_after, result, detail) "
                + "VALUES (?, ?, 1, 'MOCK_RAZORPAY', 'UNKNOWN', 'PROCESSING', 'PROCESSING', 'RETRY', 'Legacy lookup')",
                UUID.randomUUID(), uncertain);

        Set<String> identifiers = new HashSet<>(Set.of(
                "merchant-full", "merchant-partial", "merchant-uncertain", "idempotency-only", " ID_ONLY "));
        // V1/V2 allow these strings. V8 must not discard, trim, case-fold, or normalize them.
        List<String> variants = List.of("Merchant", "merchant", " Merchant", "Merchant ", "", " ",
                "x".repeat(100), "café", "cafe\u0301", "मर्चेंट");
        for (String merchant : variants) {
            UUID id = payment(merchant, "CREATED");
            idempotency(id, merchant);
            identifiers.add(merchant);
        }
        return identifiers;
    }

    private Map<String, List<Map<String, Object>>> legacyRows() {
        Map<String, List<Map<String, Object>>> result = new LinkedHashMap<>();
        for (String name : LEGACY_TABLES) {
            result.put(name, jdbc.queryForList("SELECT * FROM " + table(name) + " ORDER BY 1"));
        }
        return result;
    }

    private List<Map<String, Object>> legacyColumns() {
        return jdbc.queryForList("""
                SELECT table_name, column_name, ordinal_position, data_type, udt_name,
                       character_maximum_length, numeric_precision, numeric_scale,
                       is_nullable, column_default, collation_name
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name IN
                    ('payments','idempotency_keys','refunds','payment_gateway_transactions',
                     'simulated_gateway_outcomes','webhook_events','reconciliation_jobs','reconciliation_attempts')
                ORDER BY table_name, ordinal_position
                """, schema);
    }

    private List<Map<String, Object>> appliedV1ToV7() {
        return jdbc.queryForList("SELECT * FROM " + table("flyway_schema_history")
                + " WHERE version IN ('1','2','3','4','5','6','7') ORDER BY installed_rank");
    }

    private void assertNoSeededAccountsOrClaims() {
        for (String name : EMPTY_AFTER_MIGRATION) assertEquals(0, count(name), name);
        assertEquals(List.of("ADMIN", "MERCHANT"), jdbc.queryForList(
                "SELECT role_name FROM " + table("roles") + " ORDER BY role_name", String.class));
    }

    @Test
    void v8PreservesEveryLegacyRowColumnAndAppliedMigration() {
        seedLegacyRecordsAndExactIdentifiers();
        Map<String, List<Map<String, Object>>> before = legacyRows();
        for (String name : LEGACY_TABLES) assertFalse(before.get(name).isEmpty(), name + " fixture missing");
        var columnsBefore = legacyColumns();
        var migrationsBefore = appliedV1ToV7();
        assertEquals(7, migrationsBefore.size());

        migrateV8();

        assertEquals(before, legacyRows(), "All original values, timestamps, versions and hashes must survive V8");
        assertEquals(columnsBefore, legacyColumns(), "V8 must not alter legacy columns");
        assertEquals(migrationsBefore, appliedV1ToV7(), "Applied V1–V7 checksums/history must remain unchanged");
        assertNoSeededAccountsOrClaims();
    }

    @Test
    void backfillsExactUnionWithoutVerificationClaimsOrReplayChanges() {
        Set<String> expected = seedLegacyRecordsAndExactIdentifiers();
        migrateV8();
        Set<String> actual = new HashSet<>(jdbc.queryForList(
                "SELECT merchant_id FROM " + table("merchants"), String.class));
        assertEquals(expected, actual);
        assertEquals(expected.size(), count("merchants"));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM " + table("merchants")
                + " WHERE verified OR active OR verified_by IS NOT NULL OR verified_at IS NOT NULL", Integer.class));
        assertEquals("C", jdbc.queryForObject("SELECT collation_name FROM information_schema.columns "
                + "WHERE table_schema = ? AND table_name = 'merchants' AND column_name = 'merchant_id'", String.class, schema));
        assertNoSeededAccountsOrClaims();
        var registryBefore = jdbc.queryForList("SELECT * FROM " + table("merchants") + " ORDER BY merchant_id");
        assertEquals(0, flyway("8").migrate().migrationsExecuted, "Flyway replay must not seed duplicates or change timestamps");
        assertEquals(registryBefore, jdbc.queryForList("SELECT * FROM " + table("merchants") + " ORDER BY merchant_id"));
    }

    @Test
    void emptyV7DatabaseCreatesOnlySchemaAndRoleReferenceData() {
        migrateV8();
        for (String name : NEW_TABLES) {
            assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM information_schema.tables "
                    + "WHERE table_schema = ? AND table_name = ?", Integer.class, schema, name));
        }
        assertEquals(0, count("merchants"));
        assertNoSeededAccountsOrClaims();
        assertEquals(255, jdbc.queryForObject("SELECT character_maximum_length FROM information_schema.columns "
                + "WHERE table_schema = ? AND table_name = 'app_users' AND column_name = 'password_hash'", Integer.class, schema));
        for (String name : LEGACY_TABLES) assertEquals(0, count(name));
    }

    private UUID user(String login) {
        UUID id = UUID.randomUUID();
        // Synthetic storage fixture only; no real credential, encoder or authentication exists in this phase.
        jdbc.update("INSERT INTO " + table("app_users") + " (user_id, login_normalized, password_hash) VALUES (?, ?, ?)",
                id, login, "synthetic-test-hash-not-a-credential");
        return id;
    }

    @Test
    void accountAndRoleConstraintsRejectInvalidOrDuplicateAssignments() {
        migrateV8();
        UUID user = user("merchant.user");
        Map<String, Object> account = jdbc.queryForMap("SELECT * FROM " + table("app_users") + " WHERE user_id = ?", user);
        assertEquals(false, account.get("enabled"));
        assertEquals(0L, account.get("authorization_version"));
        assertNotNull(account.get("created_at"));
        assertNotNull(account.get("updated_at"));
        assertThrows(DataIntegrityViolationException.class, () -> user("merchant.user"));
        assertThrows(DataIntegrityViolationException.class, () -> user("Merchant.User"));
        assertThrows(DataIntegrityViolationException.class, () -> user(" merchant.user "));
        assertThrows(DataIntegrityViolationException.class, () -> user(""));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("UPDATE " + table("app_users")
                + " SET authorization_version = -1 WHERE user_id = ?", user));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("UPDATE " + table("app_users")
                + " SET password_hash = ' ' WHERE user_id = ?", user));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("INSERT INTO " + table("roles")
                + " (role_name) VALUES ('SUPERUSER')"));
        String assignment = "INSERT INTO " + table("user_roles") + " (user_id, role_name) VALUES (?, ?)";
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(assignment, UUID.randomUUID(), "MERCHANT"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(assignment, user, "UNKNOWN"));
        jdbc.update(assignment, user, "MERCHANT");
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(assignment, user, "MERCHANT"));
        assertEquals(1, count("user_roles"));
    }

    @Test
    void membershipsRequireExistingIdentitiesAndCannotDuplicateOrAutoVerifyMerchants() {
        migrateV8();
        UUID user = user("member");
        jdbc.update("INSERT INTO " + table("merchants") + " (merchant_id) VALUES ('verified-later')");
        String membership = "INSERT INTO " + table("merchant_memberships") + " (user_id, merchant_id) VALUES (?, ?)";
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(membership, user, "missing"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(membership, UUID.randomUUID(), "verified-later"));
        jdbc.update(membership, user, "verified-later");
        assertEquals(false, jdbc.queryForObject("SELECT active FROM " + table("merchant_memberships"), Boolean.class));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(membership, user, "verified-later"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("UPDATE " + table("merchants") + " SET active = TRUE"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("UPDATE " + table("merchants") + " SET verified = TRUE"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("UPDATE " + table("merchant_memberships")
                + " SET granted_by = ?", UUID.randomUUID()));
        assertEquals(false, jdbc.queryForObject("SELECT verified FROM " + table("merchants"), Boolean.class));
        assertEquals(0, count("user_roles"), "Membership does not grant any application role");
    }

    @Test
    void auditSurvivesAccountDisablementAndPreventsActorDeletion() {
        migrateV8();
        UUID actor = user("audit.actor");
        UUID event = UUID.randomUUID();
        jdbc.update("UPDATE " + table("app_users") + " SET enabled = TRUE WHERE user_id = ?", actor);
        String insert = "INSERT INTO " + table("security_audit_events")
                + " (event_id, actor_user_id, event_type, target_merchant_id, outcome) VALUES (?, ?, ?, ?, ?)";
        jdbc.update(insert, event, actor, "ACCESS_DENIED", "unknown-merchant", "DENIED");
        var before = jdbc.queryForMap("SELECT * FROM " + table("security_audit_events") + " WHERE event_id = ?", event);
        assertNotNull(before.get("occurred_at"));
        jdbc.update("UPDATE " + table("app_users")
                + " SET enabled = FALSE, authorization_version = authorization_version + 1 WHERE user_id = ?", actor);
        assertEquals(before, jdbc.queryForMap("SELECT * FROM " + table("security_audit_events") + " WHERE event_id = ?", event));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("DELETE FROM " + table("app_users")
                + " WHERE user_id = ?", actor));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(insert, UUID.randomUUID(), UUID.randomUUID(),
                "ACCESS_DENIED", "unknown-merchant", "DENIED"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(insert, UUID.randomUUID(), actor,
                "ACCESS_DENIED", "unknown-merchant", "INVALID"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("UPDATE " + table("security_audit_events")
                + " SET metadata = '[]'::jsonb WHERE event_id = ?", event));
        // Unknown actors/resources are legitimate audit subjects, not FK violations.
        jdbc.update(insert, UUID.randomUUID(), null, "LOGIN_FAILURE", null, "FAILURE");
        assertEquals(2, count("security_audit_events"));
        assertEquals(1, count("app_users"));
    }

    @Test
    void migrationDoesNotAddForeignKeysOrProvisioningRequirementsToLegacyWrites() {
        migrateV8();
        UUID payment = payment("post-v8-legacy-writer", "CREATED");
        idempotency(payment, "post-v8-legacy-writer");
        assertEquals(1, count("payments"));
        assertEquals(1, count("idempotency_keys"));
        assertEquals(0, count("merchants"), "V8 is a one-time backfill, not an ownership/provisioning trigger");
        assertNoSeededAccountsOrClaims();
    }
}
