package com.paymesh.backend.service.internal;

import com.paymesh.backend.dto.RefundCreationResult;
import com.paymesh.backend.dto.RefundRequest;
import com.paymesh.backend.dto.RefundResponse;
import java.util.List;
import java.util.UUID;

/** Trusted financial core, never an HTTP authorization boundary. */
public interface InternalRefundService {
    RefundCreationResult refund(UUID paymentId, RefundRequest request, String idempotencyKey);
    RefundResponse getRefund(UUID paymentId);
    List<RefundResponse> getRefundHistory(UUID paymentId);
}
