-- Update QRClaim status constraint to only allow: new, used, expired

-- 1. Drop existing constraints
ALTER TABLE qr_claim DROP CONSTRAINT IF EXISTS qr_claim_status_check;
ALTER TABLE qr_claim DROP CONSTRAINT IF EXISTS qr_claim_status_used_at_check;

-- 2. Add new constraint with only 3 values
ALTER TABLE qr_claim ADD CONSTRAINT qr_claim_status_check 
CHECK (status IN ('new', 'used', 'expired'));

-- 3. Add constraint to ensure used_at is set when status = 'used'
ALTER TABLE qr_claim ADD CONSTRAINT qr_claim_status_used_at_check 
CHECK ((status != 'used') OR (status = 'used' AND used_at IS NOT NULL));

-- 4. Update existing 'claimed' records to 'used' and set used_at
UPDATE qr_claim SET status = 'used', used_at = NOW() WHERE status = 'claimed';

-- 5. Update existing 'revoked' records to 'expired'
UPDATE qr_claim SET status = 'expired' WHERE status = 'revoked';

-- 6. Verify the constraint
SELECT DISTINCT status FROM qr_claim ORDER BY status;
