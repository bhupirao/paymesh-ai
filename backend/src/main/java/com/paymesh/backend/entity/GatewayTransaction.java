
package com.paymesh.backend.entity;

import jakarta.persistence.*;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "payment_gateway_transactions")
public class GatewayTransaction {

    @Id
    @Column(name = "id", nullable = false)
    private UUID id;

    @Column(name = "payment_id", nullable = false)
    private UUID paymentId;

    @Column(name = "gateway_name", nullable = false, length = 100)
    private String gatewayName;

    @Column(name = "gateway_transaction_id")
    private UUID gatewayTransactionId;

    @Column(name = "status", nullable = false, length = 30)
    private String status;

    @Column(name = "error_code", length = 100)
    private String errorCode;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected GatewayTransaction() {
        // Required by JPA
    }

    public GatewayTransaction(
            UUID paymentId,
            String gatewayName
    ) {
        this.id = UUID.randomUUID();
        this.paymentId = paymentId;
        this.gatewayName = gatewayName;
        this.status = "INITIATED";
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
    }

    public void updateResult(
            UUID gatewayTransactionId,
            String status,
            String errorCode,
            String errorMessage
    ) {
        this.gatewayTransactionId = gatewayTransactionId;
        this.status = status;
        this.errorCode = errorCode;
        this.errorMessage = errorMessage;
        this.updatedAt = Instant.now();
    }

    public void setGatewayName(String gatewayName) {
        if (gatewayName != null && !gatewayName.isBlank()) this.gatewayName = gatewayName;
    }

    public UUID getId() {
        return id;
    }

    public UUID getPaymentId() {
        return paymentId;
    }

    public String getGatewayName() {
        return gatewayName;
    }

    public UUID getGatewayTransactionId() {
        return gatewayTransactionId;
    }

    public String getStatus() {
        return status;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
