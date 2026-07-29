-- Run this in Supabase SQL Editor

-- Core tables
CREATE TABLE IF NOT EXISTS users (
    user_id_hash TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    doc_name TEXT NOT NULL,
    user_name TEXT NOT NULL,
    user_id_hash TEXT NOT NULL REFERENCES users(user_id_hash) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forget_codes (
    id BIGSERIAL PRIMARY KEY,
    user_id_hash TEXT NOT NULL REFERENCES users(user_id_hash) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_documents_user_hash ON documents(user_id_hash);
CREATE INDEX IF NOT EXISTS idx_documents_code ON documents(code);
CREATE INDEX IF NOT EXISTS idx_forget_codes_code ON forget_codes(code);
CREATE INDEX IF NOT EXISTS idx_forget_codes_user_hash ON forget_codes(user_id_hash);

-- Rate-limiting table for tracking attempts
CREATE TABLE IF NOT EXISTS rate_limits (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL,
    attempts INT DEFAULT 1,
    window_start TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_key ON rate_limits(key);

-- VULN-008: Prevent TOCTOU race condition on user registration
ALTER TABLE users ADD CONSTRAINT users_user_id_hash_key UNIQUE (user_id_hash);

-- Grant anon role full access to all tables
GRANT USAGE ON SCHEMA public TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon;
