package com.paymesh.backend.settlement;

import com.paymesh.backend.gateway.*;
import java.math.BigDecimal;
import java.util.UUID;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class RoutingLedgerTest {
    @Test
    void routingRemainsCurrencyBasedAndPersistsOnlySimulatedResults() {
        var ledger = mock(SimulatedGatewayLedger.class);
        var router = new RoutingPaymentGateway(new MockRazorpayGateway(), new MockStripeGateway(), ledger);
        UUID inr = UUID.randomUUID();
        UUID usd = UUID.randomUUID();
        var razorpay = router.processPayment(inr, BigDecimal.TEN, "INR");
        var stripe = router.processPayment(usd, BigDecimal.TEN, "USD");
        assertEquals("MOCK_RAZORPAY", razorpay.gatewayName());
        assertEquals("MOCK_STRIPE", stripe.gatewayName());
        assertEquals(GatewayStatus.SUCCESS, razorpay.status());
        assertEquals(GatewayStatus.SUCCESS, stripe.status());
        verify(ledger).record(inr, razorpay);
        verify(ledger).record(usd, stripe);
        assertEquals(GatewayStatus.FAILED, router.processPayment(UUID.randomUUID(), BigDecimal.TEN, "EUR").status());
    }
}
