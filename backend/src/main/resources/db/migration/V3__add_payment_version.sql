
-- V3: Add optimistic locking support to payments

ALTER TABLE payments
ADD COLUMN version BIGINT NOT NULL DEFAULT 0;
