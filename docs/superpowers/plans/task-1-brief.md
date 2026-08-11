# Task 1 Brief: Application facade + sole diagnose aggregation

Work from: `d:\project\-AFVC`
Branch: `feat/afvc-architecture-rebuild`

## Full plan
`docs/superpowers/plans/2026-08-11-afvc-architecture-rebuild.md` — execute **Task 1 only**.

## Spec
`docs/architecture.md`

## Goal
Create `backend/application` use-case facade (`usecases.py` eight functions) and `diagnose_device` as the only aggregation. Move IO/adapters into `backend/infrastructure`. Use `domain.warning` only for warning levels. Do not change prediction algorithms.

## Important (controller ruling)
- Do **not** leave a dual public API. 
- After moving logic, update **internal** imports (`backend/api`, `backend/agent`, tests that import services) to call `backend.application.usecases` (or infrastructure) so the tree stays importable; then **delete** old `backend/services/` and migrated `backend/adapters/` files. This is not an old/new HTTP compat layer.
- Do **not** implement Interaction or delete `backend/agent` in this task.
- Commit when `pytest tests/application -v` passes. Also run a broader `pytest -q` and fix breakages from import moves.

## Use-case signatures
See plan section「用例门面」.

## Status report
Return DONE / DONE_WITH_CONCERNS / BLOCKED with tests run and commit hash.
