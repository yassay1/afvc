-- Tighten pending_actions to the P3 state machine and add a UI summary column.
-- 'approved' is not a persisted status: pending → executed happens in one transaction.

ALTER TABLE agent.pending_actions
    ADD COLUMN IF NOT EXISTS summary TEXT;

ALTER TABLE agent.pending_actions
    DROP CONSTRAINT IF EXISTS pending_actions_status_check;

ALTER TABLE agent.pending_actions
    ADD CONSTRAINT pending_actions_status_check
        CHECK (status IN ('pending', 'rejected', 'expired', 'executed', 'failed'));
