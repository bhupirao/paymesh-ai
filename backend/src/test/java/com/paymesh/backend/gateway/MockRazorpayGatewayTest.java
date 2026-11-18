
package com.paymesh.backend.gateway;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class MockRazorpayGatewayTest {

    private MockRazorpayGateway gateway;

    @BeforeEach
    void setUp() {
        gateway = new MockRazorpayGateway();
    }

    @Test
    void shouldProcessValidINRPaymentSuccessfully() {

        GatewayResponse response = gateway.processPayment(
                UUID.randomUUID(),
                new BigDecimal("500.00"),
                "INR"
        );

        assertEquals(GatewayStatus.SUCCESS, response.status());
        assertEquals("MOCK_RAZORPAY", response.gatewayName());
        assertNotNull(response.gatewayTransactionId());
        assertNull(response.errorCode());
        assertNull(response.errorMessage());
    }

    @Test
    void shouldRejectZeroAmount() {

        GatewayResponse response = gateway.processPayment(
                UUID.randomUUID(),
                BigDecimal.ZERO,
                "INR"
        );

        assertEquals(GatewayStatus.FAILED, response.status());
        assertEquals("INVALID_AMOUNT", response.errorCode());
        assertNull(response.gatewayTransactionId());
    }

    @Test
    void shouldRejectNegativeAmount() {

        GatewayResponse response = gateway.processPayment(
                UUID.randomUUID(),
                new BigDecimal("-100.00"),
                "INR"
        );

        assertEquals(GatewayStatus.FAILED, response.status());
        assertEquals("INVALID_AMOUNT", response.errorCode());
    }

    @Test
    void shouldRejectUnsupportedCurrency() {

        GatewayResponse response = gateway.processPayment(
                UUID.randomUUID(),
                new BigDecimal("500.00"),
                "USD"
        );

        assertEquals(GatewayStatus.FAILED, response.status());
        assertEquals("UNSUPPORTED_CURRENCY", response.errorCode());
    }

    @Test
    void shouldAcceptLowercaseINR() {

        GatewayResponse response = gateway.processPayment(
                UUID.randomUUID(),
                new BigDecimal("500.00"),
                "inr"
        );

        assertEquals(GatewayStatus.SUCCESS, response.status());
    }
}
