-- =====================================================
-- Database Update for PC Users Support
-- Supabase PostgreSQL Database
-- =====================================================
-- INSTRUCTIONS:
-- 1. Go to Supabase Dashboard > SQL Editor
-- 2. Create a "New Query"
-- 3. Copy and paste this entire file
-- 4. Click "Run"
-- =====================================================

-- =====================================================
-- STEP 1: Update users table for PC users support
-- =====================================================

-- Make telegram_user_id nullable (PC users won't have it)
ALTER TABLE users 
    ALTER COLUMN telegram_user_id DROP NOT NULL;

-- Add mobile_number column for PC users
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(50);

-- Add user_type column (telegram or pc)
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'telegram';

-- Add unique constraint on mobile_number (for PC users)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_mobile_number 
    ON users(mobile_number) 
    WHERE mobile_number IS NOT NULL;

-- Update existing users to have user_type = 'telegram'
UPDATE users 
    SET user_type = 'telegram' 
    WHERE user_type IS NULL OR user_type = '';

-- =====================================================
-- STEP 2: Update phone_numbers table for PC users
-- =====================================================

-- Make telegram_user_id nullable in phone_numbers
ALTER TABLE phone_numbers 
    ALTER COLUMN telegram_user_id DROP NOT NULL;

-- Add mobile_number column (for PC users to track their own mobile)
ALTER TABLE phone_numbers 
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(50);

-- =====================================================
-- STEP 3: Update completed_numbers table for PC users
-- =====================================================

-- Make telegram_user_id nullable in completed_numbers
ALTER TABLE completed_numbers 
    ALTER COLUMN telegram_user_id DROP NOT NULL;

-- Add mobile_number column
ALTER TABLE completed_numbers 
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(50);

-- =====================================================
-- STEP 4: Update bot_sessions table for PC users
-- =====================================================

-- Make telegram_user_id nullable in bot_sessions
ALTER TABLE bot_sessions 
    ALTER COLUMN telegram_user_id DROP NOT NULL;

-- Add mobile_number column
ALTER TABLE bot_sessions 
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(50);

-- Update unique constraint to allow NULL telegram_user_id
-- First drop the constraint (if it exists as a constraint)
ALTER TABLE bot_sessions DROP CONSTRAINT IF EXISTS bot_sessions_telegram_user_id_key;
-- Drop index if it exists separately
DROP INDEX IF EXISTS bot_sessions_telegram_user_id_key;
-- Create new partial unique index that allows NULL
CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_sessions_telegram_id 
    ON bot_sessions(telegram_user_id) 
    WHERE telegram_user_id IS NOT NULL;

-- =====================================================
-- STEP 5: Update daily_reports table for PC users
-- =====================================================

-- Make telegram_user_id nullable in daily_reports
ALTER TABLE daily_reports 
    ALTER COLUMN telegram_user_id DROP NOT NULL;

-- Add mobile_number column
ALTER TABLE daily_reports 
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(50);

-- =====================================================
-- STEP 6: Update admin_notifications table for PC users
-- =====================================================

-- Add mobile_number column
ALTER TABLE admin_notifications 
    ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(50);

-- =====================================================
-- STEP 7: Create new indexes for PC users
-- =====================================================

-- Index for mobile_number in users table
CREATE INDEX IF NOT EXISTS idx_users_mobile_number_search 
    ON users(mobile_number) 
    WHERE mobile_number IS NOT NULL;

-- Index for user_type
CREATE INDEX IF NOT EXISTS idx_users_user_type 
    ON users(user_type);

-- Index for mobile_number in phone_numbers
CREATE INDEX IF NOT EXISTS idx_phone_numbers_mobile_number 
    ON phone_numbers(mobile_number) 
    WHERE mobile_number IS NOT NULL;

-- =====================================================
-- STEP 8: Update existing constraints (if needed)
-- =====================================================

-- Note: Some foreign key constraints might need adjustment
-- but we'll keep them as they reference user_id which remains the same

-- =====================================================
-- DONE! Database updated for PC users support.
-- =====================================================
-- Changes made:
-- 1. users table: Added mobile_number, user_type, made telegram_user_id nullable
-- 2. phone_numbers table: Made telegram_user_id nullable, added mobile_number
-- 3. completed_numbers table: Made telegram_user_id nullable, added mobile_number
-- 4. bot_sessions table: Made telegram_user_id nullable, added mobile_number
-- 5. daily_reports table: Made telegram_user_id nullable, added mobile_number
-- 6. admin_notifications table: Added mobile_number
-- 7. Created indexes for better performance
-- =====================================================

