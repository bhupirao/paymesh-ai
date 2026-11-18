package com.paymesh.backend.security.business;

import com.fasterxml.jackson.databind.*;
import com.paymesh.backend.dto.*;
import com.paymesh.backend.entity.*;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.exception.PaymentNotFoundException;
import com.paymesh.backend.gateway.PaymentGateway;
import com.paymesh.backend.repository.*;
import com.paymesh.backend.security.accounts.SecurityAuditEventRepository;
import com.paymesh.backend.service.*;
import com.paymesh.backend.testing.BusinessJwtTestSupport;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.context.*;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class BusinessAuthorizationIntegrationTest extends BusinessJwtTestSupport {
    private static final String A = "security-a-" + UUID.randomUUID(), B = "security-b-" + UUID.randomUUID();
    private static final String SETTLEMENT = UUID.randomUUID().toString() + UUID.randomUUID();
    private static final String HMAC = UUID.randomUUID().toString() + UUID.randomUUID();
    @DynamicPropertySource static void independentSecrets(DynamicPropertyRegistry registry) {
        registry.add("paymesh.settlement.admin-token", () -> SETTLEMENT);
        registry.add("paymesh.webhooks.razorpay-secret", () -> HMAC);
    }
    @Override protected Set<String> allowedMerchants() { return Set.of(A); }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired PaymentRepository records;
    @Autowired PaymentService payments;
    @Autowired RefundService refunds;
    @Autowired GatewayTransactionService gateways;
    @Autowired GatewayTransactionRepository attempts;
    @Autowired RefundRepository refundRecords;
    @Autowired IdempotencyKeyRepository idempotency;
    @MockitoSpyBean SecurityAuditEventRepository audits;
    @Autowired com.paymesh.backend.util.PaymentRequestHasher hasher;
    @MockitoSpyBean PaymentGateway gateway;
    Identity other;
    Identity admin;

    @BeforeEach void otherActors() throws Exception { other = identity("MERCHANT", Set.of(B)); admin = identity("ADMIN", Set.of()); }
    private UUID payment(String merchant, PaymentStatus status) {
        Payment record = new Payment(merchant, "SECURITY_CUSTOMER", new BigDecimal("1000.00"), "INR", "UPI");
        record.updateStatus(status); return records.saveAndFlush(record).getPaymentId();
    }
    private String path(UUID id) { return "/api/v1/payments/" + id; }
    private PaymentRequest request(String merchant) { return new PaymentRequest(merchant, new BigDecimal("1000.00"), "INR", "CUSTOMER", "UPI"); }
    private String body(String merchant) throws Exception { return json.writeValueAsString(request(merchant)); }

    @Test
    void everyBusinessEndpointRejectsMissingJwtWithoutSideEffects() throws Exception {
        org.springframework.security.test.context.TestSecurityContextHolder.clearContext();
        UUID id = payment(A, PaymentStatus.CREATED);
        for (String suffix : List.of("", "/refund", "/refunds", "/gateway-transactions"))
            mvc.perform(get(path(id) + suffix)).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/payments").header("Idempotency-Key", "anonymous")
                .contentType(MediaType.APPLICATION_JSON).content(body(A))).andExpect(status().isUnauthorized());
        mvc.perform(post(path(id) + "/process")).andExpect(status().isUnauthorized());
        mvc.perform(post(path(id) + "/refund").header("Idempotency-Key", "anonymous")
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":200}")).andExpect(status().isUnauthorized());
        assertEquals(PaymentStatus.CREATED, records.findById(id).orElseThrow().getStatus());
        assertEquals(0, attempts.countByPaymentId(id));
        assertEquals(0, refundRecords.totalSuccessfulAmount(id).compareTo(BigDecimal.ZERO));
        verify(gateway, never()).processPayment(any(), any(), any());
    }

    @Test
    void directApplicationServicesRequireAuthenticationAndDatabaseQueriesRemainScoped() throws Exception {
        UUID id = payment(B, PaymentStatus.SUCCESS);
        SecurityContextHolder.clearContext();
        assertThrows(AuthenticationException.class, () -> payments.getPaymentById(id));
        assertThrows(AuthenticationException.class, () -> refunds.getRefundHistory(id));
        assertThrows(AuthenticationException.class, () -> gateways.getTransactionsByPaymentId(id));
        assertThrows(PaymentNotFoundException.class, () -> asCaller(() -> payments.getPaymentById(id)));
        assertThrows(PaymentNotFoundException.class, () -> asCaller(() -> refunds.refund(id, new RefundRequest(BigDecimal.ONE), "blocked")));
        // A request-supplied ADMIN flag alone cannot defeat the server-role predicate.
        assertTrue(records.findAccessibleById(id, caller.userId(), 0, true, false).isEmpty());
        assertEquals(0, refundRecords.totalSuccessfulAmount(id).signum());
    }

    @Test
    void ownerCanCreateReadProcessAndViewGatewayHistory() throws Exception {
        var created = mvc.perform(post("/api/v1/payments").with(businessJwt()).header("Idempotency-Key", "owned-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON).content(body(A))).andExpect(status().isCreated()).andReturn();
        UUID id = UUID.fromString(json.readTree(created.getResponse().getContentAsString()).get("paymentId").asText());
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isOk());
        mvc.perform(post(path(id) + "/process").with(businessJwt())).andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("SUCCESS"));
        mvc.perform(get(path(id) + "/gateway-transactions").with(businessJwt())).andExpect(status().isOk())
                .andExpect(jsonPath("$[0].status").value("SUCCESS"));
        mvc.perform(get(path(id)).with(jwt(other))).andExpect(status().isNotFound());
    }

    @Test
    void crossMerchantReadsAndMutationsConcealExistence() throws Exception {
        UUID id = payment(B, PaymentStatus.CREATED);
        for (String suffix : List.of("", "/refund", "/refunds", "/gateway-transactions"))
            mvc.perform(get(path(id) + suffix).with(businessJwt())).andExpect(status().isNotFound());
        mvc.perform(post(path(id) + "/process").with(businessJwt())).andExpect(status().isNotFound());
        mvc.perform(post(path(id) + "/refund").with(businessJwt()).header("Idempotency-Key", "cross")
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":200}")).andExpect(status().isNotFound());
        mvc.perform(get(path(UUID.randomUUID())).with(businessJwt())).andExpect(status().isNotFound());
        assertEquals(PaymentStatus.CREATED, records.findById(id).orElseThrow().getStatus());
        assertEquals(0, attempts.countByPaymentId(id));
        verify(gateway, never()).processPayment(any(), any(), any());
    }

    @Test
    void spoofedMerchantIdAndUnauthorizedReplayAreDeniedBeforeIdempotency() throws Exception {
        String key = "spoof-" + UUID.randomUUID();
        mvc.perform(post("/api/v1/payments").with(businessJwt()).header("Idempotency-Key", key)
                .contentType(MediaType.APPLICATION_JSON).content(body(B))).andExpect(status().isForbidden());
        assertTrue(idempotency.findByMerchantIdAndIdempotencyKey(B, key).isEmpty());
        UUID foreign = payment(B, PaymentStatus.CREATED);
        idempotency.saveAndFlush(new IdempotencyKey(A, key, hasher.hash(request(A)), foreign));
        mvc.perform(post("/api/v1/payments").with(businessJwt()).header("Idempotency-Key", key)
                .contentType(MediaType.APPLICATION_JSON).content(body(A))).andExpect(status().isNotFound());
        assertEquals(foreign, idempotency.findByMerchantIdAndIdempotencyKey(A, key).orElseThrow().getPaymentId());
        verify(gateway, never()).processPayment(any(), any(), any());
    }

    @Test
    void revocationRejectsOldTokenAndFreshTokenCannotReadRevokedMerchant() throws Exception {
        UUID id = payment(A, PaymentStatus.SUCCESS);
        jdbc.update("UPDATE merchant_memberships SET active = FALSE WHERE user_id = ? AND merchant_id = ?", caller.userId(), A);
        jdbc.update("UPDATE app_users SET authorization_version = authorization_version + 1 WHERE user_id = ?", caller.userId());
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isUnauthorized());
        Identity refreshed = refreshed(caller.userId(), "MERCHANT");
        mvc.perform(get(path(id)).with(jwt(refreshed))).andExpect(status().isNotFound());
        assertEquals(PaymentStatus.SUCCESS, records.findById(id).orElseThrow().getStatus());
    }

    @Test
    void activeMembershipDoesNotAuthorizeUnverifiedOrInactiveMerchant() throws Exception {
        String pending = "pending-" + UUID.randomUUID();
        jdbc.update("INSERT INTO merchants(merchant_id) VALUES (?)", pending);
        jdbc.update("INSERT INTO merchant_memberships(user_id, merchant_id, active) VALUES (?, ?, TRUE)", caller.userId(), pending);
        UUID id = payment(pending, PaymentStatus.SUCCESS);
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isNotFound());
        mvc.perform(post(path(id) + "/refund").with(businessJwt()).header("Idempotency-Key", "pending")
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":200}")).andExpect(status().isNotFound());
        mvc.perform(post("/api/v1/payments").with(businessJwt()).header("Idempotency-Key", "pending-create")
                .contentType(MediaType.APPLICATION_JSON).content(body(pending))).andExpect(status().isForbidden());
        assertFalse(jdbc.queryForObject("SELECT verified FROM merchants WHERE merchant_id = ?", Boolean.class, pending));
        jdbc.update("UPDATE merchants SET verified = TRUE, verified_by = ?, verified_at = CURRENT_TIMESTAMP WHERE merchant_id = ?",
                admin.userId(), pending);
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isNotFound()); // Verified but still inactive.
    }

    @Test
    void disabledAccountCannotReadOrRefund() throws Exception {
        UUID id = payment(A, PaymentStatus.SUCCESS);
        jdbc.update("UPDATE app_users SET enabled = FALSE, authorization_version = authorization_version + 1 WHERE user_id = ?", caller.userId());
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isUnauthorized());
        mvc.perform(post(path(id) + "/refund").with(businessJwt()).header("Idempotency-Key", "disabled")
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":200}")).andExpect(status().isUnauthorized());
        assertEquals(0, refundRecords.totalSuccessfulAmount(id).signum());
    }

    @Test
    void refundOwnershipIsCheckedBeforeReplayOrAmountConflict() throws Exception {
        UUID id = payment(B, PaymentStatus.SUCCESS);
        refundRecords.saveAndFlush(new Refund(id, new BigDecimal("200"), "existing-refund"));
        mvc.perform(post(path(id) + "/refund").with(businessJwt()).header("Idempotency-Key", "existing-refund")
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":201}")).andExpect(status().isNotFound());
        assertEquals(0, new BigDecimal("200").compareTo(refundRecords.totalSuccessfulAmount(id)));
        mvc.perform(get(path(id) + "/refunds").with(jwt(other))).andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
    }

    @Test
    void ownedPartialAndFullRefundCalculationsAndReplaysArePreserved() throws Exception {
        UUID id = payment(A, PaymentStatus.SUCCESS);
        String key = "partial-" + UUID.randomUUID();
        for (int expected : new int[]{201, 200}) mvc.perform(post(path(id) + "/refund").with(businessJwt())
                .header("Idempotency-Key", key).contentType(MediaType.APPLICATION_JSON).content("{\"amount\":200}"))
                .andExpect(status().is(expected));
        mvc.perform(post(path(id) + "/refund").with(businessJwt()).header("Idempotency-Key", "remainder")
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":800}")).andExpect(status().isCreated());
        assertEquals(PaymentStatus.REFUNDED, records.findById(id).orElseThrow().getStatus());
        mvc.perform(get(path(id) + "/refunds").with(businessJwt())).andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(2));
    }

    @Test
    void adminCrossMerchantAccessIsExplicitAuditedAndDoesNotGrantMembership() throws Exception {
        UUID id = payment(B, PaymentStatus.SUCCESS);
        mvc.perform(get(path(id)).with(jwt(admin))).andExpect(status().isOk());
        mvc.perform(post(path(id) + "/refund").with(jwt(admin)).header("Idempotency-Key", "admin-refund")
                .contentType(MediaType.APPLICATION_JSON).content("{\"amount\":200}")).andExpect(status().isCreated());
        mvc.perform(get(path(id) + "/gateway-transactions").with(jwt(admin))).andExpect(status().isOk());
        var history = audits.findByResourceIdOrderByOccurredAtAsc(id.toString());
        assertTrue(history.stream().anyMatch(event -> admin.userId().equals(event.getActorUserId()) && B.equals(event.getTargetMerchantId())
                && event.getEventType().equals("ADMIN_REFUND_CREATED_OR_REPLAYED")));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM merchant_memberships WHERE user_id = ?", Integer.class, admin.userId()));
        mvc.perform(get("/actuator/info").with(jwt(admin))).andExpect(status().isOk());
        mvc.perform(get("/actuator/info").with(businessJwt())).andExpect(status().isForbidden());
    }

    @Test
    void adminCreationStillRequiresVerifiedRegisteredMerchant() throws Exception {
        String pending = "admin-pending-" + UUID.randomUUID();
        jdbc.update("INSERT INTO merchants(merchant_id) VALUES (?)", pending);
        mvc.perform(post("/api/v1/payments").with(jwt(admin)).header("Idempotency-Key", "admin-pending")
                .contentType(MediaType.APPLICATION_JSON).content(body(pending))).andExpect(status().isForbidden());
        mvc.perform(post("/api/v1/payments").with(jwt(admin)).header("Idempotency-Key", "admin-missing")
                .contentType(MediaType.APPLICATION_JSON).content(body("unknown-" + UUID.randomUUID()))).andExpect(status().isNotFound());
        mvc.perform(post("/api/v1/payments").with(jwt(admin)).header("Idempotency-Key", "admin-verified-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON).content(body(B))).andExpect(status().isCreated());
    }

    @Test
    void multipleVerifiedMembershipsAreSupportedWithoutTrustingRequestMerchantId() throws Exception {
        UUID id = payment(B, PaymentStatus.SUCCESS);
        jdbc.update("INSERT INTO merchant_memberships(user_id, merchant_id, active) VALUES (?, ?, TRUE)", caller.userId(), B);
        jdbc.update("UPDATE app_users SET authorization_version = authorization_version + 1 WHERE user_id = ?", caller.userId());
        Identity refreshed = refreshed(caller.userId(), "MERCHANT");
        mvc.perform(get(path(id)).with(jwt(refreshed))).andExpect(status().isOk());
        mvc.perform(post("/api/v1/payments").with(jwt(refreshed)).header("Idempotency-Key", "multi-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON).content(body(B))).andExpect(status().isCreated());
    }

    @Test
    void webhookHmacAndSettlementTokenRemainIndependentOfJwt() throws Exception {
        UUID id = payment(A, PaymentStatus.PROCESSING), gatewayId = UUID.randomUUID();
        GatewayTransaction attempt = new GatewayTransaction(id, "MOCK_RAZORPAY");
        attempt.updateResult(gatewayId, "UNKNOWN", null, null); attempts.saveAndFlush(attempt);
        String body = json.writeValueAsString(Map.of("eventId", "security-" + UUID.randomUUID(), "paymentId", id,
                "gatewayTransactionId", gatewayId, "status", "SUCCESS", "occurredAt", Instant.now()));
        String timestamp = Long.toString(Instant.now().getEpochSecond());
        mvc.perform(post("/api/v1/webhooks/mock-razorpay").with(jwt(admin))
                .header("X-Paymesh-Timestamp", timestamp).header("X-Paymesh-Signature", "0".repeat(64))
                .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isUnauthorized());
        Mac mac = Mac.getInstance("HmacSHA256"); mac.init(new SecretKeySpec(HMAC.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        String signature = HexFormat.of().formatHex(mac.doFinal((timestamp + "." + body).getBytes(StandardCharsets.UTF_8)));
        mvc.perform(post("/api/v1/webhooks/mock-razorpay").header("Authorization", "Bearer invalid-jwt")
                .header("X-Paymesh-Timestamp", timestamp).header("X-Paymesh-Signature", signature)
                .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isOk());
        assertEquals(PaymentStatus.SUCCESS, records.findById(id).orElseThrow().getStatus());
        String auditPath = "/api/v1/settlement/payments/" + id + "/webhooks";
        mvc.perform(get(auditPath)).andExpect(status().isUnauthorized());
        mvc.perform(get(auditPath).with(jwt(admin))).andExpect(status().isUnauthorized());
        mvc.perform(get(auditPath).header("Authorization", "Bearer " + SETTLEMENT)).andExpect(status().isOk());
        mvc.perform(get("/api/v1/payments/health").header("Authorization", "Bearer invalid-jwt")).andExpect(status().isOk());
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
    }

    @Test
    void revocationDuringAcceptedProcessingDoesNotStrandOrReverseFinancialOutcome() throws Exception {
        UUID id = payment(A, PaymentStatus.CREATED);
        doAnswer(invocation -> {
            assertFalse(org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive());
            assertTrue(jdbc.queryForObject("SELECT pg_try_advisory_xact_lock(hashtextextended('paymesh:account-administration', 0))", Boolean.class));
            jdbc.update("UPDATE merchant_memberships SET active = FALSE WHERE user_id = ? AND merchant_id = ?", caller.userId(), A);
            jdbc.update("UPDATE app_users SET authorization_version = authorization_version + 1 WHERE user_id = ?", caller.userId());
            return invocation.callRealMethod();
        }).when(gateway).processPayment(eq(id), any(), eq("INR"));
        mvc.perform(post(path(id) + "/process").with(businessJwt())).andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("SUCCESS"));
        assertEquals(PaymentStatus.SUCCESS, records.findById(id).orElseThrow().getStatus());
        mvc.perform(get(path(id)).with(businessJwt())).andExpect(status().isUnauthorized());
        mvc.perform(get(path(id)).with(jwt(refreshed(caller.userId(), "MERCHANT")))).andExpect(status().isNotFound());
    }

    @Test
    void failedAdminAuditRollsBackRefundAndPaymentChange() throws Exception {
        UUID id = payment(B, PaymentStatus.SUCCESS);
        doThrow(new IllegalStateException("Simulated audit failure")).when(audits)
                .saveAndFlush(argThat((com.paymesh.backend.security.accounts.SecurityAuditEvent event) ->
                        event != null && event.getEventType().equals("ADMIN_REFUND_CREATED_OR_REPLAYED")));
        assertThrows(IllegalStateException.class, () -> as(admin,
                () -> refunds.refund(id, new RefundRequest(new BigDecimal("1000")), "audit-rollback")));
        assertEquals(0, refundRecords.totalSuccessfulAmount(id).signum());
        assertEquals(PaymentStatus.SUCCESS, records.findById(id).orElseThrow().getStatus());
    }
}
