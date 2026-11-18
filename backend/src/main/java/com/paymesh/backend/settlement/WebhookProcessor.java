package com.paymesh.backend.settlement;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.paymesh.backend.repository.PaymentRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WebhookProcessor {
    private final WebhookInbox inbox;
    private final PaymentRepository payments;
    private final OutcomeApplier applier;
    private final ObjectMapper json;

    public WebhookProcessor(WebhookInbox inbox, PaymentRepository payments, OutcomeApplier applier, ObjectMapper json) {
        this.inbox = inbox; this.payments = payments; this.applier = applier; this.json = json;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED)
    public void process(UUID id) {
        var snapshot = inbox.get(id);
        // Payment first, then inbox: consistent ordering with reconciliation and refunds.
        var payment = payments.findByIdForSettlement(snapshot.paymentId());
        var event = inbox.lock(id);
        if (!event.pending() || event.attempts() >= 3 || event.nextAttemptAt().isAfter(Instant.now())) return;
        if (payment.isEmpty()) {
            inbox.finish(event, "DEFERRED", "Payment is not yet available");
            return;
        }
        try {
            WebhookPayload payload = json.readValue(event.payload(), WebhookPayload.class);
            var result = applier.apply(payment.get(), event.gateway(), payload.gatewayTransactionId(),
                    payload.status(), payload.occurredAt());
            inbox.finish(event, result.status(), result.detail());
        } catch (JsonProcessingException ex) {
            inbox.finish(event, "FAILED", "Stored webhook payload is invalid");
        }
    }
}
