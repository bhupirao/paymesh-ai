package com.paymesh.backend.settlement;

import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.exception.PaymentNotFoundException;
import com.paymesh.backend.repository.GatewayTransactionRepository;
import com.paymesh.backend.repository.PaymentRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ReconciliationService {
    private final PaymentRepository payments;
    private final GatewayTransactionRepository transactions;
    private final SimulatedStatusLookup lookup;
    private final OutcomeApplier applier;
    private final JdbcTemplate jdbc;

    public ReconciliationService(PaymentRepository payments, GatewayTransactionRepository transactions,
                                 SimulatedStatusLookup lookup, OutcomeApplier applier, JdbcTemplate jdbc) {
        this.payments = payments; this.transactions = transactions;
        this.lookup = lookup; this.applier = applier; this.jdbc = jdbc;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED)
    public Report reconcile(UUID paymentId) {
        Payment payment = payments.findByIdForSettlement(paymentId)
                .orElseThrow(() -> new PaymentNotFoundException(paymentId));
        if (payment.getStatus() == PaymentStatus.CREATED) {
            // Do not consume the retry budget before processing has even started.
            return new Report(paymentId, "NOT_ELIGIBLE", 0, Instant.now());
        }
        Report job = job(paymentId);
        if (!job.due()) return job;
        String before = payment.getStatus().name();
        if (payment.getStatus() != PaymentStatus.PROCESSING) {
            return finish(paymentId, job.attempts(), null, null, before, before, "SKIPPED", "Payment is not PROCESSING");
        }
        var attempt = transactions.findFirstByPaymentIdOrderByCreatedAtDesc(paymentId);
        if (attempt.isEmpty()) {
            return finish(paymentId, job.attempts(), null, "UNKNOWN", before, before, "RETRY", "No gateway attempt found");
        }
        String gateway = OutcomeApplier.gateway(payment, attempt.get());
        var observed = lookup.lookup(payment, attempt.get());
        var result = applier.apply(payment, gateway, observed.transactionId(), observed.outcome(), null);
        String status = switch (result.status()) {
            case "PROCESSED" -> "RESOLVED";
            case "IGNORED" -> "EXHAUSTED"; // Identity or final-outcome conflict needs investigation, not guessing.
            default -> "RETRY";
        };
        return finish(paymentId, job.attempts(), gateway, observed.outcome().name(), before,
                payment.getStatus().name(), status, result.detail());
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED)
    public Report failed(UUID paymentId) {
        Payment payment = payments.findByIdForSettlement(paymentId)
                .orElseThrow(() -> new PaymentNotFoundException(paymentId));
        if (payment.getStatus() == PaymentStatus.CREATED) {
            return new Report(paymentId, "NOT_ELIGIBLE", 0, Instant.now());
        }
        Report job = job(paymentId);
        if (!job.due()) return job;
        return finish(paymentId, job.attempts(), null, "UNKNOWN", payment.getStatus().name(),
                payment.getStatus().name(), "RETRY", "Lookup or processing failed; manual investigation needed if exhausted");
    }

    private Report job(UUID id) {
        // The payment lock serializes both job creation and all attempt counters across nodes.
        jdbc.update("INSERT INTO reconciliation_jobs(payment_id) VALUES (?) ON CONFLICT (payment_id) DO NOTHING", id);
        return jdbc.queryForObject("SELECT * FROM reconciliation_jobs WHERE payment_id = ?", (rs, row) ->
                new Report(id, rs.getString("status"), rs.getInt("attempts"), rs.getTimestamp("next_attempt_at").toInstant()), id);
    }

    private Report finish(UUID id, int priorAttempts, String gateway, String outcome, String before,
                          String after, String status, String detail) {
        int attempt = priorAttempts + 1;
        if (status.equals("RETRY") && attempt >= 3) status = "EXHAUSTED";
        jdbc.update("""
                INSERT INTO reconciliation_attempts(id, payment_id, attempt, gateway, outcome,
                    status_before, status_after, result, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, UUID.randomUUID(), id, attempt, gateway, outcome, before, after, status, detail);
        jdbc.update("""
                UPDATE reconciliation_jobs SET attempts = ?, status = ?, updated_at = CURRENT_TIMESTAMP,
                next_attempt_at = CURRENT_TIMESTAMP + (? * INTERVAL '1 second') WHERE payment_id = ?
                """, attempt, status, 30 * (1 << (attempt - 1)), id);
        return job(id);
    }

    public record Report(UUID paymentId, String status, int attempts, Instant nextAttemptAt) {
        public boolean due() {
            return (status.equals("PENDING") || status.equals("RETRY"))
                    && attempts < 3 && !nextAttemptAt.isAfter(Instant.now());
        }
    }
}
