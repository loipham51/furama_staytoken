-- Fix QRClaim code field length issue
-- Run this to increase the code field length from 64 to 128 characters

-- 1. Increase code field length
ALTER TABLE qr_claim ALTER COLUMN code TYPE character varying(128);

-- 2. Add check constraint for code format
ALTER TABLE qr_claim ADD CONSTRAINT IF NOT EXISTS qr_claim_code_format_check 
    CHECK (code ~ '^[a-zA-Z0-9_-]+$');

-- 3. Add missing indexes for performance
CREATE INDEX IF NOT EXISTS idx_qr_claim_used_by_user ON qr_claim(used_by_user);
CREATE INDEX IF NOT EXISTS idx_qr_claim_voucher_type ON qr_claim(voucher_type_id);

-- 4. Analyze table for query optimization
ANALYZE qr_claim;
