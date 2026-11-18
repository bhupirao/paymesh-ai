
CREATE TABLE payment_gateway_transactions (

    id UUID PRIMARY KEY,

    payment_id UUID NOT NULL,

    gateway_name VARCHAR(100) NOT NULL,

    gateway_transaction_id UUID,

    status VARCHAR(30) NOT NULL,

    error_code VARCHAR(100),

    error_message TEXT,

    created_at TIMESTAMP WITH TIME ZONE
        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP WITH TIME ZONE
        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_gateway_transaction_payment
        FOREIGN KEY (payment_id)
        REFERENCES payments(payment_id),

    CONSTRAINT chk_gateway_transaction_status
        CHECK (
            status IN (
                'INITIATED',
                'SUCCESS',
                'FAILED',
                'TIMEOUT',
                'UNKNOWN'
            )
        )
);

CREATE INDEX idx_gateway_transactions_payment_id
    ON payment_gateway_transactions(payment_id);

CREATE INDEX idx_gateway_transactions_status
    ON payment_gateway_transactions(status);
