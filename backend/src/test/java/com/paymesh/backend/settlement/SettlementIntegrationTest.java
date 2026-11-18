package com.paymesh.backend.settlement;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.paymesh.backend.dto.RefundRequest;
import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.gateway.GatewayResponse;
import com.paymesh.backend.gateway.GatewayStatus;
import com.paymesh.backend.gateway.DemoGatewayTimeoutSimulator;
import com.paymesh.backend.repository.GatewayTransactionRepository;
import com.paymesh.backend.repository.PaymentRepository;
import com.paymesh.backend.repository.RefundRepository;
import com.paymesh.backend.service.internal.InternalGatewayTransactionService;
import com.paymesh.backend.service.internal.InternalPaymentService;
import com.paymesh.backend.service.PaymentOrchestrationService;
import com.paymesh.backend.service.internal.InternalRefundService;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.context.annotation.Bean;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "paymesh.webhooks.razorpay-secret=" + WebhookSignatureVerifierTest.RAZORPAY,
        "paymesh.webhooks.stripe-secret=" + WebhookSignatureVerifierTest.STRIPE,
        "paymesh.settlement.admin-token=integration-admin-token-at-least-32-characters",
        "paymesh.settlement.scheduling-enabled=false"})
@Import(SettlementIntegrationTest.DemoTimeoutTestConfiguration.class)
@AutoConfigureMockMvc
class SettlementIntegrationTest extends com.paymesh.backend.testing.BusinessJwtTestSupport {
    @Override protected java.util.Set<String> allowedMerchants() { return java.util.Set.of("WEBHOOK_TEST", "LEDGER_TEST"); }
    private static final String AUTH = "Bearer integration-admin-token-at-least-32-characters";
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcTemplate jdbc;
    @Autowired PaymentRepository payments;
    @Autowired GatewayTransactionRepository transactions;
    @Autowired RefundRepository refunds;
    @Autowired InternalRefundService refundService;
    @Autowired InternalPaymentService paymentService;
    @Autowired PaymentOrchestrationService orchestration;
    @Autowired InternalGatewayTransactionService transactionService;
    @Autowired WebhookInbox inbox;
    @Autowired WebhookIngress ingress;
    @Autowired ReconciliationRunner reconciler;
    @Autowired SimulatedGatewayLedger ledger;
    @MockitoSpyBean SimulatedStatusLookup lookup;
    @MockitoSpyBean OutcomeApplier applier;

    @TestConfiguration(proxyBeanMethods = false)
    static class DemoTimeoutTestConfiguration {
        @Bean DemoGatewayTimeoutSimulator demoGatewayTimeoutSimulator() {
            return new DemoGatewayTimeoutSimulator();
        }
    }

    record Fixture(UUID paymentId, UUID attemptId, UUID transactionId, String gateway) {}

    private Fixture fixture(String currency, PaymentStatus status) {
        Payment p = new Payment("WEBHOOK_TEST", "CUSTOMER", new BigDecimal("1000.00"), currency, "UPI");
        p.updateStatus(status);
        payments.saveAndFlush(p);
        String gateway = currency.equals("USD") ? "MOCK_STRIPE" : "MOCK_RAZORPAY";
        UUID transactionId = UUID.randomUUID();
        GatewayTransaction attempt = new GatewayTransaction(p.getPaymentId(), gateway);
        attempt.updateResult(transactionId, "UNKNOWN", "SIMULATED_UNCERTAIN", "Awaiting outcome");
        transactions.saveAndFlush(attempt);
        return new Fixture(p.getPaymentId(), attempt.getId(), transactionId, gateway);
    }

    private String payload(Fixture f, String id, String outcome, Instant occurredAt) throws Exception {
        return json.writeValueAsString(new WebhookPayload(id, f.paymentId(), f.transactionId(),
                Observation.valueOf(outcome), occurredAt));
    }

    private MvcResult send(String provider, String payload) throws Exception {
        byte[] raw = payload.getBytes(StandardCharsets.UTF_8);
        String timestamp = Long.toString(Instant.now().getEpochSecond());
        String secret = provider.equals("mock-stripe") ? WebhookSignatureVerifierTest.STRIPE : WebhookSignatureVerifierTest.RAZORPAY;
        return mvc.perform(post("/api/v1/webhooks/" + provider).contentType(MediaType.APPLICATION_JSON)
                .header("X-Paymesh-Timestamp", timestamp)
                .header("X-Paymesh-Signature", WebhookSignatureVerifierTest.sign(secret, timestamp, raw))
                .content(raw)).andReturn();
    }

    private MvcResult send(Fixture f, String payload) throws Exception {
        return send(f.gateway().equals("MOCK_STRIPE") ? "mock-stripe" : "mock-razorpay", payload);
    }

    private JsonNode body(MvcResult result) throws Exception {
        return json.readTree(result.getResponse().getContentAsString());
    }

    private PaymentStatus state(Fixture f) {
        return payments.findById(f.paymentId()).orElseThrow().getStatus();
    }

    private void outcome(Fixture f, Observation status) {
        jdbc.update("""
                INSERT INTO simulated_gateway_outcomes(gateway, payment_id, gateway_transaction_id, outcome)
                VALUES (?, ?, ?, ?)
                """, f.gateway(), f.paymentId(), f.transactionId(), status.name());
    }

    private void dueWebhook(UUID id) {
        jdbc.update("UPDATE webhook_events SET next_attempt_at = CURRENT_TIMESTAMP - INTERVAL '1 second' WHERE id = ?", id);
    }

    private void dueReconciliation(UUID id) {
        jdbc.update("UPDATE reconciliation_jobs SET next_attempt_at = CURRENT_TIMESTAMP - INTERVAL '1 second' WHERE payment_id = ?", id);
    }

    private Fixture createAndTimeoutThroughHttp(String currency, String customerId) throws Exception {
        MvcResult created = mvc.perform(post("/api/v1/payments").with(businessJwt())
                        .header("Idempotency-Key", "demo-fault-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsBytes(new PaymentRequest("WEBHOOK_TEST", new BigDecimal("125.00"),
                                currency, customerId, "CARD"))))
                .andExpect(status().isCreated()).andReturn();
        UUID paymentId = UUID.fromString(body(created).get("paymentId").asText());

        mvc.perform(post("/api/v1/payments/{paymentId}/process", paymentId).with(businessJwt()))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("PROCESSING"));

        JsonNode history = json.readTree(mvc.perform(get("/api/v1/payments/{paymentId}/gateway-transactions", paymentId)
                        .with(businessJwt()))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        assertEquals(1, history.size());
        JsonNode attempt = history.get(0);
        assertEquals("TIMEOUT", attempt.get("status").asText());
        UUID gatewayTransactionId = UUID.fromString(attempt.get("gatewayTransactionId").asText());
        String actualGateway = "INR".equals(currency) ? "MOCK_RAZORPAY" : "MOCK_STRIPE";
        assertEquals(new SimulatedGatewayLedger.Lookup(gatewayTransactionId, Observation.SUCCESS),
                ledger.lookup(paymentId, actualGateway).orElseThrow());
        return new Fixture(paymentId, UUID.fromString(attempt.get("id").asText()), gatewayTransactionId, actualGateway);
    }

    @Test
    void deterministicTimeoutIsResolvedBySignedWebhookAndDuplicateIsIdempotent() throws Exception {
        Fixture f = createAndTimeoutThroughHttp("INR", DemoGatewayTimeoutSimulator.RESERVED_CUSTOMER_ID);
        assertEquals(PaymentStatus.PROCESSING, state(f));
        String raw = payload(f, "demo-webhook-" + UUID.randomUUID(), "SUCCESS", Instant.now());
        JsonNode first = body(send(f, raw));
        assertEquals("PROCESSED", first.get("status").asText());
        assertEquals(PaymentStatus.SUCCESS, state(f));
        long versionAfterFirst = jdbc.queryForObject("SELECT version FROM payments WHERE payment_id = ?", Long.class, f.paymentId());

        JsonNode duplicate = body(send(f, raw));
        assertEquals(first, duplicate);
        assertEquals(PaymentStatus.SUCCESS, state(f));
        assertEquals(versionAfterFirst, jdbc.queryForObject("SELECT version FROM payments WHERE payment_id = ?", Long.class, f.paymentId()));
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM webhook_events WHERE payment_id = ?", Integer.class, f.paymentId()));
        assertEquals(1, jdbc.queryForObject("SELECT attempts FROM webhook_events WHERE payment_id = ?", Integer.class, f.paymentId()));
        assertEquals(1, transactions.countByPaymentId(f.paymentId()));
    }

    @Test
    void deterministicTimeoutIsIndependentlyResolvedBySettlementReconciliation() throws Exception {
        Fixture f = createAndTimeoutThroughHttp("USD", DemoGatewayTimeoutSimulator.RESERVED_CUSTOMER_ID);
        assertEquals(PaymentStatus.PROCESSING, state(f));
        mvc.perform(post("/api/v1/settlement/payments/{paymentId}/reconcile", f.paymentId())
                        .header("Authorization", AUTH))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("RESOLVED"));
        assertEquals(PaymentStatus.SUCCESS, state(f));
        assertEquals(new SimulatedGatewayLedger.Lookup(f.transactionId(), Observation.SUCCESS),
                ledger.lookup(f.paymentId(), f.gateway()).orElseThrow());
        assertEquals(1, transactions.countByPaymentId(f.paymentId()));
    }

    @Test
    void duplicateProcessCannotCreateSecondCharge() throws Exception {
        Fixture timedOut = createAndTimeoutThroughHttp("INR", DemoGatewayTimeoutSimulator.RESERVED_CUSTOMER_ID);
        mvc.perform(post("/api/v1/payments/{paymentId}/process", timedOut.paymentId()).with(businessJwt()))
                .andExpect(status().isConflict());
        assertEquals(1, transactions.countByPaymentId(timedOut.paymentId()));
        assertEquals(Observation.SUCCESS,
                ledger.lookup(timedOut.paymentId(), "MOCK_RAZORPAY").orElseThrow().outcome());
    }

    @ParameterizedTest
    @ValueSource(strings = {"INR", "USD"})
    void normalSupportedCurrencyPaymentsStillSucceed(String currency) throws Exception {
        Fixture ordinary = createAndProcessOrdinaryPayment(currency);
        assertEquals(PaymentStatus.SUCCESS, state(ordinary));
        String gateway = "INR".equals(currency) ? "MOCK_RAZORPAY" : "MOCK_STRIPE";
        assertEquals(Observation.SUCCESS, ledger.lookup(ordinary.paymentId(), gateway).orElseThrow().outcome());
    }

    private Fixture createAndProcessOrdinaryPayment(String currency) throws Exception {
        MvcResult created = mvc.perform(post("/api/v1/payments").with(businessJwt())
                        .header("Idempotency-Key", "ordinary-" + UUID.randomUUID())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsBytes(new PaymentRequest("WEBHOOK_TEST", new BigDecimal("125.00"),
                                currency, "ordinary-demo-customer", "CARD"))))
                .andExpect(status().isCreated()).andReturn();
        UUID paymentId = UUID.fromString(body(created).get("paymentId").asText());
        mvc.perform(post("/api/v1/payments/{paymentId}/process", paymentId).with(businessJwt()))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("SUCCESS"));
        GatewayTransaction attempt = transactions.findFirstByPaymentIdOrderByCreatedAtDesc(paymentId).orElseThrow();
        return new Fixture(paymentId, attempt.getId(), attempt.getGatewayTransactionId(), "MOCK_STRIPE");
    }

    @ParameterizedTest
    @ValueSource(strings = {"INR", "USD"})
    void bothProvidersSettleAndPersistRawAudit(String currency) throws Exception {
        Fixture f = fixture(currency, PaymentStatus.PROCESSING);
        String raw = payload(f, "event-" + UUID.randomUUID(), "SUCCESS", Instant.now());
        MvcResult response = send(f, raw);
        assertEquals(200, response.getResponse().getStatus());
        assertEquals("PROCESSED", body(response).get("status").asText());
        assertEquals(PaymentStatus.SUCCESS, state(f));
        assertEquals("SUCCESS", transactions.findById(f.attemptId()).orElseThrow().getStatus());
        Map<String, Object> audit = jdbc.queryForMap("SELECT * FROM webhook_events WHERE payment_id = ?", f.paymentId());
        assertEquals(raw, audit.get("payload"));
        assertEquals(1, audit.get("attempts"));
        assertNotNull(audit.get("processed_at"));
        assertNotNull(audit.get("received_at"));
    }

    @Test
    void duplicateReplaysAndPayloadCollisionAreSafe() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        String event = "event-" + UUID.randomUUID();
        String raw = payload(f, event, "SUCCESS", Instant.now());
        JsonNode first = body(send(f, raw));
        JsonNode duplicate = body(send(f, raw));
        assertEquals(first, duplicate);
        assertEquals(409, send(f, payload(f, event, "FAILED", Instant.now())).getResponse().getStatus());
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM webhook_events WHERE payment_id = ?", Integer.class, f.paymentId()));
        assertEquals(1L, jdbc.queryForObject("SELECT version FROM payments WHERE payment_id = ?", Long.class, f.paymentId()));
        assertEquals(raw, jdbc.queryForObject("SELECT payload FROM webhook_events WHERE payment_id = ?", String.class, f.paymentId()));
    }

    @Test
    void invalidSignatureAndMalformedSignedBodyDoNotChangePayments() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        mvc.perform(post("/api/v1/webhooks/mock-razorpay").contentType(MediaType.APPLICATION_JSON)
                .header("X-Paymesh-Timestamp", Instant.now().getEpochSecond())
                .header("X-Paymesh-Signature", "0".repeat(64)).content("{}"))
                .andExpect(status().isUnauthorized());
        assertEquals(400, send(f, "{}").getResponse().getStatus());
        assertEquals(400, send(f, "not-json").getResponse().getStatus());
        assertEquals(413, send(f, "x".repeat(65537)).getResponse().getStatus());
        assertEquals(PaymentStatus.PROCESSING, state(f));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM webhook_events WHERE payment_id = ?", Integer.class, f.paymentId()));
    }

    @ParameterizedTest
    @ValueSource(strings = {"SUCCESS", "FAILED", "CANCELLED", "REFUNDED"})
    void terminalPaymentStatesNeverRegress(String status) throws Exception {
        Fixture f = fixture("INR", PaymentStatus.valueOf(status));
        assertEquals("IGNORED", body(send(f, payload(f, "terminal-" + UUID.randomUUID(), "SUCCESS", Instant.now()))).get("status").asText());
        assertEquals(PaymentStatus.valueOf(status), state(f));
    }

    @Test
    void outOfOrderUncertainAndConflictingEventsCannotReverseFirstTerminalResult() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        Instant at = Instant.now();
        String timeout = payload(f, "uncertain-" + UUID.randomUUID(), "TIMEOUT", at);
        MvcResult deferred = send(f, timeout);
        assertEquals(202, deferred.getResponse().getStatus());
        assertEquals(PaymentStatus.PROCESSING, state(f));
        assertEquals("PROCESSED", body(send(f, payload(f, "failure-" + UUID.randomUUID(), "FAILED", at.plusMillis(1)))).get("status").asText());
        assertEquals("IGNORED", body(send(f, payload(f, "late-success-" + UUID.randomUUID(), "SUCCESS", at))).get("status").asText());
        UUID deferredId = UUID.fromString(body(deferred).get("id").asText());
        dueWebhook(deferredId);
        ingress.retry(deferredId);
        assertEquals("IGNORED", inbox.get(deferredId).status());
        assertEquals(PaymentStatus.FAILED, state(f));
    }

    @Test
    void delayedEventForCurrentAttemptIsAcceptedButPredatingOrWrongIdentityIsIgnored() throws Exception {
        Fixture delayed = fixture("INR", PaymentStatus.PROCESSING);
        jdbc.update("UPDATE payment_gateway_transactions SET created_at = CURRENT_TIMESTAMP - INTERVAL '2 hours' WHERE id = ?", delayed.attemptId());
        assertEquals("PROCESSED", body(send(delayed, payload(delayed, "delayed-" + UUID.randomUUID(), "SUCCESS", Instant.now().minusSeconds(3600)))).get("status").asText());
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        assertEquals("IGNORED", body(send(f, payload(f, "old-" + UUID.randomUUID(), "SUCCESS", Instant.now().minusSeconds(3600)))).get("status").asText());
        Fixture wrong = new Fixture(f.paymentId(), f.attemptId(), UUID.randomUUID(), f.gateway());
        assertEquals("IGNORED", body(send(f, payload(wrong, "wrong-" + UUID.randomUUID(), "SUCCESS", Instant.now()))).get("status").asText());
        assertEquals("IGNORED", body(send("mock-stripe", payload(f, "provider-" + UUID.randomUUID(), "SUCCESS", Instant.now()))).get("status").asText());
        assertEquals(PaymentStatus.PROCESSING, state(f));
    }

    @Test
    void deferredWebhookCanResolveLaterAndUnknownPaymentRetriesAreBounded() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.CREATED);
        UUID eventId = UUID.fromString(body(send(f, payload(f, "early-" + UUID.randomUUID(), "SUCCESS", Instant.now()))).get("id").asText());
        assertEquals("DEFERRED", inbox.get(eventId).status());
        paymentService.updatePaymentStatus(f.paymentId(), PaymentStatus.PROCESSING);
        dueWebhook(eventId);
        ingress.retry(eventId);
        assertEquals("PROCESSED", inbox.get(eventId).status());
        Fixture missing = new Fixture(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), "MOCK_RAZORPAY");
        UUID missingEvent = UUID.fromString(body(send(missing, payload(missing, "missing-" + UUID.randomUUID(), "SUCCESS", Instant.now()))).get("id").asText());
        ingress.retry(missingEvent); // Backoff prevents immediate retries from using the budget.
        assertEquals(1, inbox.get(missingEvent).attempts());
        for (int i = 0; i < 4; i++) { dueWebhook(missingEvent); ingress.retry(missingEvent); }
        assertEquals("FAILED", inbox.get(missingEvent).status());
        assertEquals(3, inbox.get(missingEvent).attempts());
    }

    @Test
    void fullRefundRemainsRefundedAfterLateWebhookAndSynchronousCompletion() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        send(f, payload(f, "paid-" + UUID.randomUUID(), "SUCCESS", Instant.now()));
        var refund = refundService.refund(f.paymentId(), new RefundRequest(new BigDecimal("1000")), "full-refund");
        assertEquals("IGNORED", body(send(f, payload(f, "late-" + UUID.randomUUID(), "SUCCESS", Instant.now()))).get("status").asText());
        assertThrows(IllegalStateException.class, () -> paymentService.updatePaymentStatus(f.paymentId(), PaymentStatus.SUCCESS));
        transactionService.markTransactionUnknown(f.attemptId(), "late timeout");
        transactionService.completeTransaction(f.attemptId(), new GatewayResponse(f.transactionId(), f.gateway(), GatewayStatus.FAILED, null, null));
        assertEquals("SUCCESS", transactions.findById(f.attemptId()).orElseThrow().getStatus());
        assertEquals(PaymentStatus.REFUNDED, state(f));
        assertEquals(refund.refund(), refundService.getRefund(f.paymentId()));
        assertEquals(0, new BigDecimal("1000").compareTo(refunds.totalSuccessfulAmount(f.paymentId())));
    }

    @ParameterizedTest
    @ValueSource(strings = {"SUCCESS", "FAILED"})
    void reconciliationResolvesFromSimulatedLedger(String outcome) {
        Fixture f = fixture("USD", PaymentStatus.PROCESSING);
        outcome(f, Observation.valueOf(outcome));
        var report = reconciler.run(f.paymentId());
        assertEquals("RESOLVED", report.status());
        assertEquals(1, report.attempts());
        assertEquals(PaymentStatus.valueOf(outcome), state(f));
        assertEquals(outcome, transactions.findById(f.attemptId()).orElseThrow().getStatus());
        assertEquals(report, reconciler.run(f.paymentId()));
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM reconciliation_attempts WHERE payment_id = ?", Integer.class, f.paymentId()));
    }

    @Test
    void reconciliationSupportsRouterAttemptsAndLegacyPersistedResults() {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        jdbc.update("UPDATE payment_gateway_transactions SET gateway_name = 'MOCK_ROUTER', gateway_transaction_id = NULL WHERE id = ?", f.attemptId());
        outcome(f, Observation.SUCCESS);
        assertEquals("RESOLVED", reconciler.run(f.paymentId()).status());
        assertEquals(PaymentStatus.SUCCESS, state(f));
        Fixture legacy = fixture("INR", PaymentStatus.PROCESSING);
        jdbc.update("UPDATE payment_gateway_transactions SET status = 'SUCCESS' WHERE id = ?", legacy.attemptId());
        assertEquals("RESOLVED", reconciler.run(legacy.paymentId()).status());
        assertEquals(PaymentStatus.SUCCESS, state(legacy));
    }

    @Test
    void unknownOutcomesExhaustRetriesWithoutInventingSuccess() {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        assertEquals("RETRY", reconciler.run(f.paymentId()).status());
        assertEquals(1, reconciler.run(f.paymentId()).attempts());
        dueReconciliation(f.paymentId());
        assertEquals(2, reconciler.run(f.paymentId()).attempts());
        dueReconciliation(f.paymentId());
        assertEquals("EXHAUSTED", reconciler.run(f.paymentId()).status());
        dueReconciliation(f.paymentId());
        assertEquals(3, reconciler.run(f.paymentId()).attempts());
        assertEquals(PaymentStatus.PROCESSING, state(f));
        assertEquals(3, jdbc.queryForObject("SELECT count(*) FROM reconciliation_attempts WHERE payment_id = ?", Integer.class, f.paymentId()));
    }

    @Test
    void lookupFailureIsAuditedAndRetryCanRecover() {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        outcome(f, Observation.SUCCESS);
        doThrow(new IllegalStateException("Simulated lookup unavailable")).doCallRealMethod()
                .when(lookup).lookup(argThat(p -> p != null && p.getPaymentId().equals(f.paymentId())), any());
        assertEquals("RETRY", reconciler.run(f.paymentId()).status());
        assertEquals(PaymentStatus.PROCESSING, state(f));
        dueReconciliation(f.paymentId());
        assertEquals("RESOLVED", reconciler.run(f.paymentId()).status());
        assertEquals(2, jdbc.queryForObject("SELECT count(*) FROM reconciliation_attempts WHERE payment_id = ?", Integer.class, f.paymentId()));
    }

    @Test
    void conflictingProviderEvidenceRequiresInvestigation() {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        outcome(f, Observation.FAILED);
        jdbc.update("UPDATE payment_gateway_transactions SET status = 'SUCCESS' WHERE id = ?", f.attemptId());
        assertEquals("EXHAUSTED", reconciler.run(f.paymentId()).status());
        assertEquals(PaymentStatus.PROCESSING, state(f));
    }

    @Test
    void adminEndpointsRequireTokenAndExposeAudit() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.REFUNDED);
        String base = "/api/v1/settlement/payments/" + f.paymentId();
        mvc.perform(post(base + "/reconcile").header("Authorization", "Bearer wrong")).andExpect(status().isUnauthorized());
        mvc.perform(post(base + "/reconcile").header("Authorization", AUTH)).andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("SKIPPED"));
        mvc.perform(get(base + "/reconciliation").header("Authorization", AUTH)).andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status_before").value("REFUNDED"));
        send(f, payload(f, "audit-" + UUID.randomUUID(), "SUCCESS", Instant.now()));
        mvc.perform(get(base + "/webhooks").header("Authorization", AUTH)).andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status").value("IGNORED"));
        mvc.perform(post("/api/v1/settlement/payments/" + UUID.randomUUID() + "/reconcile")
                .header("Authorization", AUTH)).andExpect(status().isNotFound());
    }

    private <T> List<T> concurrent(List<Callable<T>> tasks) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(tasks.size());
        CountDownLatch ready = new CountDownLatch(tasks.size());
        CountDownLatch start = new CountDownLatch(1);
        try {
            List<Future<T>> futures = new ArrayList<>();
            for (Callable<T> task : tasks) futures.add(pool.submit(() -> {
                ready.countDown();
                if (!start.await(10, TimeUnit.SECONDS)) throw new IllegalStateException("Start timed out");
                return task.call();
            }));
            assertTrue(ready.await(10, TimeUnit.SECONDS));
            start.countDown();
            List<T> results = new ArrayList<>();
            for (Future<T> future : futures) results.add(future.get(30, TimeUnit.SECONDS));
            return results;
        } finally {
            start.countDown(); pool.shutdownNow();
            assertTrue(pool.awaitTermination(10, TimeUnit.SECONDS));
        }
    }

    @Test
    void concurrentDuplicateWebhooksProcessExactlyOnce() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        String raw = payload(f, "concurrent-" + UUID.randomUUID(), "SUCCESS", Instant.now());
        List<Callable<MvcResult>> tasks = new ArrayList<>();
        for (int i = 0; i < 8; i++) tasks.add(() -> send(f, raw));
        for (MvcResult result : concurrent(tasks)) assertEquals(200, result.getResponse().getStatus());
        assertEquals(PaymentStatus.SUCCESS, state(f));
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM webhook_events WHERE payment_id = ?", Integer.class, f.paymentId()));
        assertEquals(1, jdbc.queryForObject("SELECT attempts FROM webhook_events WHERE payment_id = ?", Integer.class, f.paymentId()));
        assertEquals(1L, jdbc.queryForObject("SELECT version FROM payments WHERE payment_id = ?", Long.class, f.paymentId()));
    }

    @Test
    void concurrentReconciliationAndWebhooksConverge() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        outcome(f, Observation.SUCCESS);
        String raw = payload(f, "race-" + UUID.randomUUID(), "SUCCESS", Instant.now());
        List<Callable<String>> tasks = new ArrayList<>();
        for (int i = 0; i < 4; i++) tasks.add(() -> reconciler.run(f.paymentId()).status());
        for (int i = 0; i < 4; i++) tasks.add(() -> body(send(f, raw)).get("status").asText());
        for (String result : concurrent(tasks)) assertTrue(Set.of("RESOLVED", "SKIPPED", "PROCESSED", "IGNORED").contains(result));
        assertEquals(PaymentStatus.SUCCESS, state(f));
        assertEquals("SUCCESS", transactions.findById(f.attemptId()).orElseThrow().getStatus());
        assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM reconciliation_attempts WHERE payment_id = ?", Integer.class, f.paymentId()));
        assertEquals(1L, jdbc.queryForObject("SELECT version FROM payments WHERE payment_id = ?", Long.class, f.paymentId()));
    }

    @Test
    void concurrentRefundAndWebhookCannotRestoreSuccess() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.SUCCESS);
        List<Callable<String>> tasks = List.of(
                () -> refundService.refund(f.paymentId(), new RefundRequest(new BigDecimal("1000")), "race-refund").refund().status(),
                () -> body(send(f, payload(f, "refund-race-" + UUID.randomUUID(), "SUCCESS", Instant.now()))).get("status").asText());
        concurrent(tasks);
        assertEquals(PaymentStatus.REFUNDED, state(f));
        assertEquals(0, new BigDecimal("1000").compareTo(refunds.totalSuccessfulAmount(f.paymentId())));
    }

    @Test
    void failedWebhookProcessingRollsBackStateAndRetainsInboxForRetry() throws Exception {
        Fixture f = fixture("INR", PaymentStatus.PROCESSING);
        doAnswer(invocation -> {
            invocation.callRealMethod();
            throw new IllegalStateException("Simulated application failure after mutation");
        }).doCallRealMethod().when(applier).apply(
                argThat(p -> p != null && p.getPaymentId().equals(f.paymentId())), anyString(), any(), any(), any());
        MvcResult response = send(f, payload(f, "rollback-" + UUID.randomUUID(), "SUCCESS", Instant.now()));
        assertEquals(202, response.getResponse().getStatus());
        UUID id = UUID.fromString(body(response).get("id").asText());
        assertEquals("DEFERRED", inbox.get(id).status());
        assertEquals(1, inbox.get(id).attempts());
        assertEquals(PaymentStatus.PROCESSING, state(f));
        assertEquals("UNKNOWN", transactions.findById(f.attemptId()).orElseThrow().getStatus());
        dueWebhook(id);
        ingress.retry(id);
        assertEquals("PROCESSED", inbox.get(id).status());
        assertEquals(2, inbox.get(id).attempts());
        assertEquals(PaymentStatus.SUCCESS, state(f));
    }

    @ParameterizedTest
    @ValueSource(strings = {"INR", "USD"})
    void realMockRoutingPersistsIndependentSimulationEvidence(String currency) throws Exception {
        UUID id = paymentService.createPayment(new PaymentRequest("LEDGER_TEST", new BigDecimal("1000.00"),
                currency, "CUSTOMER", "CARD"), "ledger-" + UUID.randomUUID()).payment().paymentId();
        assertEquals("SUCCESS", asCaller(() -> orchestration.processPayment(id)).status());
        String gateway = currency.equals("INR") ? "MOCK_RAZORPAY" : "MOCK_STRIPE";
        var evidence = ledger.lookup(id, gateway).orElseThrow();
        assertEquals(Observation.SUCCESS, evidence.outcome());
        assertEquals(evidence.transactionId(), transactions.findFirstByPaymentIdOrderByCreatedAtDesc(id).orElseThrow().getGatewayTransactionId());
    }

    @Test
    void prematureReconciliationDoesNotConsumeFutureRetryBudget() {
        Fixture f = fixture("INR", PaymentStatus.CREATED);
        assertEquals("NOT_ELIGIBLE", reconciler.run(f.paymentId()).status());
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM reconciliation_jobs WHERE payment_id = ?", Integer.class, f.paymentId()));
        paymentService.updatePaymentStatus(f.paymentId(), PaymentStatus.PROCESSING);
        outcome(f, Observation.SUCCESS);
        assertEquals("RESOLVED", reconciler.run(f.paymentId()).status());
        assertEquals(1, jdbc.queryForObject("SELECT attempts FROM reconciliation_jobs WHERE payment_id = ?", Integer.class, f.paymentId()));
    }

    @Test
    void schedulerDiscoversStuckPaymentsAndLeavesYoungAttemptsAlone() {
        Fixture stuck = fixture("INR", PaymentStatus.PROCESSING);
        Fixture young = fixture("INR", PaymentStatus.PROCESSING);
        outcome(stuck, Observation.SUCCESS);
        outcome(young, Observation.SUCCESS);
        jdbc.update("UPDATE payments SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 minutes' WHERE payment_id = ?", stuck.paymentId());
        new SettlementScheduler(inbox, ingress, jdbc, reconciler).tick();
        assertEquals(PaymentStatus.SUCCESS, state(stuck));
        assertEquals(PaymentStatus.PROCESSING, state(young));
    }
}
