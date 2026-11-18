package com.paymesh.backend.entity;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.UUID;
@Entity @Table(name="refunds")
public class Refund {
    @Id @Column(name="refund_id") private UUID refundId;
    @Column(name="payment_id",nullable=false) private UUID paymentId;
    @Column(nullable=false,precision=19,scale=2) private BigDecimal amount;
    @Column(nullable=false) private String status;
    @Column(name="created_at",nullable=false) private Instant createdAt;
    // Null for refunds created before V6; those records remain unchanged.
    @Column(name="idempotency_key",length=255) private String idempotencyKey;
    protected Refund() {}
    public Refund(UUID paymentId, BigDecimal amount, String idempotencyKey) {
        this.refundId=UUID.randomUUID(); this.paymentId=paymentId;
        this.amount=amount.setScale(2, java.math.RoundingMode.UNNECESSARY);
        this.idempotencyKey=idempotencyKey;
        this.status="SUCCESS"; this.createdAt=Instant.now().truncatedTo(ChronoUnit.MICROS);
    }
    public UUID getRefundId(){return refundId;}
    public UUID getPaymentId(){return paymentId;}
    public BigDecimal getAmount(){return amount;}
    public String getStatus(){return status;}
    public Instant getCreatedAt(){return createdAt;}
    public String getIdempotencyKey(){return idempotencyKey;}
}
