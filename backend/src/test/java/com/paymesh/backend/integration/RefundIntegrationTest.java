package com.paymesh.backend.integration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.paymesh.backend.dto.RefundRequest;
import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.repository.PaymentRepository;
import com.paymesh.backend.repository.RefundRepository;
import com.paymesh.backend.service.RefundService;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class RefundIntegrationTest extends com.paymesh.backend.testing.BusinessJwtTestSupport {
    @Override protected java.util.Set<String> allowedMerchants() { return java.util.Set.of("REFUND_TEST"); }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired PaymentRepository payments;
    @Autowired RefundRepository refunds;
    @Autowired RefundService service;

    private UUID payment(PaymentStatus status) {
        Payment payment = new Payment("REFUND_TEST", "CUSTOMER", new BigDecimal("1000.00"), "INR", "UPI");
        payment.updateStatus(status);
        return payments.saveAndFlush(payment).getPaymentId();
    }

    private String path(UUID id) {
        return "/api/v1/payments/" + id + "/refund";
    }

    private MvcResult refund(UUID id, String amount, String key) throws Exception {
        return mvc.perform(post(path(id)).with(businessJwt()).header("Idempotency-Key", key)
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":" + amount + "}"))
                .andReturn();
    }

    private JsonNode body(MvcResult result) throws Exception {
        return json.readTree(result.getResponse().getContentAsString());
    }

    private void assertTotal(UUID id, String expected) {
        assertEquals(0, new BigDecimal(expected).compareTo(refunds.totalSuccessfulAmount(id)));
    }

    @Test
    void fullRefundAndReplayAfterCompletion() throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        MvcResult created = refund(id, "1000.00", "full");
        assertEquals(201, created.getResponse().getStatus());
        assertEquals("SUCCESS", body(created).get("status").asText());
        assertEquals(id.toString(), body(created).get("paymentId").asText());
        assertNotNull(body(created).get("createdAt"));
        assertEquals(PaymentStatus.REFUNDED, payments.findById(id).orElseThrow().getStatus());
        MvcResult replay = refund(id, "1000", "full");
        assertEquals(200, replay.getResponse().getStatus());
        assertEquals(body(created), body(replay));
        assertEquals(409, refund(id, "0.01", "another").getResponse().getStatus());
        assertTotal(id, "1000.00");
        assertEquals(1, asCaller(() -> service.getRefundHistory(id)).size());
    }

    @Test
    void multiplePartialRefundsAndHistoryThenRemainingFullBalance() throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        mvc.perform(get(path(id) + "s").with(businessJwt())).andExpect(status().isOk()).andExpect(content().json("[]"));
        MvcResult first = refund(id, "200.00", "part-1");
        MvcResult second = refund(id, "300.00", "part-2");
        assertEquals(201, first.getResponse().getStatus());
        assertEquals(201, second.getResponse().getStatus());
        assertNotEquals(body(first).get("refundId"), body(second).get("refundId"));
        assertEquals(PaymentStatus.SUCCESS, payments.findById(id).orElseThrow().getStatus());
        assertTotal(id, "500.00");
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isOk())
                .andExpect(jsonPath("$.refundId").value(body(second).get("refundId").asText()));
        JsonNode history = body(mvc.perform(get(path(id) + "s").with(businessJwt())).andExpect(status().isOk()).andReturn());
        assertTrue(history.isArray());
        assertEquals(2, history.size());
        assertEquals(body(first), history.get(0));
        assertEquals(body(second), history.get(1));
        assertEquals(201, refund(id, "500.00", "remainder").getResponse().getStatus());
        assertEquals(PaymentStatus.REFUNDED, payments.findById(id).orElseThrow().getStatus());
        assertTotal(id, "1000.00");
    }

    @Test
    void sameKeyReplaysButChangedAmountConflicts() throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        MvcResult first = refund(id, "200", "retry");
        assertEquals(201, first.getResponse().getStatus());
        MvcResult replay = refund(id, "200.00", "retry");
        assertEquals(200, replay.getResponse().getStatus());
        assertEquals(body(first), body(replay));
        assertEquals(409, refund(id, "201", "retry").getResponse().getStatus());
        assertEquals(1, asCaller(() -> service.getRefundHistory(id)).size());
        assertTotal(id, "200");
        // Keys are scoped to payments, so another payment may reuse the key.
        assertEquals(201, refund(payment(PaymentStatus.SUCCESS), "200", "retry").getResponse().getStatus());
    }

    @Test
    void rejectsAmountsAboveOriginalAndRemainingWithoutConsumingKey() throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        assertEquals(409, refund(id, "1000.01", "too-large").getResponse().getStatus());
        assertTotal(id, "0");
        assertEquals(201, refund(id, "800", "first").getResponse().getStatus());
        assertEquals(409, refund(id, "200.01", "too-large").getResponse().getStatus());
        assertTotal(id, "800");
        assertEquals(PaymentStatus.SUCCESS, payments.findById(id).orElseThrow().getStatus());
        assertEquals(201, refund(id, "200", "too-large").getResponse().getStatus());
        assertTotal(id, "1000");
    }

    @ParameterizedTest
    @ValueSource(strings = {"0", "-1", "0.001", "1.001", "100000000000000000", "null"})
    void rejectsInvalidAmounts(String amount) throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        assertEquals(400, refund(id, amount, "invalid").getResponse().getStatus());
        assertTotal(id, "0");
        assertEquals(PaymentStatus.SUCCESS, payments.findById(id).orElseThrow().getStatus());
    }

    @Test
    void requiresBodyAmountAndValidKey() throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        mvc.perform(post(path(id)).with(businessJwt()).header("Idempotency-Key", "missing-body"))
                .andExpect(status().isBadRequest());
        mvc.perform(post(path(id)).with(businessJwt()).header("Idempotency-Key", "missing-amount")
                .contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest());
        mvc.perform(post(path(id)).with(businessJwt()).contentType(MediaType.APPLICATION_JSON).content("{\"amount\":200}"))
                .andExpect(status().isBadRequest());
        assertEquals(400, refund(id, "200", "   ").getResponse().getStatus());
        assertEquals(400, refund(id, "200", "x".repeat(256)).getResponse().getStatus());
        assertTotal(id, "0");
    }

    @ParameterizedTest
    @ValueSource(strings = {"CREATED", "PROCESSING", "FAILED", "CANCELLED", "REFUNDED"})
    void rejectsIneligiblePaymentStates(String status) throws Exception {
        UUID id = payment(PaymentStatus.valueOf(status));
        assertEquals(409, refund(id, "200", "state").getResponse().getStatus());
        assertTotal(id, "0");
        assertEquals(PaymentStatus.valueOf(status), payments.findById(id).orElseThrow().getStatus());
    }

    @Test
    void nonexistentPaymentReturnsNotFound() throws Exception {
        UUID id = UUID.randomUUID();
        assertEquals(404, refund(id, "200", "missing").getResponse().getStatus());
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isNotFound());
        mvc.perform(get(path(id) + "s").with(businessJwt())).andExpect(status().isNotFound());
    }

    @Test
    void serviceAlsoRejectsInvalidInputs() {
        UUID id = payment(PaymentStatus.SUCCESS);
        assertThrows(IllegalArgumentException.class, () -> asCaller(() -> service.refund(id, new RefundRequest(new BigDecimal("1.001")), "key")));
        assertThrows(IllegalArgumentException.class, () -> asCaller(() -> service.refund(id, null, "key")));
        assertThrows(IllegalArgumentException.class, () -> asCaller(() -> service.refund(id, new RefundRequest(BigDecimal.ONE), null)));
        assertTotal(id, "0");
    }

    private List<MvcResult> concurrent(UUID id, int count, String amount, boolean sameKey) throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(count);
        CountDownLatch ready = new CountDownLatch(count);
        CountDownLatch start = new CountDownLatch(1);
        try {
            List<Future<MvcResult>> futures = new ArrayList<>();
            for (int i = 0; i < count; i++) {
                String key = sameKey ? "concurrent-retry" : "concurrent-" + i;
                futures.add(executor.submit(() -> {
                    ready.countDown();
                    if (!start.await(10, TimeUnit.SECONDS)) throw new IllegalStateException("Start timed out");
                    return refund(id, amount, key);
                }));
            }
            assertTrue(ready.await(10, TimeUnit.SECONDS));
            start.countDown();
            List<MvcResult> results = new ArrayList<>();
            for (Future<MvcResult> future : futures) results.add(future.get(30, TimeUnit.SECONDS));
            return results;
        } finally {
            start.countDown();
            executor.shutdownNow();
            assertTrue(executor.awaitTermination(10, TimeUnit.SECONDS));
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"200", "300"})
    void concurrentDistinctRequestsNeverExceedBalance(String amount) throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        List<MvcResult> results = concurrent(id, 10, amount, false);
        int expectedCreated = amount.equals("200") ? 5 : 3;
        assertEquals(expectedCreated, results.stream().filter(r -> r.getResponse().getStatus() == 201).count());
        assertEquals(10 - expectedCreated, results.stream().filter(r -> r.getResponse().getStatus() == 409).count());
        assertTotal(id, amount.equals("200") ? "1000" : "900");
        assertEquals(expectedCreated, asCaller(() -> service.getRefundHistory(id)).size());
        assertEquals(amount.equals("200") ? PaymentStatus.REFUNDED : PaymentStatus.SUCCESS,
                payments.findById(id).orElseThrow().getStatus());
    }

    @ParameterizedTest
    @ValueSource(strings = {"200", "1000"})
    void concurrentDuplicateRequestsCreateOnlyOneRefund(String amount) throws Exception {
        UUID id = payment(PaymentStatus.SUCCESS);
        List<MvcResult> results = concurrent(id, 10, amount, true);
        assertEquals(1, results.stream().filter(r -> r.getResponse().getStatus() == 201).count());
        assertEquals(9, results.stream().filter(r -> r.getResponse().getStatus() == 200).count());
        List<String> ids = new ArrayList<>();
        for (MvcResult result : results) ids.add(body(result).get("refundId").asText());
        assertEquals(1, ids.stream().distinct().count());
        assertTotal(id, amount);
        assertEquals(1, asCaller(() -> service.getRefundHistory(id)).size());
    }
}
