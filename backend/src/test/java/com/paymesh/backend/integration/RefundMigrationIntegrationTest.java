package com.paymesh.backend.integration;

import java.util.Map;
import java.util.UUID;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@AutoConfigureMockMvc
class RefundMigrationIntegrationTest {
    @Autowired DataSource dataSource;

    @Test
    void v6PreservesLegacyRecordsAndAllowsMultipleKeyedRefunds() {
        // A separate schema in the isolated test database exercises a genuine V5 upgrade.
        // No clean, truncate, drop-schema or record deletion is performed.
        String schema = "refund_upgrade_" + UUID.randomUUID().toString().replace("-", "");
        Flyway.configure().dataSource(dataSource).schemas(schema).defaultSchema(schema)
                .target("5").load().migrate();
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        UUID legacyPayment = UUID.randomUUID();
        UUID legacyRefund = UUID.randomUUID();
        insertPayment(jdbc, schema, legacyPayment, "REFUNDED");
        jdbc.update("INSERT INTO " + schema + ".refunds (refund_id, payment_id, amount, status) VALUES (?, ?, 1000, 'SUCCESS')",
                legacyRefund, legacyPayment);
        Map<String, Object> paymentBefore = jdbc.queryForMap("SELECT * FROM " + schema + ".payments WHERE payment_id = ?", legacyPayment);
        Map<String, Object> refundBefore = jdbc.queryForMap("SELECT * FROM " + schema + ".refunds WHERE refund_id = ?", legacyRefund);

        Flyway.configure().dataSource(dataSource).schemas(schema).defaultSchema(schema).load().migrate();

        assertEquals(paymentBefore, jdbc.queryForMap("SELECT * FROM " + schema + ".payments WHERE payment_id = ?", legacyPayment));
        Map<String, Object> refundAfter = jdbc.queryForMap("SELECT * FROM " + schema + ".refunds WHERE refund_id = ?", legacyRefund);
        assertNull(refundAfter.remove("idempotency_key"));
        assertEquals(refundBefore, refundAfter);
        UUID partialPayment = UUID.randomUUID();
        insertPayment(jdbc, schema, partialPayment, "SUCCESS");
        String insert = "INSERT INTO " + schema + ".refunds (refund_id, payment_id, amount, status, idempotency_key) VALUES (?, ?, ?, 'SUCCESS', ?)";
        jdbc.update(insert, UUID.randomUUID(), partialPayment, 200, "part-1");
        jdbc.update(insert, UUID.randomUUID(), partialPayment, 300, "part-2");
        assertEquals(2, jdbc.queryForObject("SELECT count(*) FROM " + schema + ".refunds WHERE payment_id = ?", Integer.class, partialPayment));
        assertThrows(org.springframework.dao.DataIntegrityViolationException.class,
                () -> jdbc.update(insert, UUID.randomUUID(), partialPayment, 200, "part-1"));
        // The legacy refund remains present after new refunds are added.
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM " + schema + ".refunds WHERE refund_id = ?", Integer.class, legacyRefund));
    }

    private void insertPayment(JdbcTemplate jdbc, String schema, UUID id, String status) {
        jdbc.update("INSERT INTO " + schema + ".payments (payment_id, merchant_id, customer_id, amount, currency, payment_method, status) "
                + "VALUES (?, 'MIGRATION_TEST', 'CUSTOMER', 1000, 'INR', 'UPI', ?)", id, status);
    }
}
