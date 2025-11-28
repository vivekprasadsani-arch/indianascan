-- Settings table for storing bot configuration
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS bot_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value VARCHAR(255) NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by BIGINT  -- Admin telegram user ID who made the change
);

-- Insert default working hours settings
INSERT INTO bot_settings (setting_key, setting_value, description) VALUES
    ('work_start_hour', '10', 'Working hours start hour (24-hour format)'),
    ('work_start_minute', '30', 'Working hours start minute'),
    ('work_end_hour', '23', 'Working hours end hour (24-hour format)'),
    ('work_end_minute', '0', 'Working hours end minute'),
    ('earnings_per_number', '10', 'Earnings per completed number in Taka')
ON CONFLICT (setting_key) DO NOTHING;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_bot_settings_key ON bot_settings(setting_key);

-- Function to update setting
CREATE OR REPLACE FUNCTION update_setting(
    p_key VARCHAR(100),
    p_value VARCHAR(255),
    p_admin_id BIGINT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    UPDATE bot_settings 
    SET setting_value = p_value, 
        updated_at = NOW(),
        updated_by = p_admin_id
    WHERE setting_key = p_key;
END;
$$ LANGUAGE plpgsql;

