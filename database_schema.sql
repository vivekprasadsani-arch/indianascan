-- =====================================================
-- Database Schema for Telegram QR Code Bot
-- Supabase PostgreSQL Database
-- =====================================================
-- INSTRUCTIONS:
-- 1. Go to Supabase Dashboard > SQL Editor
-- 2. Create a "New Query"
-- 3. Copy and paste this entire file
-- 4. Click "Run"
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- STEP 1: Drop existing tables (run this first if you have old tables)
-- =====================================================
DROP TABLE IF EXISTS admin_notifications CASCADE;
DROP TABLE IF EXISTS daily_reports CASCADE;
DROP TABLE IF EXISTS bot_sessions CASCADE;
DROP TABLE IF EXISTS completed_numbers CASCADE;
DROP TABLE IF EXISTS website_completions CASCADE;
DROP TABLE IF EXISTS phone_numbers CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- =====================================================
-- STEP 2: Create tables (in proper order)
-- =====================================================

-- Users table - stores bot users with approval system
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    total_earnings DECIMAL(10, 2) DEFAULT 0.00,
    approved_at TIMESTAMP WITH TIME ZONE,
    approved_by BIGINT,
    rejected_at TIMESTAMP WITH TIME ZONE,
    rejected_by BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Phone numbers table - stores phone numbers added by users
CREATE TABLE phone_numbers (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    telegram_user_id BIGINT NOT NULL,
    phone_number VARCHAR(50) NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    websites_completed INTEGER DEFAULT 0,
    earnings_added BOOLEAN DEFAULT FALSE,
    reset_date DATE NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Website completions table
CREATE TABLE website_completions (
    id BIGSERIAL PRIMARY KEY,
    phone_number_id BIGINT NOT NULL,
    website_index INTEGER NOT NULL,
    website_name VARCHAR(100),
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    phone_detected VARCHAR(50),
    name_detected VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Completed numbers table
CREATE TABLE completed_numbers (
    id BIGSERIAL PRIMARY KEY,
    phone_number_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    telegram_user_id BIGINT NOT NULL,
    phone_number VARCHAR(50) NOT NULL,
    earnings DECIMAL(10, 2) DEFAULT 10.00,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reset_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Bot sessions table
CREATE TABLE bot_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    current_website_index INTEGER DEFAULT 0,
    current_phone_number VARCHAR(50),
    current_phone_number_id BIGINT,
    is_polling BOOLEAN DEFAULT FALSE,
    last_message_id BIGINT,
    poll_count INTEGER DEFAULT 0,
    completed_websites INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    session_data JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Daily reports table
CREATE TABLE daily_reports (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    user_id BIGINT NOT NULL,
    telegram_user_id BIGINT NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    total_numbers_added INTEGER DEFAULT 0,
    total_numbers_completed INTEGER DEFAULT 0,
    total_earnings DECIMAL(10, 2) DEFAULT 0.00,
    report_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Admin notifications table
CREATE TABLE admin_notifications (
    id BIGSERIAL PRIMARY KEY,
    notification_type VARCHAR(50) NOT NULL,
    user_id BIGINT,
    telegram_user_id BIGINT,
    message TEXT,
    is_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- STEP 3: Add Foreign Key Constraints
-- =====================================================

ALTER TABLE phone_numbers 
    ADD CONSTRAINT fk_phone_numbers_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE website_completions 
    ADD CONSTRAINT fk_website_completions_phone 
    FOREIGN KEY (phone_number_id) REFERENCES phone_numbers(id) ON DELETE CASCADE;

ALTER TABLE completed_numbers 
    ADD CONSTRAINT fk_completed_numbers_phone 
    FOREIGN KEY (phone_number_id) REFERENCES phone_numbers(id) ON DELETE CASCADE;

ALTER TABLE completed_numbers 
    ADD CONSTRAINT fk_completed_numbers_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE bot_sessions 
    ADD CONSTRAINT fk_bot_sessions_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE daily_reports 
    ADD CONSTRAINT fk_daily_reports_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE admin_notifications 
    ADD CONSTRAINT fk_admin_notifications_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- =====================================================
-- STEP 4: Add Unique Constraints
-- =====================================================

ALTER TABLE website_completions 
    ADD CONSTRAINT unique_website_completion 
    UNIQUE (phone_number_id, website_index);

ALTER TABLE daily_reports 
    ADD CONSTRAINT unique_daily_report 
    UNIQUE (report_date, user_id);

-- =====================================================
-- STEP 5: Create Indexes for Performance
-- =====================================================

CREATE INDEX idx_users_telegram_id ON users(telegram_user_id);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_phone_numbers_user_id ON phone_numbers(user_id);
CREATE INDEX idx_phone_numbers_telegram_user_id ON phone_numbers(telegram_user_id);
CREATE INDEX idx_phone_numbers_reset_date ON phone_numbers(reset_date);
CREATE INDEX idx_phone_numbers_is_completed ON phone_numbers(is_completed);
CREATE INDEX idx_website_completions_phone_id ON website_completions(phone_number_id);
CREATE INDEX idx_completed_numbers_user_id ON completed_numbers(user_id);
CREATE INDEX idx_completed_numbers_telegram_user_id ON completed_numbers(telegram_user_id);
CREATE INDEX idx_completed_numbers_reset_date ON completed_numbers(reset_date);
CREATE INDEX idx_bot_sessions_telegram_id ON bot_sessions(telegram_user_id);
CREATE INDEX idx_daily_reports_date ON daily_reports(report_date);
CREATE INDEX idx_daily_reports_user_id ON daily_reports(user_id);

-- =====================================================
-- STEP 6: Create Functions and Triggers
-- =====================================================

-- Function to auto-update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bot_sessions_updated_at 
    BEFORE UPDATE ON bot_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_daily_reports_updated_at 
    BEFORE UPDATE ON daily_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- STEP 7: Enable Row Level Security (RLS) - Optional
-- =====================================================
-- Supabase recommends enabling RLS for security
-- For this bot, we use service role key so RLS is bypassed

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE phone_numbers ENABLE ROW LEVEL SECURITY;
ALTER TABLE website_completions ENABLE ROW LEVEL SECURITY;
ALTER TABLE completed_numbers ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_notifications ENABLE ROW LEVEL SECURITY;

-- Create policies to allow all operations (for service role)
CREATE POLICY "Allow all for service role" ON users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service role" ON phone_numbers FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service role" ON website_completions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service role" ON completed_numbers FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service role" ON bot_sessions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service role" ON daily_reports FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for service role" ON admin_notifications FOR ALL USING (true) WITH CHECK (true);

-- =====================================================
-- DONE! Tables created successfully.
-- =====================================================
-- Tables created:
-- 1. users - Bot users with approval status
-- 2. phone_numbers - Phone numbers added by users
-- 3. website_completions - Website scan tracking
-- 4. completed_numbers - Fully completed numbers
-- 5. bot_sessions - User session data
-- 6. daily_reports - Daily statistics
-- 7. admin_notifications - Admin notifications
-- =====================================================
