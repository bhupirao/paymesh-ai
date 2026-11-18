package com.paymesh.backend.service.impl;

import com.paymesh.backend.dto.*;
import com.paymesh.backend.security.business.BusinessAccess;
import com.paymesh.backend.service.RefundService;
import com.paymesh.backend.service.internal.InternalRefundService;
import java.util.List;
import java.util.UUID;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

@Service
@Primary
@Transactional(isolation = Isolation.READ_COMMITTED)
public class RefundServiceImpl implements RefundService {
    private final InternalRefundService core;
    private final BusinessAccess access;
    public RefundServiceImpl(InternalRefundService core, BusinessAccess access) { this.core = core; this.access = access; }
    @Override public RefundCreationResult refund(UUID id, RefundRequest request, String key) {
        var actor = access.actor(); var payment = access.payment(actor, id, true);
        var result = core.refund(id, request, key);
        access.audit(actor, payment.getMerchantId(), id, "ADMIN_REFUND_CREATED_OR_REPLAYED"); return result;
    }
    @Override public RefundResponse getRefund(UUID id) {
        var actor = access.actor(); var payment = access.payment(actor, id, false);
        var result = core.getRefund(id);
        access.audit(actor, payment.getMerchantId(), id, "ADMIN_REFUND_READ"); return result;
    }
    @Override public List<RefundResponse> getRefundHistory(UUID id) {
        var actor = access.actor(); var payment = access.payment(actor, id, false);
        var result = core.getRefundHistory(id);
        access.audit(actor, payment.getMerchantId(), id, "ADMIN_REFUND_HISTORY_READ"); return result;
    }
}
