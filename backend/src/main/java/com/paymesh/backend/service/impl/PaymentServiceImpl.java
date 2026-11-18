package com.paymesh.backend.service.impl;

import com.paymesh.backend.dto.*;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.repository.IdempotencyKeyRepository;
import com.paymesh.backend.security.business.*;
import com.paymesh.backend.service.PaymentService;
import com.paymesh.backend.service.internal.InternalPaymentService;
import java.util.UUID;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

/** Secured application boundary; financial calculations remain in the internal core. */
@Service
@Primary
@Transactional(isolation = Isolation.READ_COMMITTED)
public class PaymentServiceImpl implements PaymentService {
    private final InternalPaymentService core;
    private final BusinessAccess access;
    private final BusinessProcessingClaims claims;
    private final IdempotencyKeyRepository idempotency;
    public PaymentServiceImpl(InternalPaymentService core, BusinessAccess access, BusinessProcessingClaims claims,
                              IdempotencyKeyRepository idempotency) {
        this.core = core; this.access = access; this.claims = claims; this.idempotency = idempotency;
    }
    @Override public PaymentCreationResult createPayment(PaymentRequest request, String key) {
        var actor = access.actor();
        access.creation(actor, request.merchantId());
        // Legacy inconsistent idempotency references must not expose another merchant.
        idempotency.findByMerchantIdAndIdempotencyKey(request.merchantId(), key)
                .ifPresent(record -> access.payment(actor, record.getPaymentId(), false));
        var result = core.createPayment(request, key);
        access.payment(actor, result.payment().paymentId(), false);
        access.audit(actor, result.payment().merchantId(), result.payment().paymentId(), "ADMIN_PAYMENT_CREATED_OR_REPLAYED");
        return result;
    }
    @Override public PaymentResponse getPaymentById(UUID id) {
        var actor = access.actor(); var payment = access.payment(actor, id, false);
        var result = core.getPaymentById(id);
        access.audit(actor, payment.getMerchantId(), id, "ADMIN_PAYMENT_READ"); return result;
    }
    @Override public PaymentResponse updatePaymentStatus(UUID id, PaymentStatus next) {
        var actor = access.actor(); var payment = access.payment(actor, id, true);
        var result = core.updatePaymentStatus(id, next);
        access.audit(actor, payment.getMerchantId(), id, "ADMIN_PAYMENT_STATUS_UPDATED"); return result;
    }
    @Override
    @Transactional(propagation = org.springframework.transaction.annotation.Propagation.NOT_SUPPORTED)
    public void claimPaymentForProcessing(UUID id) { claims.claim(id); }
}
