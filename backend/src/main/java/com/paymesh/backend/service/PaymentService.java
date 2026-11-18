
package com.paymesh.backend.service;

import com.paymesh.backend.dto.PaymentCreationResult;
import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.enums.PaymentStatus;

import java.util.UUID;

public interface PaymentService {

    PaymentCreationResult createPayment(
            PaymentRequest request,
            String idempotencyKey
    );

    PaymentResponse getPaymentById(UUID paymentId);

    PaymentResponse updatePaymentStatus(
            UUID paymentId,
            PaymentStatus newStatus
    );
    void claimPaymentForProcessing(UUID paymentId);
}
