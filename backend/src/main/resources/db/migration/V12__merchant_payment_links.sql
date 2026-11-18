-- Link management only. No existing payment, account or financial row is changed.
CREATE TABLE payment_links (
 link_id UUID PRIMARY KEY,
 merchant_id VARCHAR(100) COLLATE "C" NOT NULL REFERENCES merchants(merchant_id),
 public_token VARCHAR(43) COLLATE "C" NOT NULL UNIQUE CHECK(public_token ~ '^[A-Za-z0-9_-]{43}$'),
 amount NUMERIC(14,2) NOT NULL CHECK(amount>=0.01 AND amount<=999999999999.99),
 currency VARCHAR(3) NOT NULL CHECK(currency IN ('INR','USD')),
 payment_method VARCHAR(10) NOT NULL CHECK(payment_method IN ('UPI','CARD')),
 gateway_name VARCHAR(30) NOT NULL,
 customer_reference VARCHAR(100) NOT NULL,
 description VARCHAR(500) NOT NULL,
 status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','CANCELLED','EXPIRED','PAID')),
 expires_at TIMESTAMPTZ NOT NULL,
 created_at TIMESTAMPTZ NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL,
 payment_id UUID UNIQUE REFERENCES payments(payment_id),
 idempotency_key VARCHAR(128) COLLATE "C" NOT NULL,
 request_fingerprint CHAR(64) NOT NULL CHECK(request_fingerprint ~ '^[a-f0-9]{64}$'),
 UNIQUE(merchant_id,idempotency_key),
 CHECK(expires_at>created_at),
 CHECK((currency='INR' AND gateway_name='MOCK_RAZORPAY') OR
       (currency='USD' AND payment_method='CARD' AND gateway_name='MOCK_STRIPE')),
 CHECK((status='PAID')=(payment_id IS NOT NULL))
);
CREATE INDEX idx_payment_links_owned ON payment_links(merchant_id,created_at DESC,link_id);
CREATE INDEX idx_payment_links_expiry ON payment_links(merchant_id,status,expires_at);
