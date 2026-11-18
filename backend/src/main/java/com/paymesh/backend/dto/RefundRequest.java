package com.paymesh.backend.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

public record RefundRequest(
        @NotNull(message = "Refund amount is required")
        @DecimalMin(value = "0.01", message = "Refund amount must be positive")
        @Digits(integer = 17, fraction = 2)
        BigDecimal amount
) {}
