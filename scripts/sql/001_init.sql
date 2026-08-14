-- AFVC initial schema: business workorders + agent placeholders.
-- Checkpointer tables are created by LangGraph PostgresSaver.setup(), not here.

CREATE SCHEMA IF NOT EXISTS business;
CREATE SCHEMA IF NOT EXISTS agent;

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS business.import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_filename TEXT NOT NULL,
    stored_path TEXT,
    mode TEXT NOT NULL CHECK (mode IN ('replace', 'append')),
    row_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id UUID NULL
);

CREATE TABLE IF NOT EXISTS business.workorders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_batch_id UUID NOT NULL REFERENCES business.import_batches (id) ON DELETE CASCADE,
    assetnum TEXT,
    station_name TEXT,
    cust_linenum TEXT,
    current_faildate TEXT,
    prev_faildate TEXT,
    total_failure_count TEXT,
    description TEXT,
    cust_brand TEXT,
    cust_subsys TEXT,
    worktype TEXT,
    pre_type TEXT,
    pre_value TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id UUID NULL
);

CREATE INDEX IF NOT EXISTS idx_workorders_assetnum
    ON business.workorders (assetnum);

CREATE INDEX IF NOT EXISTS idx_workorders_current_faildate
    ON business.workorders (current_faildate);

CREATE INDEX IF NOT EXISTS idx_workorders_import_batch
    ON business.workorders (import_batch_id);

-- P3 HITL table is created now so later rounds do not migrate identity.
-- This round does not expose approve/reject or write tools.
CREATE TABLE IF NOT EXISTS agent.pending_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'executed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    actor_id UUID NULL,
    result JSONB
);

CREATE INDEX IF NOT EXISTS idx_pending_actions_thread
    ON agent.pending_actions (thread_id, status);
