
package com.paymesh.backend.dto;

public record PaymentCreationResult(
        PaymentResponse payment,
        boolean created
) {
}
