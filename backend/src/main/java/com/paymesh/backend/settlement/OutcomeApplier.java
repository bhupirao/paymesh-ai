package com.paymesh.backend.settlement;

import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.repository.GatewayTransactionRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Component;

/** Caller must hold the payment row lock for the entire transaction. */
@Component
public class OutcomeApplier {
    private final GatewayTransactionRepository transactions;
    private final SimulatedGatewayLedger ledger;

    public OutcomeApplier(GatewayTransactionRepository transactions, SimulatedGatewayLedger ledger) {
        this.transactions = transactions;
        this.ledger = ledger;
    }

    public Result apply(Payment payment, String gateway, UUID transactionId, Observation outcome, Instant occurredAt) {
        if (payment.getStatus() != PaymentStatus.PROCESSING) {
            return payment.getStatus() == PaymentStatus.CREATED
                    ? new Result("DEFERRED", "Payment has not started processing")
                    : new Result("IGNORED", "Terminal payment state is immutable: " + payment.getStatus());
        }
        var latest = transactions.findFirstByPaymentIdOrderByCreatedAtDesc(payment.getPaymentId());
        if (latest.isEmpty()) return new Result("DEFERRED", "Gateway attempt is not yet available");
        GatewayTransaction attempt = latest.get();
        if (!gateway.equals(gateway(payment, attempt))) return new Result("IGNORED", "Gateway does not match the payment attempt");
        UUID expected = attempt.getGatewayTransactionId();
        if (expected == null) {
            expected = ledger.lookup(payment.getPaymentId(), gateway).map(SimulatedGatewayLedger.Lookup::transactionId).orElse(null);
        }
        if (expected == null) return new Result("DEFERRED", "Awaiting a known gateway transaction identity");
        if (!expected.equals(transactionId)) return new Result("IGNORED", "Gateway transaction identity mismatch");
        if (occurredAt != null && occurredAt.isBefore(attempt.getCreatedAt().minusSeconds(1))) {
            return new Result("IGNORED", "Event predates the current gateway attempt");
        }
        if (!outcome.terminal()) return new Result("DEFERRED", "Gateway outcome is uncertain");
        if (terminal(attempt.getStatus()) && !attempt.getStatus().equals(outcome.name())) {
            return new Result("IGNORED", "Conflicting terminal gateway outcome requires investigation");
        }
        attempt.setGatewayName(gateway);
        attempt.updateResult(transactionId, outcome.name(), null, null);
        payment.updateStatus(PaymentStatus.valueOf(outcome.name()));
        return new Result("PROCESSED", "Payment and gateway attempt resolved");
    }

    public static boolean terminal(String status) {
        return "SUCCESS".equals(status) || "FAILED".equals(status);
    }

    public static String gateway(Payment payment, GatewayTransaction attempt) {
        if (!"MOCK_ROUTER".equals(attempt.getGatewayName())) return attempt.getGatewayName();
        if ("INR".equalsIgnoreCase(payment.getCurrency())) return "MOCK_RAZORPAY";
        if ("USD".equalsIgnoreCase(payment.getCurrency())) return "MOCK_STRIPE";
        return "MOCK_ROUTER";
    }

    public record Result(String status, String detail) {}
}
