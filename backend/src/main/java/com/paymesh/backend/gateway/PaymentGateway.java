
package com.paymesh.backend.gateway;

import java.math.BigDecimal;
import java.util.UUID;

public interface PaymentGateway {

    String getGatewayName();

    GatewayResponse processPayment(
            UUID paymentId,
            BigDecimal amount,
            String currency
    );
}
