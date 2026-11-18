package com.paymesh.backend.settlement;

import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

@Configuration
@EnableScheduling
@ConditionalOnProperty(name = "paymesh.settlement.scheduling-enabled", havingValue = "true")
public class SettlementScheduler {
    private static final Logger log = LoggerFactory.getLogger(SettlementScheduler.class);
    private final WebhookInbox inbox;
    private final WebhookIngress ingress;
    private final JdbcTemplate jdbc;
    private final ReconciliationRunner runner;

    public SettlementScheduler(WebhookInbox inbox, WebhookIngress ingress, JdbcTemplate jdbc, ReconciliationRunner runner) {
        this.inbox = inbox; this.ingress = ingress; this.jdbc = jdbc; this.runner = runner;
    }

    @Scheduled(fixedDelayString = "${paymesh.settlement.poll-ms:30000}")
    public void tick() {
        for (UUID id : inbox.due()) {
            try { ingress.retry(id); }
            catch (RuntimeException ex) { log.warn("Webhook retry unavailable for {}", id); }
        }
        var ids = jdbc.query("""
                SELECT p.payment_id FROM payments p LEFT JOIN reconciliation_jobs j ON j.payment_id = p.payment_id
                WHERE p.status = 'PROCESSING' AND p.updated_at < CURRENT_TIMESTAMP - INTERVAL '60 seconds'
                AND (j.payment_id IS NULL OR (j.status IN ('PENDING','RETRY') AND j.attempts < 3
                     AND j.next_attempt_at <= CURRENT_TIMESTAMP))
                ORDER BY p.updated_at, p.payment_id LIMIT 100
                """, (rs, row) -> rs.getObject(1, UUID.class));
        for (UUID id : ids) {
            try { runner.run(id); }
            catch (RuntimeException ex) { log.warn("Reconciliation unavailable for {}", id); }
        }
    }
}
