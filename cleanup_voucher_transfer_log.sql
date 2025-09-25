-- Simple cleanup script for voucher_transfer_log table
-- Run this to safely remove the table

-- Step 1: Create backup (just in case)
CREATE TABLE IF NOT EXISTS voucher_transfer_log_backup AS 
SELECT * FROM voucher_transfer_log;

-- Step 2: Show what we're backing up
SELECT 'Backup created with records:' as status, COUNT(*) as count 
FROM voucher_transfer_log_backup;

-- Step 3: Drop the original table
DROP TABLE IF EXISTS voucher_transfer_log CASCADE;

-- Step 4: Verify it's gone
SELECT 'voucher_transfer_log table status:' as status,
       CASE 
           WHEN EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'voucher_transfer_log') 
           THEN 'STILL EXISTS' 
           ELSE 'SUCCESSFULLY DROPPED' 
       END as result;

-- Step 5: Show remaining tables
SELECT 'Remaining tables:' as status;
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
