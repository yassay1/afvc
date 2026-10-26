-- Fixed-account gate: users + server-side sessions (no self-registration).

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT auth_users_username_nonempty CHECK (length(trim(username)) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_users_username_lower
    ON auth.users (lower(username));

CREATE TABLE IF NOT EXISTS auth.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_sessions_token_hash
    ON auth.sessions (token_hash);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
    ON auth.sessions (user_id);
