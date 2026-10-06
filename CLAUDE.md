# CLAUDE.md — working instructions for this repo

Vesper brings customers back to pay when a PayPal payment fails, and is never allowed to touch their money. Read the four specs in order before writing code; they are the source of truth and already contain the decisions. The specs were written under the working name "Recoup"; read it as Vesper (package `vesper`, product name Vesper). See `docs/CHANGES.md`.

1. `docs/01_PRD.md` — what we are building and why; vocabulary; scope
2. `docs/02_TECHNICAL_ARCHITECTURE.md` — data model, API, PayPal integration, pipeline, rules, deployment
3. `docs/03_FRONTEND_SPEC.md` — three screens, exact copy, tokens, components
4. `docs/04_SECURITY.md` — invariants and the tests that enforce them

## Invariants (never violate, even if a task seems to require it)

- Sandbox only. No live PayPal host string anywhere under `api/`.
- The model is called from exactly two sites: `pipeline/diagnose.py` and `pipeline/propose.py`.
- Model output schemas have no numeric fields. Amounts come from the `cases` row, which came from PayPal.
- Four actions only: `SEND_INVOICE`, `WAIT`, `ESCALATE`, `NONE`.
- Rules read `failure_category_hint` from code, not the model's category.
- Messages are templates with approved placeholders; `messaging.validate` runs before any send; fallback on failure.
- Agent Toolkit read-only; allowlist asserted at startup.
- One call site for `send_invoice`; the kill-switch check lives inside it.
- `case_events` is append-only.
- No charts in the UI. Three screens plus Rules and the demo Store.

If a change would break one of these, stop and say so instead of working around it.

## Working style

- Before touching a PayPal request or the Agent Toolkit, check the item marked **verify** in `02_TECHNICAL_ARCHITECTURE.md` against the installed package or current PayPal docs. Do not invent field names.
- Use the vocabulary in `01_PRD.md` §16 everywhere: Case, Failed, Diagnosed, Proposed, Checked, Recovered, Held, Escalated, Closed, Rule, Verdict, Touch, Invoice, Kill switch.
- Prefer deleting over adding. If a feature is not in the PRD's Phase 1, do not build it without asking.
- Write the invariant test before the feature it protects when the two land together.
- Record any decision that changes a spec in `docs/CHANGES.md` with the date and one sentence of reasoning. Do not edit the four specs in place during the hackathon.

## Commands

```
# api
cd api && uv sync && uv run alembic upgrade head
LLM_PROVIDER=fixture uv run pytest -q
uv run uvicorn vesper.main:app --reload

# web
cd web && npm install && npm run dev

# scripts (need sandbox credentials in api/.env)
uv run python -m scripts.register_webhook
uv run python -m scripts.seed_demo
uv run python -m scripts.e2e_sandbox
```

## Build order (from the PRD)

Day 1 sandbox checkout + forced decline + webhook listener + case persisted →
Day 2 rules engine with tests, before any model code →
Day 3 two model calls, slot messages, real invoice, buyer pays, webhook recovers →
Day 4 Floor and Case screens →
Day 5 Approvals, Fail-a-payment, subscription path →
Day 6 video, README with GIF above the fold and a ten-line quickstart.

If behind: cut Approvals first, then the subscription path, then multi-language. Never cut the live loop, the eight rules, the Held-back counter, or the Fail-a-payment button.
