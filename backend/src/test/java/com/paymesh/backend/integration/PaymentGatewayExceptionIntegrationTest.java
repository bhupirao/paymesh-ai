
package com.paymesh.backend.integration;

import com.paymesh.backend.exception.PaymentGatewayException;
import com.paymesh.backend.service.PaymentOrchestrationService;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class PaymentGatewayExceptionIntegrationTest extends com.paymesh.backend.testing.BusinessJwtTestSupport {
    @Override protected java.util.Set<String> allowedMerchants() { return java.util.Set.of("EXCEPTION_TEST"); }

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private PaymentOrchestrationService orchestrationService;

    @Test
    void shouldReturn503WhenGatewayThrowsException()
            throws Exception {

        UUID paymentId = UUID.randomUUID();

        when(orchestrationService.processPayment(eq(paymentId)))
                .thenThrow(new PaymentGatewayException(
                        "Payment gateway processing failed; " +
                                "payment outcome requires reconciliation",
                        new RuntimeException(
                                "Gateway connection failed"
                        )
                ));

        mockMvc.perform(
                        post("/api/v1/payments/{paymentId}/process",
                                paymentId).with(businessJwt())
                                .accept(MediaType.APPLICATION_JSON)
                )
                .andExpect(status().isServiceUnavailable())
                .andExpect(content().contentTypeCompatibleWith(
                        MediaType.APPLICATION_JSON
                ))
                .andExpect(jsonPath("$.status").value(503))
                .andExpect(jsonPath("$.error")
                        .value("Payment Gateway Unavailable"))
                .andExpect(jsonPath("$.message")
                        .value(
                                "Payment gateway processing failed; " +
                                        "payment outcome requires reconciliation"
                        ))
                .andExpect(jsonPath("$.path")
                        .value(
                                "/api/v1/payments/" +
                                        paymentId + "/process"
                        ))
                .andExpect(jsonPath("$.timestamp").exists());

        verify(orchestrationService, times(1))
                .processPayment(paymentId);
    }
}
