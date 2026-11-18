
package com.paymesh.backend.service;

import com.paymesh.backend.dto.PaymentResponse;

import java.util.UUID;

public interface PaymentOrchestrationService {

    PaymentResponse processPayment(UUID paymentId);
}
