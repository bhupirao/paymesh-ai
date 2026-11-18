package com.paymesh.backend.settlement;

import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.UUID;

public record WebhookPayload(
        @NotBlank @Size(max = 255) String eventId,
        @NotNull UUID paymentId,
        @NotNull UUID gatewayTransactionId,
        @NotNull Observation status,
        @NotNull Instant occurredAt) {}
