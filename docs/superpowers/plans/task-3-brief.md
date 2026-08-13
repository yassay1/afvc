# Task 3 Brief: Thin Interaction; delete entire backend/agent

Work from: `d:\project\-AFVC`
Branch: `feat/afvc-architecture-rebuild`

## Plan
Task 3 in `docs/superpowers/plans/2026-08-11-afvc-architecture-rebuild.md`

## Goal
1. Create `backend/interaction/` — understand (rules first), narrate, `handle_turn`
2. Create `backend/infrastructure/session_memory.py`
3. Wire `POST /interaction/turn` to `handle_turn` (replace 501)
4. **Delete entire `backend/agent/`** — no graph, tools, nodes, report_builder as agent skeleton
5. Delete all `tests/test_agent_*.py` and other agent-only tests; fix fallout
6. Optional: move llm helpers to infrastructure if narrate needs them; LLM off by default with template narrate

## Forbidden
- tool registry / plan_tools / evaluate_evidence / replan / EvidencePacket main path
- Hand-assembling diagnose from multiple use cases inside interaction (call `usecases.diagnose_device`)

## Tests required (AFVC_USE_LLM=false)
See plan Task 3 Step 1 examples: diagnose intent, follow-up last_assetnum, missing asset clarified.

## Commit
`git -c user.email="afvc@local" -c user.name="AFVC" commit ...` — never git config

## Report
DONE / DONE_WITH_CONCERNS / BLOCKED + hash + pytest
