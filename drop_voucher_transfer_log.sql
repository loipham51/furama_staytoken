-- Drop voucher_transfer_log table
-- This table is no longer needed as we use QRClaim for tracking instead

-- 1. Check if table exists and show current data
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename = 'voucher_transfer_log';

-- 2. Show current data count (for reference)
SELECT COUNT(*) as current_records FROM voucher_transfer_log;

-- 3. Drop the table
DROP TABLE IF EXISTS voucher_transfer_log CASCADE;

-- 4. Verify table is dropped
SELECT 
    schemaname,
    tablename
FROM pg_tables 
WHERE tablename = 'voucher_transfer_log';

-- 5. Show remaining tables for verification
SELECT 
    tablename,
    tableowner
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;
