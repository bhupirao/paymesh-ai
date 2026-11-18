
package com.paymesh.backend.gateway;

import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.UUID;

@Component
public class MockRazorpayGateway implements PaymentGateway {

    @Override
    public String getGatewayName() {
        return "MOCK_RAZORPAY";
    }

    @Override
    public GatewayResponse processPayment(
            UUID paymentId,
            BigDecimal amount,
            String currency
    ) {

        if (amount == null || amount.signum() <= 0) {
            return new GatewayResponse(
                    null,
                    getGatewayName(),
                    GatewayStatus.FAILED,
                    "INVALID_AMOUNT",
                    "Payment amount must be greater than zero"
            );
        }

        if (currency == null ||
                !currency.equalsIgnoreCase("INR")) {
            return new GatewayResponse(
                    null,
                    getGatewayName(),
                    GatewayStatus.FAILED,
                    "UNSUPPORTED_CURRENCY",
                    "Mock Razorpay supports INR only"
            );
        }

        return new GatewayResponse(
                UUID.randomUUID(),
                getGatewayName(),
                GatewayStatus.SUCCESS,
                null,
                null
        );
    }
}
