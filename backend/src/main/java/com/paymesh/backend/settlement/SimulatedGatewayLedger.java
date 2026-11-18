package com.paymesh.backend.settlement;

import com.paymesh.backend.gateway.GatewayResponse;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class SimulatedGatewayLedger {
    private final JdbcTemplate jdbc;

    public SimulatedGatewayLedger(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // A simulated provider commit is independent of the application's completion transaction.
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void record(UUID paymentId, GatewayResponse response) {
        if (response.gatewayTransactionId() == null) return;
        jdbc.update("""
                INSERT INTO simulated_gateway_outcomes(gateway, payment_id, gateway_transaction_id, outcome)
                VALUES (?, ?, ?, ?) ON CONFLICT (gateway, payment_id) DO NOTHING
                """, response.gatewayName(), paymentId, response.gatewayTransactionId(), response.status().name());
    }

    public Optional<Lookup> lookup(UUID paymentId, String gateway) {
        return jdbc.query("""
                SELECT gateway_transaction_id, outcome FROM simulated_gateway_outcomes
                WHERE payment_id = ? AND gateway = ?
                """, (rs, row) -> new Lookup(rs.getObject(1, UUID.class), Observation.valueOf(rs.getString(2))),
                paymentId, gateway).stream().findFirst();
    }

    public record Lookup(UUID transactionId, Observation outcome) {}
}
