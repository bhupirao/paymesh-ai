package com.paymesh.backend.settlement;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/settlement")
public class SettlementAdminController {
    private final String token;
    private final ReconciliationRunner runner;
    private final JdbcTemplate jdbc;
    private final WebhookIngress ingress;
    private final WebhookInbox inbox;

    public SettlementAdminController(@Value("${paymesh.settlement.admin-token:}") String token,
                                     ReconciliationRunner runner, JdbcTemplate jdbc, WebhookIngress ingress, WebhookInbox inbox) {
        this.token = token; this.runner = runner; this.jdbc = jdbc; this.ingress = ingress; this.inbox = inbox;
    }

    @PostMapping("/payments/{paymentId}/reconcile")
    public ReconciliationService.Report reconcile(@RequestHeader(value = "Authorization", required = false) String auth,
                                                  @PathVariable("paymentId") UUID paymentId) {
        authorize(auth);
        return runner.run(paymentId);
    }

    @GetMapping("/payments/{paymentId}/reconciliation")
    public List<Map<String, Object>> history(@RequestHeader(value = "Authorization", required = false) String auth,
                                           @PathVariable("paymentId") UUID paymentId) {
        authorize(auth);
        return jdbc.queryForList("SELECT * FROM reconciliation_attempts WHERE payment_id = ? ORDER BY attempt LIMIT 100", paymentId);
    }

    @GetMapping("/payments/{paymentId}/webhooks")
    public List<Map<String, Object>> events(@RequestHeader(value = "Authorization", required = false) String auth,
                                          @PathVariable("paymentId") UUID paymentId) {
        authorize(auth);
        return jdbc.queryForList("SELECT * FROM webhook_events WHERE payment_id = ? ORDER BY received_at DESC, id LIMIT 100", paymentId);
    }

    @PostMapping("/webhooks/{id}/retry")
    public WebhookInbox.Receipt retry(@RequestHeader(value = "Authorization", required = false) String auth, @PathVariable("id") UUID id) {
        authorize(auth);
        if (jdbc.queryForObject("SELECT count(*) FROM webhook_events WHERE id = ?", Integer.class, id) == 0) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        ingress.retry(id);
        return inbox.get(id).receipt();
    }

    private void authorize(String supplied) {
        if (token == null || token.length() < 32) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Settlement admin token is not configured");
        }
        if (supplied == null || !MessageDigest.isEqual(("Bearer " + token).getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8))) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
        }
    }
}
