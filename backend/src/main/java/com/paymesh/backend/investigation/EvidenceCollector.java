package com.paymesh.backend.investigation;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.paymesh.backend.security.business.BusinessAccess;
import java.sql.*;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;

/** Detached, privacy-minimized projection. No financial writes or remote I/O. */
@Service
public class EvidenceCollector {
    private final BusinessAccess access;
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    public EvidenceCollector(BusinessAccess access, JdbcTemplate jdbc, ObjectMapper json) {
        this.access = access; this.jdbc = jdbc; this.json = json;
    }
    public record Snapshot(ObjectNode evidence, Map<String, String> unavailable) {}

    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ, propagation = Propagation.REQUIRES_NEW, timeout = 5)
    public Snapshot collect(UUID id) {
        var payment = access.payment(access.actor(), id, false);
        ObjectNode e = json.createObjectNode();
        e.put("paymentId", id.toString());
        if (payment.getAmount().precision() > 14 || payment.getAmount().scale() > 2 || payment.getAmount().signum() <= 0)
            throw new InvestigationFailure(422, "Payment amount exceeds the investigation contract");
        e.put("amount", payment.getAmount().toPlainString());
        e.put("currency", payment.getCurrency()); e.put("paymentStatus", payment.getStatus().name());
        e.put("paymentMethod", payment.getPaymentMethod());
        Map<String, String> unavailable = new LinkedHashMap<>();
        evidence(e, unavailable, id, "gatewayTransactions", "payment_gateway_transactions",
                "id, payment_id, gateway_name, gateway_transaction_id, status, error_code, created_at, updated_at", rs -> {
            if (!Set.of("SUCCESS", "FAILED", "TIMEOUT").contains(rs.getString("status"))) return null;
            ObjectNode n = base(rs); n.put("gatewayName", rs.getString("gateway_name"));
            n.put("gatewayTransactionId", rs.getString("gateway_transaction_id")); n.put("status", rs.getString("status"));
            String code = rs.getString("error_code");
            n.put("errorCode", Set.of("UNSUPPORTED_CURRENCY", "INVALID_AMOUNT").contains(code == null ? "" : code) ? code : null);
            n.putNull("errorMessage"); time(n, "createdAt", rs, "created_at"); time(n, "updatedAt", rs, "updated_at"); return n;
        });
        evidence(e, unavailable, id, "refunds", "refunds", "refund_id, payment_id, amount, status, created_at", rs -> {
            if (!"SUCCESS".equals(rs.getString("status"))) return null;
            ObjectNode n = json.createObjectNode(); n.put("refundId", rs.getString("refund_id"));
            n.put("paymentId", rs.getString("payment_id")); n.put("amount", rs.getBigDecimal("amount").toPlainString());
            n.put("status", rs.getString("status")); time(n, "createdAt", rs, "created_at"); return n;
        });
        // PostgreSQL projects only the two permitted payload fields; raw payload never leaves the database.
        evidence(e, unavailable, id, "webhooks", "webhook_events",
                "id, payment_id, status, occurred_at, payload::jsonb ->> 'gatewayTransactionId' AS gateway_transaction_id, payload::jsonb ->> 'status' AS outcome", rs -> {
            String tx = rs.getString("gateway_transaction_id"), outcome = rs.getString("outcome");
            try { UUID.fromString(tx); } catch (RuntimeException ex) { return null; }
            if (!Set.of("SUCCESS", "FAILED", "TIMEOUT", "UNKNOWN").contains(outcome == null ? "" : outcome)) return null;
            ObjectNode n = base(rs); n.put("status", rs.getString("status")); n.put("gatewayTransactionId", tx);
            n.put("outcome", outcome); time(n, "occurredAt", rs, "occurred_at"); return n;
        });
        evidence(e, unavailable, id, "reconciliation", "reconciliation_attempts",
                "id, payment_id, outcome, status_before, status_after, result, created_at", rs -> {
            ObjectNode n = base(rs); n.put("outcome", rs.getString("outcome")); n.put("statusBefore", rs.getString("status_before"));
            n.put("statusAfter", rs.getString("status_after")); n.put("result", rs.getString("result"));
            time(n, "createdAt", rs, "created_at"); return n;
        });
        e.put("collectedAt", Instant.now().toString());
        EvidenceValidator.validate(e);
        return new Snapshot(e, Collections.unmodifiableMap(unavailable));
    }
    private ObjectNode base(ResultSet rs) throws SQLException {
        ObjectNode n = json.createObjectNode(); n.put("id", rs.getString("id")); n.put("paymentId", rs.getString("payment_id")); return n;
    }
    private void time(ObjectNode n, String field, ResultSet rs, String column) throws SQLException { n.put(field, rs.getTimestamp(column).toInstant().toString()); }
    private interface Projection { ObjectNode map(ResultSet rs) throws SQLException; }
    private void evidence(ObjectNode e, Map<String,String> unavailable, UUID id, String field, String table, String columns, Projection projection) {
        // Identifiers above are compile-time constants. Fetch one extra row to reject overflow, never truncate totals.
        List<ObjectNode> rows = jdbc.query("SELECT " + columns + " FROM " + table + " WHERE payment_id = ? ORDER BY " + (table.equals("refunds") ? "refund_id" : "id") + " LIMIT 101",
                (rs, row) -> projection.map(rs), id);
        if (rows.size() > 100) throw new InvestigationFailure(422, "Investigation evidence exceeds the 100-row collection limit");
        if (rows.contains(null)) {
            e.putNull(field); unavailable.put(field, "Stored evidence includes a value unsupported by the Python contract; entire collection withheld");
        } else { ArrayNode list = e.putArray(field); rows.forEach(list::add); }
    }
}
