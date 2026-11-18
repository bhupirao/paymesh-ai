package com.paymesh.backend.investigation;

import com.fasterxml.jackson.databind.*;
import com.paymesh.backend.entity.*;
import com.paymesh.backend.repository.*;
import com.paymesh.backend.testing.BusinessJwtTestSupport;
import java.math.BigDecimal;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest @AutoConfigureMockMvc
class InvestigationIntegrationTest extends BusinessJwtTestSupport {
    private static final String MERCHANT = "investigation-" + UUID.randomUUID();
    @Override protected Set<String> allowedMerchants() { return Set.of(MERCHANT); }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired EvidenceCollector collector;
    @Autowired PaymentRepository payments;
    @Autowired GatewayTransactionRepository gateways;
    @Autowired RefundRepository refunds;
    @MockitoBean AiInvestigationClient client;
    @org.springframework.test.context.bean.override.mockito.MockitoSpyBean com.paymesh.backend.security.business.BusinessAccess access;
    UUID payment;
    @BeforeEach void fixture() {
        payment = payments.saveAndFlush(new Payment(MERCHANT,"PRIVATE_CUSTOMER",new BigDecimal("1234567890.12"),"INR","UPI")).getPaymentId();
    }
    String path(UUID id) { return "/api/v1/payments/"+id+"/investigate"; }
    @Test void merchantAndAdminUseDetachedAuthorizedSnapshotWithoutMutations() throws Exception {
        AtomicReference<JsonNode> captured = new AtomicReference<>();
        when(client.investigate(any())).thenAnswer(call -> {
            assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
            assertFalse(TransactionSynchronizationManager.hasResource(jdbc.getDataSource()));
            captured.set(call.getArgument(0)); return json.createObjectNode().put("analysisMode","RAG_LLM");
        });
        mvc.perform(post(path(payment)).with(businessJwt())).andExpect(status().isOk())
                .andExpect(jsonPath("$.evidenceProvenance.source").value("JAVA_AUTHORIZED_DATABASE_SNAPSHOT"));
        assertEquals("1234567890.12",captured.get().get("amount").textValue());
        assertFalse(captured.get().toString().contains("PRIVATE_CUSTOMER"));
        for(String field:List.of("gatewayTransactions","refunds","webhooks","reconciliation")) assertEquals(0,captured.get().get(field).size());
        mvc.perform(post(path(payment)).with(jwt(identity("ADMIN",Set.of())))).andExpect(status().isOk());
        assertEquals("CREATED", payments.findById(payment).orElseThrow().getStatus().name());
        assertEquals(0,refunds.findAllByPaymentIdOrderByCreatedAtAscRefundIdAsc(payment).size());
    }
    @Test void unauthorizedMissingAndCrossMerchantNeverCallPython() throws Exception {
        mvc.perform(post(path(payment))).andExpect(status().isUnauthorized());
        mvc.perform(post(path(payment)).header("Authorization","Bearer invalid")).andExpect(status().isUnauthorized());
        mvc.perform(post(path(payment)).with(jwt(identity("MERCHANT",Set.of("other-"+UUID.randomUUID()))))).andExpect(status().isNotFound());
        mvc.perform(post(path(UUID.randomUUID())).with(businessJwt())).andExpect(status().isNotFound());
        jdbc.update("UPDATE merchants SET active = false WHERE merchant_id = ?",MERCHANT);
        try { mvc.perform(post(path(payment)).with(businessJwt())).andExpect(status().isNotFound()); }
        finally { jdbc.update("UPDATE merchants SET active = true WHERE merchant_id = ?",MERCHANT); }
        verifyNoInteractions(client);
    }
    @Test void actualEvidenceIsProjectedWithoutProviderMessagesOrInventedTimeout() throws Exception {
        GatewayTransaction g = new GatewayTransaction(payment,"MOCK_RAZORPAY"); UUID tx=UUID.randomUUID();
        g.updateResult(tx,"SUCCESS","SECRET_CODE","PRIVATE_PROVIDER_MESSAGE"); gateways.saveAndFlush(g);
        refunds.saveAndFlush(new Refund(payment,new BigDecimal("20.10"),"PRIVATE_KEY"));
        jdbc.update("INSERT INTO webhook_events(id,gateway,event_id,payment_id,payload,status,occurred_at) VALUES (?, 'MOCK_RAZORPAY', ?, ?, ?, 'PROCESSED', CURRENT_TIMESTAMP)",UUID.randomUUID(),UUID.randomUUID().toString(),payment,
                json.writeValueAsString(Map.of("gatewayTransactionId",tx,"status","SUCCESS","private","PRIVATE_RAW")));
        jdbc.update("INSERT INTO reconciliation_attempts(id,payment_id,attempt,outcome,status_before,status_after,result) VALUES (?, ?, 1, 'SUCCESS','PROCESSING','SUCCESS','RESOLVED')",UUID.randomUUID(),payment);
        var e=asCaller(()->collector.collect(payment)).evidence();
        assertEquals("SUCCESS",e.at("/gatewayTransactions/0/status").asText());
        assertTrue(e.at("/gatewayTransactions/0/errorCode").isNull());
        assertEquals("20.10",e.at("/refunds/0/amount").asText());
        assertEquals(tx.toString(),e.at("/webhooks/0/gatewayTransactionId").asText());
        assertEquals("PROCESSING",e.at("/reconciliation/0/statusBefore").asText());
        for(String secret:List.of("PRIVATE_PROVIDER_MESSAGE","SECRET_CODE","PRIVATE_KEY","PRIVATE_RAW","TIMEOUT")) assertFalse(e.toString().contains(secret));
    }
    @Test void snapshotUsesReadOnlyRepeatableReadTransaction() throws Exception {
        doAnswer(call -> {
            assertTrue(TransactionSynchronizationManager.isActualTransactionActive());
            assertTrue(TransactionSynchronizationManager.isCurrentTransactionReadOnly());
            assertEquals("repeatable read",jdbc.queryForObject("SHOW transaction_isolation",String.class));
            assertEquals("on",jdbc.queryForObject("SHOW transaction_read_only",String.class));
            return call.callRealMethod();
        }).when(org.springframework.test.util.AopTestUtils.<com.paymesh.backend.security.business.BusinessAccess>getUltimateTargetObject(access)).actor();
        asCaller(()->collector.collect(payment));
    }
    @Test void busyRuntimeReturnsSanitizedErrorWithoutSecondRemoteCall() throws Exception {
        var controller = new InvestigationController(collector,client);
        when(client.investigate(any())).thenAnswer(call -> {
            InvestigationFailure error=assertThrows(InvestigationFailure.class,()->controller.investigate(payment));
            assertEquals(503,error.status());
            return json.createObjectNode();
        });
        asCaller(()->controller.investigate(payment));
        verify(client,times(1)).investigate(any());
    }
    @Test void unsupportedGatewayMeansUnavailableRatherThanEmpty() throws Exception {
        gateways.saveAndFlush(new GatewayTransaction(payment,"MOCK_RAZORPAY"));
        var snapshot=asCaller(()->collector.collect(payment));
        assertTrue(snapshot.evidence().get("gatewayTransactions").isNull());
        assertTrue(snapshot.unavailable().containsKey("gatewayTransactions"));
        assertTrue(snapshot.evidence().get("refunds").isArray());
    }
    @Test void overflowRejectsWholeInvestigationBeforeRemoteCall() throws Exception {
        jdbc.update("INSERT INTO refunds(refund_id,payment_id,amount,status,created_at) SELECT gen_random_uuid(), ?, 0.01, 'SUCCESS', CURRENT_TIMESTAMP FROM generate_series(1,101)",payment);
        mvc.perform(post(path(payment)).with(businessJwt())).andExpect(status().isUnprocessableEntity());
        verifyNoInteractions(client);
    }
}
