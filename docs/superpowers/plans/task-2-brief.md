# Task 2 Brief: Use-case HTTP API; delete legacy routes

Work from: `d:\project\-AFVC`
Branch: `feat/afvc-architecture-rebuild`

## Plan
`docs/superpowers/plans/2026-08-11-afvc-architecture-rebuild.md` — **Task 2 only**.

## Depends on
Task 1 DONE: `backend.application.usecases` eight functions exist.

## Goal
- Create `backend/api/usecases_api.py` with all `/usecases/*` routes from the plan
- Create `backend/api/interaction_api.py` with `POST /interaction/turn` returning **501** (Task 3 fills it)
- Rewrite `backend/main.py` to register only: health, upload, usecases, interaction
- **Delete** old routers: predict/analysis/advice/device/data/agent_api (and any unused)
- Tests: `tests/api/test_usecases_api.py` — diagnosis 200; `/agent/diagnose` → 404
- Update/delete any tests that call old paths
- Commit with `git -c user.email="afvc@local" -c user.name="AFVC" commit ...` (no git config)

## Do NOT
- Implement interaction handle_turn
- Delete backend/agent yet

## Report
DONE / DONE_WITH_CONCERNS / BLOCKED + commit hash + test summary
