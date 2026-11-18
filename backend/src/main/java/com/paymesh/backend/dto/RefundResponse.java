package com.paymesh.backend.dto;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
public record RefundResponse(UUID refundId, UUID paymentId, BigDecimal amount, String status, Instant createdAt) {}
