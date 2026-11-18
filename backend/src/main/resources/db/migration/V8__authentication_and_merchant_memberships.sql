-- Schema preparation only: no authentication behavior or account provisioning.
-- Existing business tables, rows and ownership identifiers remain unchanged.

CREATE TABLE app_users (
    user_id UUID PRIMARY KEY,
    login_normalized VARCHAR(255) COLLATE "C" NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    authorization_version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_app_users_login UNIQUE (login_normalized),
    CONSTRAINT chk_app_users_login CHECK (
        length(login_normalized) > 0
        AND login_normalized = lower(btrim(login_normalized))
    ),
    CONSTRAINT chk_app_users_password_hash CHECK (length(btrim(password_hash)) > 0),
    CONSTRAINT chk_app_users_authorization_version CHECK (authorization_version >= 0)
);

CREATE TABLE roles (
    role_name VARCHAR(20) PRIMARY KEY,
    CONSTRAINT chk_roles_name CHECK (role_name IN ('ADMIN', 'MERCHANT'))
);

-- Reference data only. Never seed passwords, users or privileged assignments.
INSERT INTO roles (role_name) VALUES ('ADMIN'), ('MERCHANT');

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    role_name VARCHAR(20) NOT NULL REFERENCES roles(role_name) ON DELETE RESTRICT,
    granted_by UUID REFERENCES app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_name)
);
CREATE INDEX idx_user_roles_role ON user_roles(role_name, user_id);
CREATE INDEX idx_user_roles_granted_by ON user_roles(granted_by);

CREATE TABLE merchants (
    -- C collation keeps distinct legacy strings distinct; never trim or case-fold.
    -- No nonblank check: even malformed legacy identifiers must be preserved.
    merchant_id VARCHAR(100) COLLATE "C" PRIMARY KEY,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by UUID REFERENCES app_users(user_id) ON DELETE RESTRICT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_merchants_active CHECK (NOT active OR verified),
    CONSTRAINT chk_merchants_verification CHECK (
        (NOT verified AND verified_by IS NULL AND verified_at IS NULL)
        OR (verified AND verified_by IS NOT NULL AND verified_at IS NOT NULL)
    )
);
CREATE INDEX idx_merchants_verified_by ON merchants(verified_by);

CREATE TABLE merchant_memberships (
    user_id UUID NOT NULL REFERENCES app_users(user_id) ON DELETE RESTRICT,
    merchant_id VARCHAR(100) COLLATE "C" NOT NULL
        REFERENCES merchants(merchant_id) ON DELETE RESTRICT,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    granted_by UUID REFERENCES app_users(user_id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, merchant_id)
);
CREATE INDEX idx_merchant_memberships_merchant ON merchant_memberships(merchant_id, user_id);
CREATE INDEX idx_merchant_memberships_granted_by ON merchant_memberships(granted_by);

CREATE TABLE security_audit_events (
    event_id UUID PRIMARY KEY,
    actor_user_id UUID REFERENCES app_users(user_id) ON DELETE RESTRICT,
    -- Snapshot identity also permits auditing an unsuccessful, unknown login.
    actor_identifier VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    -- Deliberately no target FK: denied/unknown resources must be auditable too.
    target_merchant_id VARCHAR(100) COLLATE "C",
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    outcome VARCHAR(20) NOT NULL,
    correlation_id VARCHAR(100),
    -- Future writers must exclude passwords, hashes, credentials and raw tokens.
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_security_audit_event_type CHECK (length(btrim(event_type)) > 0),
    CONSTRAINT chk_security_audit_outcome CHECK (outcome IN ('SUCCESS', 'DENIED', 'FAILURE')),
    CONSTRAINT chk_security_audit_metadata CHECK (jsonb_typeof(metadata) = 'object')
);
CREATE INDEX idx_security_audit_actor ON security_audit_events(actor_user_id, occurred_at);
CREATE INDEX idx_security_audit_merchant ON security_audit_events(target_merchant_id, occurred_at);
CREATE INDEX idx_security_audit_time ON security_audit_events(occurred_at);
CREATE INDEX idx_security_audit_correlation ON security_audit_events(correlation_id);

-- Read legacy ownership exactly as stored, including idempotency-only values.
-- No users, role assignments, memberships or security events are backfilled.
-- An unverified registry entry with no membership is unclaimed, not authorized.
INSERT INTO merchants (merchant_id)
SELECT merchant_id COLLATE "C" FROM payments
UNION
SELECT merchant_id COLLATE "C" FROM idempotency_keys;
