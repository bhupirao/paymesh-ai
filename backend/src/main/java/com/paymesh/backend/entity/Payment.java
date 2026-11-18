
package com.paymesh.backend.entity;

import com.paymesh.backend.enums.PaymentStatus;
import jakarta.persistence.Version;
import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "payments")
public class Payment {

    @Id
    @Column(name = "payment_id", nullable = false)
    private UUID paymentId;

    @Column(name = "merchant_id", nullable = false, length = 100)
    private String merchantId;

    @Column(name = "customer_id", nullable = false, length = 100)
    private String customerId;

    @Column(name = "amount", nullable = false, precision = 19, scale = 2)
    private BigDecimal amount;

    @Column(name = "currency", nullable = false, length = 3)
    private String currency;

    @Column(name = "payment_method", nullable = false, length = 30)
    private String paymentMethod;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 30)
    private PaymentStatus status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Version
    @Column(name = "version", nullable = false)
    private Long version;

    protected Payment() {
        // Required by JPA
    }

    public Payment(
            String merchantId,
            String customerId,
            BigDecimal amount,
            String currency,
            String paymentMethod
    ) {
        this.paymentId = UUID.randomUUID();
        this.merchantId = merchantId;
        this.customerId = customerId;
        this.amount = amount;
        this.currency = currency;
        this.paymentMethod = paymentMethod;
        this.status = PaymentStatus.CREATED;
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
    }

    public UUID getPaymentId() {
        return paymentId;
    }

    public String getMerchantId() {
        return merchantId;
    }

    public String getCustomerId() {
        return customerId;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public String getCurrency() {
        return currency;
    }

    public String getPaymentMethod() {
        return paymentMethod;
    }

    public PaymentStatus getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
    public void updateStatus(PaymentStatus newStatus) {
        this.status = newStatus;
        this.updatedAt = Instant.now();
    }
}
