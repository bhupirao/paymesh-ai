
package com.paymesh.backend.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;

public record PaymentRequest(

        @NotBlank(message = "Merchant ID is required")
        String merchantId,

        @NotNull(message = "Amount is required")
        @DecimalMin(value = "0.01", message = "Amount must be greater than zero")
        @Digits(integer = 12, fraction = 2)
        BigDecimal amount,

        @NotBlank(message = "Currency is required")
        String currency,

        @NotBlank(message = "Customer ID is required")
        String customerId,

        @NotBlank(message = "Payment method is required")
        String paymentMethod

) {
}
