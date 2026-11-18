
package com.paymesh.backend.integration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import com.paymesh.backend.repository.IdempotencyKeyRepository;
import org.junit.jupiter.api.Assertions;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;

import java.util.UUID;

import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

@SpringBootTest
@AutoConfigureMockMvc
class PaymentIdempotencyIntegrationTest extends com.paymesh.backend.testing.BusinessJwtTestSupport {
    @Override protected java.util.Set<String> allowedMerchants() { return java.util.Set.of("MERCHANT_TEST","MERCHANT_CONCURRENT_TEST"); }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private IdempotencyKeyRepository idempotencyKeyRepository;


    @Test
    void shouldReturnSamePaymentForRepeatedIdempotencyKey()
            throws Exception {

        String idempotencyKey = "RETRY-" + UUID.randomUUID();

        String requestBody = """
            {
                "merchantId": "MERCHANT_TEST",
                "amount": 1500.00,
                "currency": "INR",
                "customerId": "CUSTOMER_TEST",
                "paymentMethod": "UPI"
            }
            """;

        // First request: creates a new payment
        String firstResponse = mockMvc.perform(
                        post("/api/v1/payments").with(businessJwt())
                                .header("Idempotency-Key", idempotencyKey)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(requestBody)
                )
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();

        // Second request: returns the existing payment
        String secondResponse = mockMvc.perform(
                        post("/api/v1/payments").with(businessJwt())
                                .header("Idempotency-Key", idempotencyKey)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(requestBody)
                )
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        JsonNode firstJson = objectMapper.readTree(firstResponse);
        JsonNode secondJson = objectMapper.readTree(secondResponse);

        Assertions.assertEquals(
                firstJson.get("paymentId").asText(),
                secondJson.get("paymentId").asText(),
                "Repeated requests must return the same payment ID"
        );
    }


    @Test
    void shouldCreateOnlyOnePaymentForTenConcurrentRequests()
            throws Exception {

        String merchantId = "MERCHANT_CONCURRENT_TEST";
        String idempotencyKey = "CONCURRENT-" + UUID.randomUUID();

        String requestBody = """
            {
                "merchantId": "MERCHANT_CONCURRENT_TEST",
                "amount": 3500.00,
                "currency": "INR",
                "customerId": "CUSTOMER_201",
                "paymentMethod": "UPI"
            }
            """;

        int requestCount = 10;

        ExecutorService executor =
                Executors.newFixedThreadPool(requestCount);

        CountDownLatch ready = new CountDownLatch(requestCount);
        CountDownLatch start = new CountDownLatch(1);

        try {
            List<Future<org.springframework.test.web.servlet.MvcResult>>
                    futures = new ArrayList<>();

            for (int i = 0; i < requestCount; i++) {

                futures.add(executor.submit(() -> {

                    ready.countDown();
                    start.await();

                    return mockMvc.perform(
                            post("/api/v1/payments").with(businessJwt())
                                    .header("Idempotency-Key", idempotencyKey)
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .content(requestBody)
                    ).andReturn();
                }));
            }

            Assertions.assertTrue(
                    ready.await(10, TimeUnit.SECONDS),
                    "Workers did not become ready"
            );

            start.countDown();

            List<String> paymentIds = new ArrayList<>();

            int createdCount = 0;
            int replayCount = 0;

            for (Future<org.springframework.test.web.servlet.MvcResult>
                    future : futures) {

                var response = future.get(30, TimeUnit.SECONDS)
                        .getResponse();

                int statusCode = response.getStatus();

                if (statusCode == 201) {
                    createdCount++;
                } else if (statusCode == 200) {
                    replayCount++;
                } else {
                    Assertions.fail(
                            "Unexpected HTTP status: " + statusCode
                                    + " body: " + response.getContentAsString()
                    );
                }

                JsonNode json = objectMapper.readTree(
                        response.getContentAsString()
                );

                paymentIds.add(json.get("paymentId").asText());
            }

            Assertions.assertEquals(1, createdCount);
            Assertions.assertEquals(9, replayCount);

            Assertions.assertEquals(
                    1,
                    paymentIds.stream().distinct().count(),
                    "All requests must return the same payment ID"
            );

            Assertions.assertEquals(
                    1L,
                    idempotencyKeyRepository
                            .findByMerchantIdAndIdempotencyKey(
                                    merchantId,
                                    idempotencyKey
                            )
                            .stream()
                            .count()
            );

        } finally {
            start.countDown();
            executor.shutdownNow();
        }
    }

}
