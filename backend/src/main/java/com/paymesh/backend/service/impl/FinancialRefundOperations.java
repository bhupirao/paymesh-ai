package com.paymesh.backend.service.impl;

import com.paymesh.backend.dto.RefundCreationResult;
import com.paymesh.backend.dto.RefundRequest;
import com.paymesh.backend.dto.RefundResponse;
import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.entity.Refund;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.exception.IdempotencyConflictException;
import com.paymesh.backend.exception.InvalidPaymentStateException;
import com.paymesh.backend.exception.PaymentNotFoundException;
import com.paymesh.backend.repository.PaymentRepository;
import com.paymesh.backend.repository.RefundRepository;
import com.paymesh.backend.service.internal.InternalRefundService;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class FinancialRefundOperations implements InternalRefundService {
    private final PaymentRepository payments;
    private final RefundRepository refunds;

    public FinancialRefundOperations(PaymentRepository payments, RefundRepository refunds) {
        this.payments = payments;
        this.refunds = refunds;
    }

    @Override
    @Transactional(isolation = Isolation.READ_COMMITTED)
    public RefundCreationResult refund(UUID paymentId, RefundRequest request, String idempotencyKey) {
        validate(request, idempotencyKey);
        // Every refund writer locks the same payment before reading the total or key.
        // READ_COMMITTED makes the following queries see the preceding lock holder's commit.
        Payment payment = payments.findByIdForRefund(paymentId)
                .orElseThrow(() -> new PaymentNotFoundException(paymentId));
        var existing = refunds.findByPaymentIdAndIdempotencyKey(paymentId, idempotencyKey);
        if (existing.isPresent()) {
            Refund refund = existing.get();
            if (refund.getAmount().compareTo(request.amount()) != 0) {
                throw new IdempotencyConflictException(
                        "Idempotency key already used with a different refund amount");
            }
            // Replays must work even after the payment has become fully refunded.
            return new RefundCreationResult(toResponse(refund), false);
        }
        if (payment.getStatus() != PaymentStatus.SUCCESS) {
            throw new InvalidPaymentStateException("Only a successful payment with remaining balance can be refunded");
        }
        BigDecimal remaining = payment.getAmount().subtract(refunds.totalSuccessfulAmount(paymentId));
        if (request.amount().compareTo(remaining) > 0) {
            throw new InvalidPaymentStateException("Refund amount exceeds remaining refundable amount: " + remaining);
        }
        // Simulated refund: no real gateway reversal is performed.
        Refund refund = refunds.saveAndFlush(new Refund(paymentId, request.amount(), idempotencyKey));
        if (request.amount().compareTo(remaining) == 0) {
            payment.updateStatus(PaymentStatus.REFUNDED);
        }
        return new RefundCreationResult(toResponse(refund), true);
    }

    private void validate(RefundRequest request, String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank() || idempotencyKey.length() > 255) {
            throw new IllegalArgumentException("Idempotency-Key must contain 1 to 255 characters");
        }
        // Validate service calls as well as HTTP requests. Never round monetary input.
        BigDecimal amount = request == null ? null : request.amount();
        if (amount == null || amount.signum() <= 0 || amount.scale() > 2
                || amount.compareTo(new BigDecimal("99999999999999999.99")) > 0) {
            throw new IllegalArgumentException("Refund amount must be positive with at most 17 integer and 2 decimal digits");
        }
    }

    @Override
    @Transactional(readOnly = true)
    public RefundResponse getRefund(UUID paymentId) {
        return refunds.findFirstByPaymentIdOrderByCreatedAtDescRefundIdDesc(paymentId)
                .map(this::toResponse)
                .orElseThrow(() -> new PaymentNotFoundException(paymentId));
    }

    @Override
    @Transactional(readOnly = true)
    public List<RefundResponse> getRefundHistory(UUID paymentId) {
        if (!payments.existsById(paymentId)) {
            throw new PaymentNotFoundException(paymentId);
        }
        return refunds.findAllByPaymentIdOrderByCreatedAtAscRefundIdAsc(paymentId)
                .stream().map(this::toResponse).toList();
    }

    private RefundResponse toResponse(Refund refund) {
        return new RefundResponse(refund.getRefundId(), refund.getPaymentId(), refund.getAmount(),
                refund.getStatus(), refund.getCreatedAt());
    }
}
