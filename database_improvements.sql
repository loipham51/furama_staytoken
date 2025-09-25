-- Database Schema Improvements for Furama StayToken
-- Run these commands to improve database performance and constraints

-- 1. Add missing indexes for qr_claim table
CREATE INDEX IF NOT EXISTS idx_qr_claim_used_by_user ON qr_claim(used_by_user);
CREATE INDEX IF NOT EXISTS idx_qr_claim_voucher_type ON qr_claim(voucher_type_id);
CREATE INDEX IF NOT EXISTS idx_qr_claim_created_at ON qr_claim(created_at);

-- 2. Add composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_qr_claim_user_voucher ON qr_claim(used_by_user, voucher_type_id);
CREATE INDEX IF NOT EXISTS idx_qr_claim_status_created ON qr_claim(status, created_at);
CREATE INDEX IF NOT EXISTS idx_voucher_balance_wallet_type ON voucher_balance(wallet_id, voucher_type_id);

-- 3. Add partial indexes for active records
CREATE INDEX IF NOT EXISTS idx_voucher_type_active ON voucher_type(id) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_wallet_active ON wallet(id) WHERE export_status != 'denied';

-- 4. Increase code field length for safety
ALTER TABLE qr_claim ALTER COLUMN code TYPE character varying(128);

-- 5. Add check constraints
ALTER TABLE qr_claim ADD CONSTRAINT IF NOT EXISTS qr_claim_code_format_check 
    CHECK (code ~ '^[a-zA-Z0-9_-]+$');

ALTER TABLE qr_claim ADD CONSTRAINT IF NOT EXISTS qr_claim_status_used_at_check 
    CHECK ((status = 'used' AND used_at IS NOT NULL) OR (status != 'used'));

ALTER TABLE voucher_balance ADD CONSTRAINT IF NOT EXISTS voucher_balance_positive_check 
    CHECK (balance >= 0);

-- 5. Add NOT NULL constraints where appropriate
ALTER TABLE qr_claim ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE qr_claim ALTER COLUMN voucher_type_id SET NOT NULL;

-- 6. Update status values to be consistent
-- Note: This might require data migration if you have existing 'claimed' status
-- UPDATE qr_claim SET status = 'used' WHERE status = 'claimed';

-- 7. Add comments for documentation
COMMENT ON TABLE qr_claim IS 'Tracks voucher claims and their status';
COMMENT ON COLUMN qr_claim.code IS 'Unique claim code for tracking';
COMMENT ON COLUMN qr_claim.status IS 'Claim status: new, used, expired, revoked';
COMMENT ON COLUMN qr_claim.used_by_user IS 'User who claimed this voucher';
COMMENT ON COLUMN qr_claim.used_at IS 'When the voucher was used/redeemed';

COMMENT ON TABLE voucher_balance IS 'Current voucher balances per wallet';
COMMENT ON COLUMN voucher_balance.balance IS 'Number of vouchers owned (must be >= 0)';

-- 8. Analyze tables for query optimization
ANALYZE qr_claim;
ANALYZE voucher_balance;
ANALYZE voucher_type;
ANALYZE wallet;
ANALYZE app_user;
