
package com.paymesh.backend.service;

import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.gateway.GatewayResponse;

import java.util.List;
import java.util.UUID;

public interface GatewayTransactionService {

    GatewayTransaction initiateTransaction(
            UUID paymentId,
            String gatewayName
    );

    GatewayTransaction completeTransaction(
            UUID transactionId,
            GatewayResponse gatewayResponse
    );

    GatewayTransaction markTransactionUnknown(
            UUID transactionId,
            String errorMessage
    );

    List<GatewayTransaction> getTransactionsByPaymentId(
            UUID paymentId
    );
}
