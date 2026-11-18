-- Additive lifecycle state. No pending registration is approved and no financial row changes.
ALTER TABLE app_users DROP CONSTRAINT app_users_account_status_check;
ALTER TABLE app_users ADD CONSTRAINT app_users_account_status_check
 CHECK (account_status IN ('PENDING_APPROVAL','ACTIVE','REJECTED','SUSPENDED'));
CREATE TABLE merchant_administration (
 merchant_id VARCHAR(100) COLLATE "C" PRIMARY KEY REFERENCES merchants(merchant_id),
 status VARCHAR(24) NOT NULL CHECK(status IN ('PENDING_APPROVAL','ACTIVE','REJECTED','SUSPENDED')),
 approved_at TIMESTAMPTZ, approved_by UUID REFERENCES app_users(user_id),
 last_action_at TIMESTAMPTZ, last_action_by UUID REFERENCES app_users(user_id),
 reason VARCHAR(500), review_reference VARCHAR(100),
 CHECK ((approved_at IS NULL)=(approved_by IS NULL)),
 CHECK (status NOT IN ('ACTIVE','SUSPENDED') OR approved_at IS NOT NULL)
);
INSERT INTO merchant_administration(merchant_id,status,approved_at,approved_by)
 SELECT merchant_id,CASE WHEN verified AND active THEN 'ACTIVE' WHEN verified THEN 'SUSPENDED' ELSE 'PENDING_APPROVAL' END,
 verified_at,verified_by FROM merchants;
CREATE INDEX idx_merchant_administration_status ON merchant_administration(status,merchant_id);
-- Covers registrations/provisioners that continue using the established Merchant model.
CREATE FUNCTION initialize_merchant_administration() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 EXECUTE format('INSERT INTO %I.merchant_administration(merchant_id,status,approved_at,approved_by) VALUES ($1,$2,$3,$4)',TG_TABLE_SCHEMA) USING NEW.merchant_id,CASE WHEN NEW.verified AND NEW.active THEN 'ACTIVE' WHEN NEW.verified THEN 'SUSPENDED' ELSE 'PENDING_APPROVAL' END,NEW.verified_at,NEW.verified_by;
 RETURN NEW;
END $$;
CREATE TRIGGER merchant_administration_insert AFTER INSERT ON merchants FOR EACH ROW EXECUTE FUNCTION initialize_merchant_administration();
-- Existing internal/offline reviewed verification remains compatible.
CREATE FUNCTION sync_verified_merchant_administration() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.verified AND NOT OLD.verified THEN
 EXECUTE format('UPDATE %I.merchant_administration SET status=''ACTIVE'',approved_at=$1,approved_by=$2 WHERE merchant_id=$3',TG_TABLE_SCHEMA) USING NEW.verified_at,NEW.verified_by,NEW.merchant_id;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER merchant_administration_verify AFTER UPDATE ON merchants FOR EACH ROW EXECUTE FUNCTION sync_verified_merchant_administration();
