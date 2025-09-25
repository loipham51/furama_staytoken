-- Migration script: voucher_transfer_log -> QRClaim
-- This script migrates any existing data before dropping the old table

-- 1. Check current data
SELECT 'Current voucher_transfer_log records:' as info;
SELECT COUNT(*) as count FROM voucher_transfer_log;

-- 2. Show sample data
SELECT 'Sample records:' as info;
SELECT 
    id,
    from_wallet_id,
    to_wallet_id,
    voucher_type_id,
    amount,
    reason,
    pos_ref,
    created_at
FROM voucher_transfer_log 
LIMIT 5;

-- 3. Check if we have any 'claim' records that need migration
SELECT 'Claim records to migrate:' as info;
SELECT COUNT(*) as claim_count 
FROM voucher_transfer_log 
WHERE reason = 'claim';

-- 4. If you want to migrate data to QRClaim (optional):
-- Note: This is complex because QRClaim has different structure
-- You might want to just backup the data instead

-- Create backup table
CREATE TABLE IF NOT EXISTS voucher_transfer_log_backup AS 
SELECT * FROM voucher_transfer_log;

SELECT 'Backup created with' as info, COUNT(*) as records FROM voucher_transfer_log_backup;

-- 5. Drop the original table
DROP TABLE IF EXISTS voucher_transfer_log CASCADE;

-- 6. Verify
SELECT 'Tables after cleanup:' as info;
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
