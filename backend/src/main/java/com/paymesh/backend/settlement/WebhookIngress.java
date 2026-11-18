package com.paymesh.backend.settlement;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Validator;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

@Service
public class WebhookIngress {
    private static final Logger log = LoggerFactory.getLogger(WebhookIngress.class);
    private final WebhookSignatureVerifier signatures;
    private final ObjectMapper json;
    private final Validator validator;
    private final WebhookInbox inbox;
    private final WebhookProcessor processor;

    public WebhookIngress(WebhookSignatureVerifier signatures, ObjectMapper json, Validator validator,
                          WebhookInbox inbox, WebhookProcessor processor) {
        this.signatures = signatures; this.json = json; this.validator = validator;
        this.inbox = inbox; this.processor = processor;
    }

    public WebhookInbox.Receipt receive(String gateway, String timestamp, String signature, byte[] raw) {
        if (raw.length > 65536) throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE);
        signatures.verify(gateway, timestamp, signature, raw);
        WebhookPayload payload;
        try {
            payload = json.readValue(raw, WebhookPayload.class);
        } catch (java.io.IOException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid webhook JSON");
        }
        if (payload == null || !validator.validate(payload).isEmpty()
                || payload.occurredAt().isAfter(Instant.now().plusSeconds(300))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid webhook fields");
        }
        var event = inbox.accept(gateway, payload, new String(raw, StandardCharsets.UTF_8));
        retry(event.id());
        return inbox.get(event.id()).receipt();
    }

    public void retry(UUID id) {
        try {
            processor.process(id);
        } catch (RuntimeException ex) {
            // The inbox commit survives an application failure; no raw payloads or secrets are logged.
            log.warn("Webhook processing failed for event {} ({})", id, ex.getClass().getSimpleName());
            inbox.failure(id);
        }
    }
}
