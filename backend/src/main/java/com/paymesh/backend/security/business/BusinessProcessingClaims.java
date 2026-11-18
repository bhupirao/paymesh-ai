package com.paymesh.backend.security.business;

import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.exception.InvalidPaymentStateException;
import com.paymesh.backend.repository.PaymentRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
public class BusinessProcessingClaims {
    private final BusinessAccess access;
    private final PaymentRepository payments;
    public BusinessProcessingClaims(BusinessAccess access, PaymentRepository payments) { this.access = access; this.payments = payments; }

    @Transactional(propagation = Propagation.REQUIRES_NEW, isolation = Isolation.READ_COMMITTED)
    public PaymentResponse claim(UUID paymentId) {
        var actor = access.actor();
        access.payment(actor, paymentId, true);
        if (payments.claimAccessiblePayment(paymentId, actor.id(), actor.version(), actor.admin(), actor.merchant(), Instant.now()) != 1) {
            throw new InvalidPaymentStateException("Payment cannot be claimed. It may already be processing or completed.");
        }
        Payment payment = access.payment(actor, paymentId, false);
        access.audit(actor, payment.getMerchantId(), paymentId, "ADMIN_PAYMENT_PROCESSING_CLAIMED");
        return new PaymentResponse(paymentId, payment.getMerchantId(), payment.getAmount(), payment.getCurrency(),
                payment.getCustomerId(), payment.getPaymentMethod(), payment.getStatus().name(), payment.getCreatedAt());
    }
}
