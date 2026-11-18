package com.paymesh.backend.security;

import static org.junit.jupiter.api.Assertions.*;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "paymesh.jwt.private-key-file=", "paymesh.jwt.public-key-file=", "paymesh.jwt.issuer=", "paymesh.jwt.audience=",
        "paymesh.webhooks.razorpay-secret=01234567890123456789012345678901",
        "paymesh.webhooks.stripe-secret=abcdefghijklmnopqrstuvwxyzABCDEF",
        "spring.datasource.hikari.maximum-pool-size=2",
        "paymesh.settlement.scheduling-enabled=false"})
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_CLASS)
class BoundedRequestBodyHttpIntegrationTest {
    @LocalServerPort int port;
    @Autowired JdbcTemplate jdbc;
    private final HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(5)).build();

    @Test void unknownLengthOversizedLoginAndBothWebhooksReturn413() throws Exception {
        assertEquals(413, chunked("/api/v1/auth/login", "x".repeat(4097).getBytes(StandardCharsets.UTF_8)).statusCode());
        long events = jdbc.queryForObject("SELECT count(*) FROM webhook_events", Long.class);
        for (String provider : new String[]{"mock-razorpay", "mock-stripe"}) {
            HttpResponse<String> response = chunked("/api/v1/webhooks/" + provider,
                    "x".repeat(65537).getBytes(StandardCharsets.UTF_8));
            assertEquals(413, response.statusCode(), provider);
        }
        assertEquals(events, jdbc.queryForObject("SELECT count(*) FROM webhook_events", Long.class));
    }

    @Test void limitsUseUtf8BytesAndRejectedWebhookHasNoDatabaseEffects() throws Exception {
        // 2049 two-byte characters exceed 4096 bytes although the Java string is only 2049 chars.
        assertEquals(413, chunked("/api/v1/auth/login", "é".repeat(2049).getBytes(StandardCharsets.UTF_8)).statusCode());
        long events = jdbc.queryForObject("SELECT count(*) FROM webhook_events", Long.class);
        HttpResponse<String> response = chunked("/api/v1/webhooks/mock-razorpay",
                "é".repeat(32769).getBytes(StandardCharsets.UTF_8));
        assertEquals(413, response.statusCode());
        assertEquals(events, jdbc.queryForObject("SELECT count(*) FROM webhook_events", Long.class));
    }

    @Test void servletLimitPrecedesMvcAndLoginRateLimiterStillReturns429() throws Exception {
        for (int i = 0; i < 10; i++) {
            HttpResponse<String> response = chunked("/api/v1/auth/login",
                    "{\"login\":\"missing\",\"password\":\"invalid\"}".getBytes(StandardCharsets.UTF_8));
            assertEquals(503, response.statusCode(), "configured-key absence fails closed before credential lookup");
        }
        assertEquals(429, chunked("/api/v1/auth/login", "{}".getBytes(StandardCharsets.UTF_8)).statusCode());
        // The size filter is before the security chain: it rejects a bounded oversized body
        // even after the login bucket is exhausted, without invoking MVC.
        assertEquals(413, chunked("/api/v1/auth/login", new byte[4097]).statusCode());
    }

    private HttpResponse<String> chunked(String path, byte[] bytes) throws Exception {
        AtomicInteger supplied = new AtomicInteger();
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                .timeout(Duration.ofSeconds(15)).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofInputStream(() -> {
                    supplied.incrementAndGet();
                    return new java.io.ByteArrayInputStream(bytes);
                })).build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(1, supplied.get(), "request body publisher should be consumed once");
        return response;
    }
}
