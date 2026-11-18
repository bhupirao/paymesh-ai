-- Preserve existing refunds and their IDs, amounts, statuses and timestamps.
-- Legacy refunds have a null key; PostgreSQL permits multiple nulls in UNIQUE.
ALTER TABLE refunds ADD COLUMN idempotency_key VARCHAR(255);
ALTER TABLE refunds DROP CONSTRAINT uq_refunds_payment;
ALTER TABLE refunds ADD CONSTRAINT uq_refunds_payment_key
    UNIQUE (payment_id, idempotency_key);
ALTER TABLE refunds ADD CONSTRAINT chk_refund_idempotency_key
    CHECK (idempotency_key IS NULL OR length(trim(idempotency_key)) > 0);
