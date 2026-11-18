package com.paymesh.backend.settlement;

import com.paymesh.backend.exception.IdempotencyConflictException;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class WebhookInbox {
    private final JdbcTemplate jdbc;

    public WebhookInbox(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public Event accept(String gateway, WebhookPayload payload, String raw) {
        jdbc.update("""
                INSERT INTO webhook_events(id, gateway, event_id, payment_id, payload, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (gateway, event_id) DO NOTHING
                """, UUID.randomUUID(), gateway, payload.eventId(), payload.paymentId(), raw,
                java.sql.Timestamp.from(payload.occurredAt()));
        Event event = jdbc.queryForObject("SELECT * FROM webhook_events WHERE gateway = ? AND event_id = ?",
                this::map, gateway, payload.eventId());
        if (!event.payload().equals(raw)) {
            throw new IdempotencyConflictException("Webhook event ID already used with a different payload");
        }
        return event;
    }

    public Event get(UUID id) {
        return jdbc.queryForObject("SELECT * FROM webhook_events WHERE id = ?", this::map, id);
    }

    public Event lock(UUID id) {
        return jdbc.queryForObject("SELECT * FROM webhook_events WHERE id = ? FOR UPDATE", this::map, id);
    }

    public List<UUID> due() {
        return jdbc.query("""
                SELECT id FROM webhook_events WHERE status IN ('RECEIVED','DEFERRED')
                AND next_attempt_at <= CURRENT_TIMESTAMP AND attempts < 3
                ORDER BY next_attempt_at, id LIMIT 100
                """, (rs, row) -> rs.getObject(1, UUID.class));
    }

    public void finish(Event event, String status, String detail) {
        int attempts = event.attempts() + 1;
        if ("DEFERRED".equals(status) && attempts >= 3) status = "FAILED";
        jdbc.update("""
                UPDATE webhook_events SET attempts = ?, status = ?, detail = ?, updated_at = CURRENT_TIMESTAMP,
                processed_at = CASE WHEN ? IN ('PROCESSED','IGNORED','FAILED') THEN CURRENT_TIMESTAMP ELSE NULL END,
                next_attempt_at = CURRENT_TIMESTAMP + (? * INTERVAL '1 second') WHERE id = ?
                """, attempts, status, detail, status, 30 * (1 << (attempts - 1)), event.id());
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void failure(UUID id) {
        Event event = lock(id);
        if (!event.pending() || event.attempts() >= 3) return;
        finish(event, "DEFERRED", "Processing failed; bounded retry scheduled");
    }

    private Event map(ResultSet rs, int row) throws SQLException {
        return new Event(rs.getObject("id", UUID.class), rs.getString("gateway"), rs.getString("event_id"),
                rs.getObject("payment_id", UUID.class), rs.getString("payload"), rs.getString("status"),
                rs.getInt("attempts"), rs.getTimestamp("next_attempt_at").toInstant(), rs.getString("detail"));
    }

    public record Event(UUID id, String gateway, String eventId, UUID paymentId, String payload,
                        String status, int attempts, Instant nextAttemptAt, String detail) {
        public boolean pending() { return status.equals("RECEIVED") || status.equals("DEFERRED"); }
        public Receipt receipt() { return new Receipt(id, eventId, status, attempts, detail); }
    }

    public record Receipt(UUID id, String eventId, String status, int attempts, String detail) {}
}
