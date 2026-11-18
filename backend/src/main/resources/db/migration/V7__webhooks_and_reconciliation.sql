-- Additive only: existing payments, refunds and gateway attempts are preserved.
CREATE TABLE simulated_gateway_outcomes (
    gateway VARCHAR(100) NOT NULL,
    payment_id UUID NOT NULL REFERENCES payments(payment_id),
    gateway_transaction_id UUID NOT NULL,
    outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('SUCCESS','FAILED','TIMEOUT','UNKNOWN')),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (gateway, payment_id),
    UNIQUE (gateway, gateway_transaction_id)
);

CREATE TABLE webhook_events (
    id UUID PRIMARY KEY,
    gateway VARCHAR(100) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    payment_id UUID NOT NULL,
    payload TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED'
        CHECK (status IN ('RECEIVED','PROCESSED','IGNORED','DEFERRED','FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    detail VARCHAR(512),
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_webhook_gateway_event UNIQUE (gateway, event_id)
);
CREATE INDEX idx_webhook_due ON webhook_events(next_attempt_at)
    WHERE status IN ('RECEIVED','DEFERRED');
CREATE INDEX idx_webhook_payment ON webhook_events(payment_id, received_at);

CREATE TABLE reconciliation_jobs (
    payment_id UUID PRIMARY KEY REFERENCES payments(payment_id),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','RETRY','RESOLVED','EXHAUSTED','SKIPPED')),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE reconciliation_attempts (
    id UUID PRIMARY KEY,
    payment_id UUID NOT NULL REFERENCES payments(payment_id),
    attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
    gateway VARCHAR(100),
    outcome VARCHAR(20),
    status_before VARCHAR(30) NOT NULL,
    status_after VARCHAR(30) NOT NULL,
    result VARCHAR(20) NOT NULL,
    detail VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (payment_id, attempt)
);
CREATE INDEX idx_processing_reconciliation ON payments(updated_at, payment_id)
    WHERE status = 'PROCESSING';
