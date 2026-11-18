package com.paymesh.backend.settlement;

import java.util.UUID;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class SettlementMigrationIntegrationTest {
    @Autowired DataSource dataSource;

    @Test
    void v7PreservesV6PaymentsRefundsAndGatewayAttempts() {
        String schema = "settlement_upgrade_" + UUID.randomUUID().toString().replace("-", "");
        Flyway.configure().dataSource(dataSource).schemas(schema).defaultSchema(schema).target("6").load().migrate();
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO " + schema + ".payments(payment_id, merchant_id, customer_id, amount, currency, payment_method, status) "
                + "VALUES (?, 'M', 'C', 1000, 'INR', 'UPI', 'REFUNDED')", id);
        jdbc.update("INSERT INTO " + schema + ".refunds(refund_id, payment_id, amount, status, idempotency_key) VALUES (?, ?, 1000, 'SUCCESS', 'legacy-full')", UUID.randomUUID(), id);
        jdbc.update("INSERT INTO " + schema + ".payment_gateway_transactions(id, payment_id, gateway_name, gateway_transaction_id, status) "
                + "VALUES (?, ?, 'MOCK_RAZORPAY', ?, 'SUCCESS')", UUID.randomUUID(), id, UUID.randomUUID());
        var payment = jdbc.queryForList("SELECT * FROM " + schema + ".payments");
        var refund = jdbc.queryForList("SELECT * FROM " + schema + ".refunds");
        var attempt = jdbc.queryForList("SELECT * FROM " + schema + ".payment_gateway_transactions");
        Flyway.configure().dataSource(dataSource).schemas(schema).defaultSchema(schema).load().migrate();
        assertEquals(payment, jdbc.queryForList("SELECT * FROM " + schema + ".payments"));
        assertEquals(refund, jdbc.queryForList("SELECT * FROM " + schema + ".refunds"));
        assertEquals(attempt, jdbc.queryForList("SELECT * FROM " + schema + ".payment_gateway_transactions"));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM " + schema + ".webhook_events", Integer.class));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM " + schema + ".reconciliation_attempts", Integer.class));
    }
}
