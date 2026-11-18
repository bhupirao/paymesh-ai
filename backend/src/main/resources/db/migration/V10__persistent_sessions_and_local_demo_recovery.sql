-- Additive authentication state only. No credentials or recovery eligibility are seeded.
CREATE TABLE auth_sessions (
 session_id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES app_users(user_id),
 authorization_version BIGINT NOT NULL, account_status VARCHAR(24) NOT NULL, roles_snapshot TEXT NOT NULL,
 remember_me BOOLEAN NOT NULL, created_at TIMESTAMPTZ NOT NULL, absolute_expires_at TIMESTAMPTZ NOT NULL,
 idle_expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ,
 CHECK(authorization_version>=0), CHECK(length(roles_snapshot)>0), CHECK(absolute_expires_at>created_at), CHECK(idle_expires_at<=absolute_expires_at)
);
CREATE INDEX idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX idx_auth_sessions_expiry ON auth_sessions(absolute_expires_at);
CREATE TABLE auth_refresh_tokens (
 token_id UUID PRIMARY KEY, session_id UUID NOT NULL REFERENCES auth_sessions(session_id) ON DELETE CASCADE,
 token_digest CHAR(64) NOT NULL UNIQUE CHECK(token_digest ~ '^[0-9a-f]{64}$'), created_at TIMESTAMPTZ NOT NULL, used_at TIMESTAMPTZ
);
CREATE INDEX idx_auth_refresh_family ON auth_refresh_tokens(session_id);
CREATE TABLE demo_recovery_eligibility (
 user_id UUID PRIMARY KEY REFERENCES app_users(user_id), portal VARCHAR(8) NOT NULL CHECK(portal IN ('ADMIN','MERCHANT')),
 enabled BOOLEAN NOT NULL DEFAULT FALSE, designated_by UUID NOT NULL REFERENCES app_users(user_id),
 review_reference VARCHAR(100) NOT NULL CHECK(length(btrim(review_reference))>0), designated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE password_recovery_challenges (
 challenge_id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES app_users(user_id),
 portal VARCHAR(8) NOT NULL CHECK(portal IN ('ADMIN','MERCHANT')), purpose VARCHAR(32) NOT NULL CHECK(purpose='LOCAL_DEMO_PASSWORD_RESET'),
 otp_digest CHAR(64) NOT NULL CHECK(otp_digest ~ '^[0-9a-f]{64}$'), authorization_version BIGINT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
 failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK(failed_attempts BETWEEN 0 AND 5), consumed_at TIMESTAMPTZ
);
CREATE INDEX idx_recovery_account ON password_recovery_challenges(user_id,created_at);
CREATE INDEX idx_recovery_expiry ON password_recovery_challenges(expires_at);
CREATE TABLE password_reset_authorizations (
 authorization_id UUID PRIMARY KEY, challenge_id UUID NOT NULL UNIQUE REFERENCES password_recovery_challenges(challenge_id) ON DELETE CASCADE,
 token_digest CHAR(64) NOT NULL UNIQUE CHECK(token_digest ~ '^[0-9a-f]{64}$'), expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ
);
CREATE INDEX idx_reset_expiry ON password_reset_authorizations(expires_at);
-- Security changes (including the unchanged offline recovery command) revoke all credentials atomically.
CREATE FUNCTION revoke_auth_state_for_account_change() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.authorization_version IS DISTINCT FROM OLD.authorization_version OR NEW.enabled IS DISTINCT FROM OLD.enabled OR NEW.account_status IS DISTINCT FROM OLD.account_status THEN
  EXECUTE format('UPDATE %I.auth_sessions SET revoked_at=COALESCE(revoked_at,CURRENT_TIMESTAMP) WHERE user_id=$1',TG_TABLE_SCHEMA) USING NEW.user_id;
  EXECUTE format('UPDATE %I.password_recovery_challenges SET consumed_at=COALESCE(consumed_at,CURRENT_TIMESTAMP) WHERE user_id=$1',TG_TABLE_SCHEMA) USING NEW.user_id;
  EXECUTE format('UPDATE %I.password_reset_authorizations SET consumed_at=COALESCE(consumed_at,CURRENT_TIMESTAMP) WHERE challenge_id IN (SELECT challenge_id FROM %I.password_recovery_challenges WHERE user_id=$1)',TG_TABLE_SCHEMA,TG_TABLE_SCHEMA) USING NEW.user_id;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER auth_account_security_change AFTER UPDATE ON app_users FOR EACH ROW EXECUTE FUNCTION revoke_auth_state_for_account_change();
CREATE FUNCTION revoke_auth_state_for_role_change() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE target UUID;
BEGIN
 target=COALESCE(NEW.user_id,OLD.user_id);
 EXECUTE format('UPDATE %I.auth_sessions SET revoked_at=COALESCE(revoked_at,CURRENT_TIMESTAMP) WHERE user_id=$1',TG_TABLE_SCHEMA) USING target;
 EXECUTE format('UPDATE %I.password_recovery_challenges SET consumed_at=COALESCE(consumed_at,CURRENT_TIMESTAMP) WHERE user_id=$1',TG_TABLE_SCHEMA) USING target;
 EXECUTE format('UPDATE %I.password_reset_authorizations SET consumed_at=COALESCE(consumed_at,CURRENT_TIMESTAMP) WHERE challenge_id IN (SELECT challenge_id FROM %I.password_recovery_challenges WHERE user_id=$1)',TG_TABLE_SCHEMA,TG_TABLE_SCHEMA) USING target;
 RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER auth_role_security_change AFTER INSERT OR DELETE OR UPDATE ON user_roles FOR EACH ROW EXECUTE FUNCTION revoke_auth_state_for_role_change();
