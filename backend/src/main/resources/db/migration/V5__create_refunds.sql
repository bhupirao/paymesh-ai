CREATE TABLE refunds (
    refund_id UUID PRIMARY KEY,
    payment_id UUID NOT NULL REFERENCES payments(payment_id),
    amount NUMERIC(19,2) NOT NULL CHECK (amount > 0),
    status VARCHAR(30) NOT NULL CHECK (status IN ('SUCCESS')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_refunds_payment UNIQUE(payment_id)
);
CREATE INDEX idx_refunds_payment_id ON refunds(payment_id);
