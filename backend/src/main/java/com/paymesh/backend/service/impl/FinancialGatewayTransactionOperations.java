
package com.paymesh.backend.service.impl;

import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.gateway.GatewayResponse;
import com.paymesh.backend.repository.GatewayTransactionRepository;
import com.paymesh.backend.repository.PaymentRepository;
import com.paymesh.backend.settlement.OutcomeApplier;
import jakarta.persistence.EntityManager;
import com.paymesh.backend.service.internal.InternalGatewayTransactionService;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class FinancialGatewayTransactionOperations
        implements InternalGatewayTransactionService {

    private final GatewayTransactionRepository repository;
    private final PaymentRepository payments;
    private final EntityManager entityManager;

    public FinancialGatewayTransactionOperations(
            GatewayTransactionRepository repository,
            PaymentRepository payments,
            EntityManager entityManager
    ) {
        this.repository = repository;
        this.payments = payments;
        this.entityManager = entityManager;
    }

    @Override
    @Transactional
    public GatewayTransaction initiateTransaction(
            UUID paymentId,
            String gatewayName
    ) {

        GatewayTransaction transaction =
                new GatewayTransaction(
                        paymentId,
                        gatewayName
                );

        return repository.save(transaction);
    }

    @Override
    @Transactional
    public GatewayTransaction completeTransaction(
            UUID transactionId,
            GatewayResponse gatewayResponse
    ) {

        GatewayTransaction transaction = lockedTransaction(transactionId);
        if (OutcomeApplier.terminal(transaction.getStatus())) return transaction;

        transaction.setGatewayName(gatewayResponse.gatewayName());
        transaction.updateResult(
                gatewayResponse.gatewayTransactionId(),
                gatewayResponse.status().name(),
                gatewayResponse.errorCode(),
                gatewayResponse.errorMessage()
        );

        return repository.save(transaction);
    }

    @Override
    @Transactional
    public GatewayTransaction markTransactionUnknown(
            UUID transactionId,
            String errorMessage
    ) {

        GatewayTransaction transaction = lockedTransaction(transactionId);
        if (OutcomeApplier.terminal(transaction.getStatus())) return transaction;

        transaction.updateResult(
                transaction.getGatewayTransactionId(),
                "UNKNOWN",
                "GATEWAY_EXCEPTION",
                errorMessage
        );

        return repository.save(transaction);
    }

    @Override
    @Transactional(readOnly = true)
    public List<GatewayTransaction> getTransactionsByPaymentId(
            UUID paymentId
    ) {

        return repository
                .findByPaymentIdOrderByCreatedAtDesc(paymentId);
    }

    private GatewayTransaction lockedTransaction(UUID transactionId) {
        GatewayTransaction transaction = repository.findById(transactionId)
                .orElseThrow(() -> new IllegalArgumentException("Gateway transaction not found: " + transactionId));
        payments.findByIdForSettlement(transaction.getPaymentId())
                .orElseThrow(() -> new IllegalArgumentException("Payment not found"));
        // Reload after waiting on the lock; a webhook may have completed this attempt.
        entityManager.refresh(transaction);
        return transaction;
    }
}
