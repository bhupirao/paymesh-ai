
package com.paymesh.backend.dto;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record PaymentResponse(
        UUID paymentId,
        String merchantId,
        BigDecimal amount,
        String currency,
        String customerId,
        String paymentMethod,
        String status,
        Instant createdAt
) {
}
