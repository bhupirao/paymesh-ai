
CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY,

    merchant_id VARCHAR(100) NOT NULL,

    idempotency_key VARCHAR(255) NOT NULL,

    request_hash VARCHAR(64) NOT NULL,

    payment_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_idempotency_merchant_key
        UNIQUE (merchant_id, idempotency_key),

    CONSTRAINT fk_idempotency_payment
        FOREIGN KEY (payment_id)
        REFERENCES payments(payment_id)
);

CREATE INDEX idx_idempotency_payment_id
    ON idempotency_keys(payment_id);
