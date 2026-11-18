-- Private conversation content is distinct from financial/audit records.
CREATE TABLE ai_conversations (
 conversation_id UUID PRIMARY KEY,
 owner_id UUID NOT NULL REFERENCES app_users(user_id),
 portal_role VARCHAR(8) NOT NULL CHECK(portal_role IN ('MERCHANT','ADMIN')),
 context_type VARCHAR(12) NOT NULL CHECK(context_type IN ('PLATFORM','MERCHANT','PAYMENT')),
 scope_merchant_id VARCHAR(100) COLLATE "C" REFERENCES merchants(merchant_id),
 payment_id UUID,
 context JSONB NOT NULL CHECK(jsonb_typeof(context)='object'),
 title VARCHAR(120) NOT NULL CHECK(char_length(btrim(title)) BETWEEN 1 AND 120),
 version BIGINT NOT NULL DEFAULT 0 CHECK(version>=0),
 turn_count INTEGER NOT NULL DEFAULT 0 CHECK(turn_count BETWEEN 0 AND 50),
 content_bytes INTEGER NOT NULL DEFAULT 0 CHECK(content_bytes BETWEEN 0 AND 1048576),
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT (clock_timestamp()+interval '30 days'),
 FOREIGN KEY(payment_id,scope_merchant_id) REFERENCES payments(payment_id,merchant_id),
 CHECK((context_type='PLATFORM' AND portal_role='ADMIN' AND scope_merchant_id IS NULL AND payment_id IS NULL)
    OR (context_type='MERCHANT' AND scope_merchant_id IS NOT NULL AND payment_id IS NULL)
    OR (context_type='PAYMENT' AND scope_merchant_id IS NOT NULL AND payment_id IS NOT NULL)),
 CHECK(expires_at>created_at),
 CHECK(context - ARRAY['paymentId','merchantId','statistics'] = '{}'::jsonb),
 CHECK(COALESCE(context->>'paymentId','')=COALESCE(payment_id::text,'')),
 CHECK(NOT(context ? 'merchantId') OR context->>'merchantId'=scope_merchant_id)
);
CREATE INDEX ix_ai_conversation_owner ON ai_conversations(owner_id,portal_role,updated_at DESC,conversation_id DESC);
CREATE INDEX ix_ai_conversation_expiry ON ai_conversations(expires_at);
CREATE TABLE ai_conversation_creations (
 owner_id UUID NOT NULL REFERENCES app_users(user_id),
 portal_role VARCHAR(8) NOT NULL CHECK(portal_role IN ('MERCHANT','ADMIN')),
 request_id UUID NOT NULL,
 fingerprint CHAR(64) NOT NULL CHECK(fingerprint ~ '^[a-f0-9]{64}$'),
 conversation_id UUID REFERENCES ai_conversations(conversation_id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 expires_at TIMESTAMPTZ NOT NULL DEFAULT (clock_timestamp()+interval '31 days'),
 PRIMARY KEY(owner_id,portal_role,request_id)
);
CREATE INDEX ix_ai_creation_expiry ON ai_conversation_creations(expires_at);
CREATE TABLE ai_conversation_requests (
 conversation_id UUID NOT NULL REFERENCES ai_conversations(conversation_id) ON DELETE CASCADE,
 request_id UUID NOT NULL,
 question_digest CHAR(64) NOT NULL CHECK(question_digest ~ '^[a-f0-9]{64}$'),
 expected_version BIGINT NOT NULL CHECK(expected_version>=0),
 status VARCHAR(12) NOT NULL CHECK(status IN ('IN_PROGRESS','COMPLETED','FAILED')),
 worker_nonce UUID NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 1 CHECK(attempts BETWEEN 1 AND 3),
 error_code VARCHAR(40),
 accepted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 lease_until TIMESTAMPTZ NOT NULL,
 PRIMARY KEY(conversation_id,request_id)
);
CREATE UNIQUE INDEX uq_ai_inflight ON ai_conversation_requests(conversation_id) WHERE status='IN_PROGRESS';
CREATE TABLE ai_conversation_messages (
 conversation_id UUID NOT NULL,
 request_id UUID NOT NULL,
 ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 100),
 message_role VARCHAR(9) NOT NULL CHECK(message_role IN ('user','assistant')),
 content TEXT,
 public_response JSONB,
 created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(conversation_id,ordinal),
 UNIQUE(conversation_id,request_id,message_role),
 FOREIGN KEY(conversation_id,request_id) REFERENCES ai_conversation_requests(conversation_id,request_id) ON DELETE CASCADE,
 CHECK((message_role='user' AND content IS NOT NULL AND char_length(content) BETWEEN 1 AND 1000 AND public_response IS NULL AND ordinal%2=1)
 OR (message_role='assistant' AND content IS NULL AND jsonb_typeof(public_response)='object' AND COALESCE(jsonb_typeof(public_response->'answer')='string',false) AND char_length(public_response->>'answer') BETWEEN 1 AND 6000 AND octet_length(public_response::text)<=65536 AND ordinal%2=0))
);

CREATE FUNCTION preserve_ai_conversation_scope() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.owner_id,NEW.portal_role,NEW.context_type,NEW.scope_merchant_id,NEW.payment_id,NEW.context)
 IS DISTINCT FROM (OLD.owner_id,OLD.portal_role,OLD.context_type,OLD.scope_merchant_id,OLD.payment_id,OLD.context) THEN
  RAISE EXCEPTION 'Conversation scope is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ai_conversation_scope_immutable BEFORE UPDATE ON ai_conversations FOR EACH ROW EXECUTE FUNCTION preserve_ai_conversation_scope();
