package com.paymesh.backend.gateway;
import org.springframework.stereotype.Component;
import java.math.BigDecimal;
import java.util.UUID;
@Component
public class MockStripeGateway implements PaymentGateway {
    public String getGatewayName() { return "MOCK_STRIPE"; }
    public GatewayResponse processPayment(UUID paymentId, BigDecimal amount, String currency) {
        if (amount == null || amount.signum() <= 0) return new GatewayResponse(null,getGatewayName(),GatewayStatus.FAILED,"INVALID_AMOUNT","Amount must be positive");
        if (!"USD".equalsIgnoreCase(currency)) return new GatewayResponse(null,getGatewayName(),GatewayStatus.FAILED,"UNSUPPORTED_CURRENCY","Mock Stripe supports USD only");
        return new GatewayResponse(UUID.randomUUID(),getGatewayName(),GatewayStatus.SUCCESS,null,null);
    }
}
