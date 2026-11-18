package com.paymesh.backend.dto;
import java.time.Instant;
import java.util.UUID;
public record GatewayTransactionResponse(UUID id, UUID paymentId, String gatewayName,
    UUID gatewayTransactionId, String status, String errorCode, String errorMessage,
    Instant createdAt, Instant updatedAt) {}
