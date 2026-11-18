
package com.paymesh.backend.service.impl;

import com.paymesh.backend.dto.PaymentCreationResult;
import com.paymesh.backend.dto.PaymentRequest;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.entity.IdempotencyKey;
import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.exception.IdempotencyConflictException;
import com.paymesh.backend.exception.PaymentNotFoundException;
import com.paymesh.backend.repository.IdempotencyKeyRepository;
import com.paymesh.backend.repository.IdempotencyLockManager;
import com.paymesh.backend.repository.PaymentRepository;
import com.paymesh.backend.service.internal.InternalPaymentService;
import com.paymesh.backend.util.PaymentRequestHasher;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.service.PaymentStatusTransitionValidator;

import org.springframework.stereotype.Service;
import com.paymesh.backend.exception.InvalidPaymentStateException;
import org.springframework.transaction.annotation.Transactional;
import java.util.UUID;

@Service
public class FinancialPaymentOperations implements InternalPaymentService {

    private final PaymentRepository paymentRepository;
    private final IdempotencyKeyRepository idempotencyKeyRepository;
    private final IdempotencyLockManager lockManager;
    private final PaymentRequestHasher requestHasher;
    private final PaymentStatusTransitionValidator transitionValidator;

    public FinancialPaymentOperations(
            PaymentRepository paymentRepository,
            IdempotencyKeyRepository idempotencyKeyRepository,
            IdempotencyLockManager lockManager,
            PaymentRequestHasher requestHasher,PaymentStatusTransitionValidator transitionValidator
    ) {
        this.paymentRepository = paymentRepository;
        this.idempotencyKeyRepository = idempotencyKeyRepository;
        this.lockManager = lockManager;
        this.requestHasher = requestHasher;
        this.transitionValidator = transitionValidator;
    }

    @Override
    @Transactional
    public PaymentCreationResult createPayment(
            PaymentRequest request,
            String idempotencyKey
    ) {
        if (idempotencyKey == null
                || idempotencyKey.isBlank()
                || idempotencyKey.length() > 255) {
            throw new IllegalArgumentException(
                    "Idempotency-Key must contain 1 to 255 characters"
            );
        }

        String requestHash = requestHasher.hash(request);

        lockManager.lock(request.merchantId(), idempotencyKey);

        var existingRecord = idempotencyKeyRepository
                .findByMerchantIdAndIdempotencyKey(
                        request.merchantId(),
                        idempotencyKey
                );

        if (existingRecord.isPresent()) {

            IdempotencyKey record = existingRecord.get();

            if (!record.getRequestHash().equals(requestHash)) {
                throw new IdempotencyConflictException(
                        "Idempotency key already used with a different payment request"
                );
            }

            Payment existingPayment = paymentRepository
                    .findById(record.getPaymentId())
                    .orElseThrow(() ->
                            new PaymentNotFoundException(
                                    record.getPaymentId()
                            )
                    );

            return new PaymentCreationResult(
                    toResponse(existingPayment),
                    false
            );

        }

        Payment payment = new Payment(
                request.merchantId(),
                request.customerId(),
                request.amount(),
                request.currency(),
                request.paymentMethod()
        );

        Payment savedPayment = paymentRepository.save(payment);

        IdempotencyKey record = new IdempotencyKey(
                request.merchantId(),
                idempotencyKey,
                requestHash,
                savedPayment.getPaymentId()
        );

        idempotencyKeyRepository.save(record);

        return new PaymentCreationResult(
                toResponse(savedPayment),
                true
        );
    }

    @Override
    @Transactional(readOnly = true)
    public PaymentResponse getPaymentById(UUID paymentId) {

        Payment payment = paymentRepository.findById(paymentId)
                .orElseThrow(() ->
                        new PaymentNotFoundException(paymentId)
                );

        return toResponse(payment);
    }

    private PaymentResponse toResponse(Payment payment) {
        return new PaymentResponse(
                payment.getPaymentId(),
                payment.getMerchantId(),
                payment.getAmount(),
                payment.getCurrency(),
                payment.getCustomerId(),
                payment.getPaymentMethod(),
                payment.getStatus().name(),
                payment.getCreatedAt()
        );
    }

    @Override
    @Transactional
    public PaymentResponse updatePaymentStatus(
            UUID paymentId,
            PaymentStatus newStatus) {

        // 1. Retrieve the payment
        Payment payment = paymentRepository.findByIdForSettlement(paymentId)
                .orElseThrow(
                        () -> new PaymentNotFoundException(paymentId)
                );

        // 2. Validate the status transition
        transitionValidator.validate(
                payment.getStatus(),
                newStatus
        );

        // 3. Update payment status and timestamp
        payment.updateStatus(newStatus);

        // 4. Persist the updated entity
        Payment savedPayment = paymentRepository.save(payment);

        // 5. Return the updated payment details
        return new PaymentResponse(
                savedPayment.getPaymentId(),
                savedPayment.getMerchantId(),
                savedPayment.getAmount(),
                savedPayment.getCurrency(),
                savedPayment.getCustomerId(),
                savedPayment.getPaymentMethod(),
                savedPayment.getStatus().name(),
                savedPayment.getCreatedAt()
        );
    }

    @Override
    @Transactional
    public void claimPaymentForProcessing(UUID paymentId) {

        int updatedRows =
                paymentRepository.claimPaymentForProcessing(paymentId);

        if (updatedRows == 0) {
            throw new InvalidPaymentStateException(
                    "Payment cannot be claimed. " +
                            "It may already be processing or completed."
            );
        }

        if (updatedRows != 1) {
            throw new IllegalStateException(
                    "Unexpected number of payments claimed: "
                            + updatedRows
            );
        }
    }

}
