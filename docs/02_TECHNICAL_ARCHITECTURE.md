# Recoup — Technical Architecture

**Read `01_PRD.md` first.** This document says how to build it. Where a PayPal detail is marked **verify**, check the current PayPal docs or the installed package before coding; do not guess field names.

---

## 1. Shape

Two deployables, one repo.

```
recoup/
  api/            FastAPI, Python 3.12, uv-managed
  web/            Next.js 15 (App Router), TypeScript, Tailwind
  scripts/        one-off operational scripts (register webhook, seed demo, e2e)
  docs/           these four documents + CHANGES.md
  postman/        Postman collection for judges
  render.yaml     Render blueprint: api (web service) + web (web service)
  CLAUDE.md       working instructions for Claude Code
  README.md
  LICENSE         MIT
```

The API owns all state and all PayPal/LLM calls. The web app is a thin client that polls the API. Nothing in `web/` ever holds a PayPal secret or calls PayPal directly, except the PayPal JS SDK on the demo store page, which uses only the public client ID.

## 2. Stack and why

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | Schema validation of model output is the core safety mechanism; Pydantic does it well. |
| DB | SQLAlchemy 2 + Alembic. SQLite locally, Postgres on Render. | One ORM, two engines, no code change. |
| Background work | A single asyncio loop task started on app startup (`scheduler.py`), ticking every 15 s. No Celery, no Redis. | Deferred sends and TTLs only need a tick. |
| HTTP to PayPal | `httpx` with a thin `PayPalClient`. | Explicit, inspectable requests. SDKs hide headers we need (negative testing). |
| Agent Toolkit | `paypal-agent-toolkit` (Python), read-only tools only, used inside model call 2. **verify** the exact class/tool names in the installed package. | Puts PayPal's own agent tooling visibly in the loop without granting it writes. |
| LLM | Provider interface with one default implementation (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`). Groq or Anthropic; either works. | Swappable; tests use a fixture provider. |
| Web | Next.js 15, Tailwind, SWR for polling (3 s). No chart library. | Three screens, simple. |
| Hosting | Render for both services (sponsor). Vercel acceptable for `web/` if Render static hosting is awkward. | Webhook URL must be public and stable. |

## 3. Data model

All tables in `api/recoup/models.py`. Money is `Numeric(12,2)` plus a 3-letter currency. Times are UTC `DateTime(timezone=True)`.

### `customers`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| display_name | str | first name is derived for messages |
| email | str | for demo customers this is always `SANDBOX_BUYER_EMAIL` |
| country_code | str(2) | ISO 3166-1 |
| timezone | str | IANA, e.g. `Europe/Madrid` |
| locale | str | BCP-47, e.g. `es-ES` |
| email_consent | bool | |
| opted_out | bool | |
| created_at | datetime | |

### `cases`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| source | enum | `checkout_decline` `capture_denied` `subscription_failed` `capture_pending` `checkout_abandoned` `seeded` |
| customer_id | fk | |
| amount | numeric | from PayPal, never from the model |
| currency | str(3) | |
| description | str | what was being bought (order item name or plan name) |
| paypal_order_id | str nullable | |
| paypal_capture_id | str nullable | |
| paypal_subscription_id | str nullable | |
| paypal_invoice_id | str nullable | set when an invoice is created |
| failure_code | str | e.g. `INSTRUMENT_DECLINED`, `PAYER_ACTION_REQUIRED`, `DENIED`, `PENDING`, `SUBSCRIPTION_PAYMENT_FAILED` |
| failure_category_hint | enum | `soft` `hard` `pending` `unknown` — from the code table in §6.1, computed before the model sees anything |
| stage | enum | `failed` `diagnosed` `proposed` `checked` `awaiting_approval` `scheduled` `sent` `waiting` `recovered` `held` `escalated` `closed` |
| diagnosis | json nullable | validated `Diagnosis` |
| proposal | json nullable | validated `Proposal` |
| verdicts | json nullable | list of `Verdict` + `final` |
| message | json nullable | `{template, rendered, language, fallback_used, scheduled_for, sent_at, payer_link}` |
| recovered_at | datetime nullable | |
| closed_at | datetime nullable | |
| closed_reason | str nullable | |
| created_at, updated_at | datetime | |

### `case_events` (append-only)
| column | type |
|---|---|
| id | uuid pk |
| case_id | fk |
| at | datetime |
| kind | str (`created` `diagnosed` `proposed` `checked` `approval_requested` `approved` `declined` `scheduled` `sent` `recovered` `held` `escalated` `closed` `toolkit_call` `webhook`) |
| text | str — one plain-English sentence, shown in the timeline |
| data | json nullable — redacted detail |

There is no UPDATE or DELETE route for this table anywhere in the codebase. A test greps for it.

### `touches`
| column | type |
|---|---|
| id | uuid pk |
| case_id | fk |
| customer_id | fk |
| sent_at | datetime |

### `processed_webhooks`
| column | type |
|---|---|
| event_id | str pk — PayPal event id |
| received_at | datetime |

Idempotency for webhooks: insert first; if the id exists, acknowledge 200 and do nothing.

### Stage → five-dot indicator mapping (shared with the frontend)

| stage | dot filled | status label |
|---|---|---|
| failed | 1 | Failed |
| diagnosed | 2 | Diagnosed |
| proposed | 3 | Proposed |
| checked, awaiting_approval, scheduled, sent, waiting | 4 | Checked · *sub-label*: Waiting for approval / Queued for 09:00 local / Invoice sent / Waiting for payment to clear |
| recovered | 5 | Recovered |
| held, escalated, closed | 4, terminal style | Held / Escalated / Closed |

## 4. API

Base path `/api`. All routes except `/api/health`, `/webhooks/paypal`, and `/api/demo/store/*` require `X-Dashboard-Token: $DASHBOARD_TOKEN`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{ok, env: "sandbox", kill_switch, demo_mode}` |
| POST | `/webhooks/paypal` | PayPal webhook listener. Verifies, dedupes, dispatches. Always returns 200 after verification succeeds; returns 400 if verification fails. |
| GET | `/api/metrics/today` | `{recovered_total, recovered_count, held_back_count, currency}` for the merchant's local day |
| GET | `/api/cases?stage=&limit=50&cursor=` | Floor list, newest first |
| GET | `/api/cases/{id}` | Case with customer (redacted), verdicts, message, events |
| POST | `/api/cases/{id}/approve` | Only valid in `awaiting_approval`. Moves to `scheduled` or `sent`. |
| POST | `/api/cases/{id}/decline` | Only valid in `awaiting_approval`. Moves to `held`. |
| GET | `/api/rules` | The eight rules: id, name, plain-English description |
| GET | `/api/settings` | `{approval_threshold, contact_window: {start: "09:00", end: "20:00"}, kill_switch, merchant_name}` |
| POST | `/api/demo/fail` | Body `{kind: "subscription" \| "capture_denied"}`. Demo mode only. Rate-limited (§7). |
| POST | `/api/demo/store/orders` | Creates a PayPal order for the demo product. Returns `{order_id}`. |
| POST | `/api/demo/store/orders/{id}/capture?force_decline=true\|false` | Captures. With `force_decline`, sends the negative-testing header. On a recoverable error, creates a case and returns `{status: "failed", case_id}`. |

Errors are JSON `{error: {code, message}}`. No stack traces to clients.

## 5. PayPal integration (`api/recoup/paypal/`)

### 5.1 `client.py`
- OAuth client credentials: `POST {base}/v1/oauth2/token`, cached until expiry minus 60 s.
- `base` is always `https://api-m.sandbox.paypal.com`. There is no live base URL constant in the codebase (see `04_SECURITY.md` §2).
- Every write request sets `PayPal-Request-Id` to a deterministic key (`case:{id}:invoice:create` etc.) so retries are idempotent on PayPal's side.
- Negative testing: when `force_decline` is requested, add header `PayPal-Mock-Response: {"mock_application_codes": "INSTRUMENT_DECLINED"}` to the capture call. Sandbox honours this header and returns the error instead of capturing. **verify** the exact error code list on PayPal's negative-testing page; `INSTRUMENT_DECLINED` and `TRANSACTION_REFUSED` are documented.

### 5.2 `orders.py` (demo store only)
- `create_order(amount, currency, description)` → `POST /v2/checkout/orders`, intent `CAPTURE`, one purchase unit.
- `capture_order(order_id, force_decline)` → `POST /v2/checkout/orders/{id}/capture`. Map outcomes:
  - 201 with `status: COMPLETED` → success, no case.
  - 201 with capture `status: PENDING` → create case `capture_pending`.
  - 422 with issue `INSTRUMENT_DECLINED` or `PAYER_ACTION_REQUIRED` → create case `checkout_decline` (soft).
  - 422 with `TRANSACTION_REFUSED`, `PAYER_CANNOT_PAY`, or a `DENIED` capture → create case `checkout_decline` with hard hint.
  - Anything else → log, return a generic failure, no case.

### 5.3 `invoicing.py` (the only customer-facing channel)
- `create_invoice(case, note)`:
  - `POST /v2/invoicing/generate-next-invoice-number` → number (**verify** path).
  - `POST /v2/invoicing/invoices` with: detail (currency, invoice number, `note` = rendered message, `memo` = internal reference `case:{id}`), invoicer (merchant from env), primary recipient = `customer.email`, one item (`description`, quantity 1, `unit_amount` from `case.amount`), due in 7 days.
  - The item amount is read from the `cases` row inside this function. There is no parameter for an amount on any function the pipeline calls. This is enforced by a test (`04_SECURITY.md` §6).
- `send_invoice(invoice_id)` → `POST /v2/invoicing/invoices/{id}/send` with `send_to_recipient: true`. PayPal emails the customer. Store the payer view link from the response or from `GET /v2/invoicing/invoices/{id}` (**verify** which field carries the recipient link; likely under `detail.metadata.recipient_view_url`).
- Payment arrives as webhook `INVOICING.INVOICE.PAID` → case `recovered`. Cancellation `INVOICING.INVOICE.CANCELLED` → case `closed`.

### 5.4 `webhooks.py`
- Register once with `scripts/register_webhook.py` → `POST /v1/notifications/webhooks` with the public listener URL and event types below. Store the returned id as `PAYPAL_WEBHOOK_ID`.
- Event types subscribed: `PAYMENT.CAPTURE.DENIED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.REFUNDED`, `BILLING.SUBSCRIPTION.PAYMENT.FAILED`, `INVOICING.INVOICE.PAID`, `INVOICING.INVOICE.CANCELLED`, `CUSTOMER.DISPUTE.CREATED`. **verify** names against the current event catalogue.
- Verification: every inbound event is verified with `POST /v1/notifications/verify-webhook-signature`, passing the transmission headers (`PAYPAL-TRANSMISSION-ID`, `-TIME`, `-SIG`, `PAYPAL-CERT-URL`, `PAYPAL-AUTH-ALGO`), the webhook id, and the raw body. `verification_status != "SUCCESS"` → 400, event discarded, logged.
- Dispatch table:

| event | handler |
|---|---|
| `PAYMENT.CAPTURE.DENIED` | create case `capture_denied`, hard hint |
| `PAYMENT.CAPTURE.PENDING` | create case `capture_pending` |
| `PAYMENT.CAPTURE.COMPLETED` | if a case exists for the order → close `paid_elsewhere` (rule 6 data) |
| `PAYMENT.CAPTURE.REFUNDED` | close any open case for the order, `refunded` |
| `BILLING.SUBSCRIPTION.PAYMENT.FAILED` | create case `subscription_failed`; amount from the resource's billing info (**verify** field; fall back to the plan's fixed price via `GET /v1/billing/subscriptions/{id}`) |
| `INVOICING.INVOICE.PAID` | case by `paypal_invoice_id` → `recovered` |
| `INVOICING.INVOICE.CANCELLED` | → `closed` |
| `CUSTOMER.DISPUTE.CREATED` | mark the related case frozen; rule 6 refuses |

- Customer resolution: for demo and sandbox, map the payer email in the resource to a `customers` row; if none, create one with `email_consent=true` and a timezone derived from the payer country (static table in `tz_by_country.py`, with `UTC` fallback). For simulated events whose sample resource carries no real payer, use the demo customer rotation (§7).

### 5.5 Agent Toolkit (`api/recoup/llm/toolkit.py`)
- Instantiate the PayPal Agent Toolkit with sandbox credentials and **only read tools enabled** (order details, invoice details/list, transaction list if offered). **verify** the toolkit's configuration object and tool names in the installed package; mirror them in `READ_ONLY_TOOL_ALLOWLIST`.
- On startup, assert that every enabled tool name is in the allowlist. If the package exposes anything that creates, captures, sends, refunds, or pays, it must be disabled. Startup fails otherwise.
- The toolkit is passed to model call 2 only. Maximum two tool calls per case; each call is written to `case_events` as `toolkit_call` with the tool name and the sanitised arguments, so the UI can show "Checked order details with PayPal".
- If the toolkit cannot be imported or configured, call 2 runs without tools. Log once.

## 6. The pipeline (`api/recoup/pipeline/`)

Runs synchronously inside the request/webhook handler up to `checked`, then hands off to the scheduler for sends. Target: failure → checked in under 10 seconds.

### 6.1 `taxonomy.py` — computed before the model
```
HARD   = {TRANSACTION_REFUSED, PAYER_CANNOT_PAY, DENIED, CAPTURE_DENIED}
SOFT   = {INSTRUMENT_DECLINED, PAYER_ACTION_REQUIRED, SUBSCRIPTION_PAYMENT_FAILED}
PENDING= {PENDING}
```
Anything else → `unknown`. The hint is stored on the case and given to the model as context; rule 1 and rule 2 use the hint, not the model's category, so a hallucinated "soft" cannot unlock outreach on a hard failure.

### 6.2 `evidence.py` — what the model is allowed to see
```
EvidencePacket:
  source, failure_code, failure_category_hint
  amount, currency, description
  customer: first_name, country_code, timezone, local_time_now, locale, email_consent, opted_out
  prior_touches_this_case, prior_touches_30d
  merchant_name
```
Never in the packet: email, full name, raw PayPal payload, any PayPal id, any URL. A test asserts the packet model has exactly these fields.

### 6.3 `schemas.py` — model output, strictly validated
```python
class Diagnosis(BaseModel):
    category: Literal["soft","hard","pending","unknown"]
    cause: str = Field(max_length=240)          # plain English, one or two sentences
    customer_context: str = Field(max_length=200)
    confidence: Literal["low","medium","high"]

class Proposal(BaseModel):
    action: Literal["SEND_INVOICE","WAIT","ESCALATE","NONE"]
    rationale: str = Field(max_length=240)
    message_template: str | None = Field(default=None, max_length=400)
    language: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
```
`extra="forbid"` on both. Note there is no numeric type anywhere. `confidence` is categorical on purpose.

### 6.4 `diagnose.py` (call 1) and `propose.py` (call 2)
- Each stage: build prompt from the packet → call provider with `response_format` JSON where supported → `model_validate_json`. On validation failure, retry once with the validation error appended. On second failure → `escalated` with event text "The model's answer could not be validated twice."
- Prompts live in `prompts/diagnose.md` and `prompts/propose.md`. Customer-provided strings (first name, description) are wrapped in a `<data>` block and the system prompt states they are data, not instructions (`04_SECURITY.md` §4).
- `propose.md` lists the four actions, the placeholder set, and the message rules verbatim from PRD §9 rule 8, and instructs the model to write in `locale`'s language.

### 6.5 `rules.py` — the engine
```python
class Verdict(BaseModel):
    rule_id: str; name: str
    verdict: Literal["allow","defer","approve","refuse"]
    reason: str                      # one sentence, shown in UI
    scheduled_for: datetime | None = None

def evaluate(case, customer, proposal, now) -> list[Verdict], Final
```
- All eight rules run and return a verdict, even after a refusal, so the UI shows the complete picture.
- `Final.outcome` precedence: any `refuse` → `refuse`; else any `approve` → `approve`; else any `defer` → `defer` (earliest `scheduled_for` wins); else `allow`.
- Rules only apply their restrictions to `SEND_INVOICE`. `WAIT`, `ESCALATE`, `NONE` always receive `allow` from rules 1–7 (rule 8 is skipped for them).
- Safe defaults when refused: hint `pending` → stage `waiting`; otherwise stage `held`. Event text explains which rule refused.

| id | name | logic |
|---|---|---|
| R1 | Hard failures are not chased | `hint == hard` → refuse |
| R2 | Pending payments only wait | `hint == pending` → refuse |
| R3 | Consent required | `not email_consent or opted_out` → refuse |
| R4 | Contact window | customer local time outside 09:00–20:00 → defer to next 09:00 local |
| R5 | Frequency cap | touches this case ≥ 2 or touches 30d ≥ 3 → refuse |
| R6 | Freeze | case frozen (dispute) or `paid_elsewhere` / `refunded` → refuse and close |
| R7 | Approval threshold | `amount >= APPROVAL_THRESHOLD` → approve |
| R8 | Message safety | template fails `messaging.validate()` → use fallback template; verdict `allow` with reason "Model message replaced by the standard template" |

### 6.6 `messaging.py`
- Placeholders: `{first_name} {merchant} {description} {amount} {due_date}`. The invoice itself carries the pay button; no link placeholder is needed in the note.
- `validate(template, locale)`: only allowed placeholders; no digit characters; none of `BANNED_PHRASES` (case-insensitive, per language list); ≤ 400 chars; detected language matches `locale` language (use `langdetect`; on detection error treat as mismatch).
- `render(template, case, customer)`: formats amount with currency per locale (`babel`), due date per locale. The rendered note is what goes into the invoice `note`.
- `fallback(locale)`: templates for `en`, `es`, `hi`; English for anything else. Fallbacks pass `validate` by construction (test).

### 6.7 Flow per case
```
create_case → diagnose (call 1) → propose (call 2) → evaluate rules
  → outcome allow   : send now (create_invoice, send_invoice, touch) → stage sent
  → outcome defer   : stage scheduled, message.scheduled_for set
  → outcome approve : stage awaiting_approval
  → outcome refuse  : stage held or waiting (safe default)
```
Approval → re-run rules R4–R6 at approval time (window may have changed) → send or schedule.

### 6.8 `scheduler.py`
One asyncio task, every 15 s:
- Send any `scheduled` case whose `scheduled_for <= now` and whose kill switch is off (re-run R4–R6 first).
- Close any non-terminal case older than `CASE_TTL_HOURS` (72) with reason `expired`.
- Phase 2: detect abandoned orders from the demo store (created > 15 min ago, never approved) and create `checkout_abandoned` cases.
- Each tick is wrapped in try/except with structured logging; one bad case never stops the loop.

## 7. Demo mode (`DEMO_MODE=true`)

- Enables `POST /api/demo/fail` and the Fail-a-payment button. Rate limit: 6 per minute per IP, 60 per hour globally.
- Demo customers: a fixed rotation of six (names, countries, timezones, locales — include at least one where it is currently outside the contact window so a defer is likely visible, and one with `opted_out=true`). Every demo customer's email is `SANDBOX_BUYER_EMAIL` so the judge can pay the invoice.
- `kind: "subscription"` → `POST /v1/notifications/simulate-event` with `webhook_id = PAYPAL_WEBHOOK_ID` and `event_type = BILLING.SUBSCRIPTION.PAYMENT.FAILED`. PayPal delivers a sample event to the listener. The listener verifies it like any other event. Because the sample resource may not carry a usable payer, the handler attaches the next demo customer in rotation and a fixed demo plan amount (`DEMO_SUBSCRIPTION_AMOUNT`, default 29.00 USD).
- `kind: "capture_denied"` → same, with `PAYMENT.CAPTURE.DENIED`.
- **Decision point on first deploy:** if simulated events fail signature verification in sandbox, set `DEMO_FAIL_STRATEGY=internal`. Then `/api/demo/fail` creates the case directly with `source=seeded` and the UI labels it "Seeded for demo". The forced-decline path on the Store remains fully live either way, so the video always has a real failure. Record the outcome in `docs/CHANGES.md`.
- The Store (`/demo/store`) is a one-product page using the PayPal JS SDK with `createOrder` → `POST /api/demo/store/orders` and `onApprove` → capture with the page's "Make this payment fail" toggle passed as `force_decline`.

## 8. Configuration (`.env.example`)

```
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=
PAYPAL_ENV=sandbox                  # the only accepted value; see 04_SECURITY.md §2
SANDBOX_BUYER_EMAIL=                # demo customers' email
MERCHANT_NAME=Recoup Demo Store
MERCHANT_TIMEZONE=Asia/Kolkata
APPROVAL_THRESHOLD=500.00
CASE_TTL_HOURS=72
CONTACT_WINDOW_START=09:00
CONTACT_WINDOW_END=20:00
KILL_SWITCH=false
DEMO_MODE=true
DEMO_FAIL_STRATEGY=simulate_event   # or internal
DEMO_SUBSCRIPTION_AMOUNT=29.00
LLM_PROVIDER=groq                   # groq | anthropic | fixture
LLM_MODEL=
LLM_API_KEY=
DASHBOARD_TOKEN=
DATABASE_URL=sqlite:///./recoup.db
PUBLIC_API_URL=                     # used by register_webhook.py
LOG_LEVEL=info
```

Web: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_PAYPAL_CLIENT_ID`, `DASHBOARD_TOKEN` (server-side only; the Next.js route handlers proxy API calls so the token never reaches the browser).

## 9. Deployment

- `render.yaml` defines `recoup-api` (Python, `uvicorn recoup.main:app`) with a Postgres instance, and `recoup-web` (Node). Health check `/api/health`.
- First deploy order: api → set `PUBLIC_API_URL` → run `scripts/register_webhook.py` → set `PAYPAL_WEBHOOK_ID` → redeploy → web.
- `scripts/seed_demo.py` creates the six demo customers and two closed example cases so the Floor is never empty.
- `scripts/e2e_sandbox.py` runs the full loop against sandbox (forced decline → case → invoice sent) and exits non-zero if any step fails. Requires credentials; refuses to run without them.

## 10. Tests (`api/tests/`)

Run with `LLM_PROVIDER=fixture uv run pytest -q`. No network. Target under 10 s.

- `test_rules.py` — every rule, both verdicts, precedence, defer scheduling across timezones, approval re-evaluation.
- `test_schemas.py` — model output validation; rejects extra fields, numbers in disallowed places, bad language codes.
- `test_messaging.py` — placeholder whitelist, digit ban, banned phrases per language, language mismatch, fallbacks pass by construction.
- `test_taxonomy.py` — hints; a hallucinated `soft` on a hard code never unlocks outreach.
- `test_webhooks.py` — dedupe, verification failure → 400, dispatch table, close-on-paid-elsewhere. Verification call is mocked at the HTTP layer with recorded fixtures.
- `test_invoicing_contract.py` — request body shape built from a case; amount equals `case.amount`; no function in the pipeline accepts an amount.
- `test_invariants.py` — static checks: no live base URL string in `api/`; no UPDATE/DELETE against `case_events`; evidence packet field set is exact; toolkit allowlist contains no write tool names.
- `test_pipeline.py` — fixture provider returns canned diagnoses/proposals; full flow to each terminal stage.

Keep the count modest and the names legible. Nobody is impressed by a number; they are impressed by `test_hallucinated_soft_cannot_unlock_hard_failure`.

## 11. Observability

- Structured JSON logs (`structlog`): `case_id`, `stage`, `rule_id`, `event_id`, `latency_ms`. Never log email, full name, raw PayPal payloads, or model prompts at `info`. Prompts and raw payloads only at `debug`, redacted.
- `/api/health` is enough monitoring for the hackathon.

## 12. Local development

```
cd api && uv sync && cp .env.example .env
uv run alembic upgrade head
uv run python -m scripts.seed_demo
uv run uvicorn recoup.main:app --reload       # :8000
cd ../web && npm install && npm run dev        # :3000
```
For webhooks locally, expose `:8000` with a tunnel and register a second sandbox webhook pointing at it.

## 13. Decisions log (so Claude Code does not relitigate them)

1. Invoicing is the only channel. No email provider, no SMS. PayPal sends the email.
2. No retries against stored instruments. Ever, in this codebase.
3. Rules read the code-computed hint, not the model's category.
4. The model output schemas contain no numeric fields.
5. Verdicts for all eight rules are always computed and stored, even after a refusal.
6. Polling, not websockets. Three-second SWR refresh is enough and simpler.
7. One asyncio tick replaces any job queue.
8. Sandbox is hard-coded. There is no live mode to toggle.
