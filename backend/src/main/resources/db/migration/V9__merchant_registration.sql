-- Existing provisioned accounts retain their access. No financial records change.
ALTER TABLE app_users ADD COLUMN account_status VARCHAR(24) NOT NULL DEFAULT 'ACTIVE'
    CHECK (account_status IN ('ACTIVE', 'PENDING_APPROVAL'));
CREATE TABLE merchant_registrations (
    user_id UUID PRIMARY KEY REFERENCES app_users(user_id) ON DELETE RESTRICT,
    merchant_id VARCHAR(100) NOT NULL UNIQUE REFERENCES merchants(merchant_id) ON DELETE RESTRICT,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    business_name VARCHAR(160) NOT NULL,
    email VARCHAR(254) COLLATE "C" NOT NULL UNIQUE,
    mobile VARCHAR(16) NOT NULL,
    business_type VARCHAR(24) NOT NULL CHECK (business_type IN ('SOLE_PROPRIETOR','COMPANY','PARTNERSHIP','NONPROFIT','OTHER')),
    country VARCHAR(5) NOT NULL CHECK (country IN ('IN','US','GB','CA','AU','OTHER')),
    terms_version VARCHAR(32) NOT NULL,
    terms_accepted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (email = lower(btrim(email)))
);
