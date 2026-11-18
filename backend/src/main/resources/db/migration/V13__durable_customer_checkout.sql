-- Preserve V12: payment_links.payment_id is still the successful payment only.
ALTER TABLE payments ADD CONSTRAINT uq_checkout_payment_owner UNIQUE(payment_id,merchant_id);
ALTER TABLE payment_links ADD CONSTRAINT uq_checkout_link_owner UNIQUE(link_id,merchant_id);
ALTER TABLE payment_links ADD CONSTRAINT fk_checkout_success_owner FOREIGN KEY(payment_id,merchant_id) REFERENCES payments(payment_id,merchant_id);
CREATE TABLE checkout_attempts (
 attempt_id UUID PRIMARY KEY,
 link_id UUID NOT NULL,
 merchant_id VARCHAR(100) COLLATE "C" NOT NULL,
 payment_id UUID NOT NULL UNIQUE,
 key_digest CHAR(64) NOT NULL CHECK(key_digest ~ '^[a-f0-9]{64}$'),
 request_digest CHAR(64) NOT NULL CHECK(request_digest ~ '^[a-f0-9]{64}$'),
 status VARCHAR(16) NOT NULL CHECK(status IN ('PROCESSING','UNCERTAIN','SUCCESS','FAILED')),
 simulation_outcome VARCHAR(8) CHECK(simulation_outcome IN ('SUCCESS','FAILED','TIMEOUT')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(link_id,key_digest),
 FOREIGN KEY(link_id,merchant_id) REFERENCES payment_links(link_id,merchant_id),
 FOREIGN KEY(payment_id,merchant_id) REFERENCES payments(payment_id,merchant_id)
);
-- A definitive failure releases the slot; a timeout/crash does not.
CREATE UNIQUE INDEX uq_checkout_blocking_attempt ON checkout_attempts(link_id)
 WHERE status IN ('PROCESSING','UNCERTAIN','SUCCESS');
CREATE INDEX idx_checkout_history ON checkout_attempts(link_id,created_at DESC,attempt_id DESC);
CREATE FUNCTION validate_checkout_attempt() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE valid BOOLEAN;
BEGIN
 EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I.payment_links l JOIN %I.payments p ON p.payment_id=$1 WHERE l.link_id=$2 AND l.merchant_id=$3 AND p.merchant_id=l.merchant_id AND p.amount=l.amount AND p.currency=l.currency AND p.payment_method=l.payment_method AND p.status=''PROCESSING'')',TG_TABLE_SCHEMA,TG_TABLE_SCHEMA)
 INTO valid USING NEW.payment_id,NEW.link_id,NEW.merchant_id;
 IF NOT valid OR NEW.status<>'PROCESSING' THEN RAISE EXCEPTION 'Invalid checkout association'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER checkout_attempt_insert BEFORE INSERT ON checkout_attempts FOR EACH ROW EXECUTE FUNCTION validate_checkout_attempt();
-- Gateway completion, webhook and reconciliation all use the existing payment row.
-- Receipt/link/attempt state commits in the SAME transaction as its financial outcome.
CREATE FUNCTION synchronize_checkout_outcome() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status IN ('SUCCESS','REFUNDED') THEN
  EXECUTE format('UPDATE %I.payment_links l SET status=''PAID'',payment_id=$1,updated_at=clock_timestamp() FROM %I.checkout_attempts a WHERE a.payment_id=$1 AND a.link_id=l.link_id AND l.payment_id IS NULL',TG_TABLE_SCHEMA,TG_TABLE_SCHEMA) USING NEW.payment_id;
  EXECUTE format('UPDATE %I.checkout_attempts SET status=''SUCCESS'',updated_at=clock_timestamp() WHERE payment_id=$1 AND status<>''SUCCESS''',TG_TABLE_SCHEMA) USING NEW.payment_id;
 ELSIF NEW.status='FAILED' THEN
  EXECUTE format('UPDATE %I.checkout_attempts SET status=''FAILED'',updated_at=clock_timestamp() WHERE payment_id=$1 AND status IN (''PROCESSING'',''UNCERTAIN'')',TG_TABLE_SCHEMA) USING NEW.payment_id;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER checkout_payment_outcome AFTER UPDATE OF status ON payments FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status) EXECUTE FUNCTION synchronize_checkout_outcome();
