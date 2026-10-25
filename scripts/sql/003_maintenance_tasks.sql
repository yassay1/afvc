-- V1 maintenance closed-loop: adjustable tasks + execution feedback.
-- Distinct from agent.pending_actions (workorder HITL).

CREATE TABLE IF NOT EXISTS business.maintenance_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assetnum TEXT NOT NULL,
    station_name TEXT,
    fault_focus TEXT NOT NULL DEFAULT '暂停服务',
    priority INTEGER NOT NULL DEFAULT 100,
    planned_date DATE,
    assignee_crew_id TEXT,
    status TEXT NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'in_progress', 'done', 'cancelled')),
    suggestion_score DOUBLE PRECISION,
    suggestion_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    feedback_result TEXT,
    feedback_matched_fault BOOLEAN,
    feedback_followed_suggestion BOOLEAN,
    feedback_note TEXT,
    feedback_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_maintenance_tasks_status
    ON business.maintenance_tasks (status);

CREATE INDEX IF NOT EXISTS idx_maintenance_tasks_assetnum
    ON business.maintenance_tasks (assetnum);
