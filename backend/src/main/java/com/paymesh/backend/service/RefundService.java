package com.paymesh.backend.service;
import com.paymesh.backend.dto.RefundResponse;
import com.paymesh.backend.dto.RefundRequest;
import com.paymesh.backend.dto.RefundCreationResult;
import java.util.List;
import java.util.UUID;
public interface RefundService {
    RefundCreationResult refund(UUID paymentId, RefundRequest request, String idempotencyKey);
    RefundResponse getRefund(UUID paymentId);
    List<RefundResponse> getRefundHistory(UUID paymentId);
}
