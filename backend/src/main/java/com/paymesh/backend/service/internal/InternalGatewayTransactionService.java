package com.paymesh.backend.service.internal;

import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.gateway.GatewayResponse;
import java.util.List;
import java.util.UUID;

/** Trusted financial core, never an HTTP authorization boundary. */
public interface InternalGatewayTransactionService {
    GatewayTransaction initiateTransaction(UUID paymentId, String gatewayName);
    GatewayTransaction completeTransaction(UUID transactionId, GatewayResponse gatewayResponse);
    GatewayTransaction markTransactionUnknown(UUID transactionId, String errorMessage);
    List<GatewayTransaction> getTransactionsByPaymentId(UUID paymentId);
}
