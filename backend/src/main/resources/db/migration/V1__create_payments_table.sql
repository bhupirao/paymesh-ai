
CREATE TABLE payments (
    payment_id UUID PRIMARY KEY,
    merchant_id VARCHAR(100) NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    amount NUMERIC(19, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'CREATED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_payment_amount
        CHECK (amount > 0),

    CONSTRAINT chk_payment_status
        CHECK (
            status IN (
                'CREATED',
                'PROCESSING',
                'SUCCESS',
                'FAILED',
                'CANCELLED',
                'REFUNDED'
            )
        )
);

CREATE INDEX idx_payments_merchant_id
    ON payments (merchant_id);

CREATE INDEX idx_payments_customer_id
    ON payments (customer_id);

CREATE INDEX idx_payments_status
    ON payments (status);
