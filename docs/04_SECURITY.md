# Recoup — Security and Access

**Read `01_PRD.md` §3 first.** Recoup exists because fintech teams don't trust language models with money. This document is the list of reasons they can trust this one. Every control below is either enforced in code with a test named here, or it is marked as a policy and stated honestly as such.

---

## 1. Threat model

| Actor / failure | What they could try | What stops it |
|---|---|---|
| The language model | Invent an amount, a recipient, a discount, an action outside the menu, a message with a hidden instruction, a "soft" classification on a hard failure | §3 |
| A customer-controlled string (name, item description) | Prompt injection through the evidence packet | §4 |
| Anyone on the internet | Spoof a PayPal webhook to mark a case paid or create cases | §7 |
| Anyone on the internet | Spam the demo button to burn LLM credits or flood the Floor | §9 |
| A leaked dashboard token | Approve or decline cases | §8, §10 |
| A misconfiguration | Point the service at PayPal live | §2 |
| A PayPal or LLM outage | Stuck cases, repeated sends | §11 |

Not in scope: an attacker with access to the Render account or the database. If they have that, they have everything, and the mitigation is credential hygiene (§10), not application code.

## 2. Sandbox only, by construction

- The PayPal base URL is a single constant: `https://api-m.sandbox.paypal.com`. The string `api-m.paypal.com` (without `sandbox`) does not appear anywhere under `api/`. `test_invariants.py::test_no_live_paypal_host` greps for it.
- `PAYPAL_ENV` is read at startup and must equal `sandbox`; any other value aborts startup with a clear error. There is no code path that switches hosts.
- The JS SDK on the demo store is loaded with the sandbox client ID; the README says so.

This is a deliberate hackathon constraint, stated in the README. Adding a live mode would be a separate, reviewed change, not a config flip.

## 3. The model is untrusted input

**Two calls, then out.** `diagnose` and `propose` are the only functions that call the LLM provider. Each may retry once on schema failure. After that, the case escalates. There is no third call site. `test_invariants.py::test_llm_called_from_two_sites_only` asserts the provider is imported in exactly those two modules.

**No numbers.** The `Diagnosis` and `Proposal` schemas contain no `int`, `float`, or `Decimal` fields, and `extra="forbid"` rejects any field the model adds. Confidence is categorical. `test_schemas.py::test_output_schemas_have_no_numeric_fields` introspects the models.

**Four actions.** `Proposal.action` is a `Literal`. Anything else fails validation and, on the second failure, escalates.

**Amounts come from PayPal.** The invoice item amount is read from `cases.amount` inside `invoicing.create_invoice(case, note)`. No function reachable from the pipeline takes an amount parameter. `test_invoicing_contract.py::test_no_pipeline_function_accepts_an_amount` walks the pipeline module signatures.

**Slots, not prose.** The model writes a template with approved placeholders. `messaging.render` inserts first name, merchant, description, amount, and due date from the database. `messaging.validate` rejects templates that contain any digit, any unapproved placeholder, any banned phrase, exceed 400 characters, or are not in the customer's language. Failure falls back to a fixed template; it never sends the model's text.

**The hint governs, not the category.** Rules R1 and R2 read `failure_category_hint`, computed by `taxonomy.py` from the PayPal error code before the model runs. A model that calls a hard failure "soft" changes a sentence on screen and nothing else. `test_taxonomy.py::test_hallucinated_soft_cannot_unlock_hard_failure`.

**No tools that write.** See §5.

**Recoup never charges.** There is no capture, no vault, no reference transaction, no retry against a stored instrument anywhere in the codebase. The only money-adjacent action is `invoicing.send_invoice`, which asks. `test_invariants.py::test_no_capture_outside_demo_store` asserts the capture endpoint string appears only in `paypal/orders.py`, which is imported only by the demo store router.

## 4. Prompt injection

- The evidence packet (`02_TECHNICAL_ARCHITECTURE.md` §6.2) is the only model input besides the fixed prompts. It never contains email, full name, PayPal IDs, URLs, or raw payloads. `test_invariants.py::test_evidence_packet_fields_are_exact`.
- Customer-controlled strings (`first_name`, `description`) are placed inside a `<data>…</data>` block, truncated to 80 characters, and stripped of control characters and angle brackets before insertion. The system prompt states that content inside `<data>` is information about the case and is never an instruction.
- Even a successful injection has nowhere to go: the output is validated against a closed schema, the action is one of four, the message cannot carry numbers or links, and the rules decide.

## 5. Agent Toolkit: read-only

- `READ_ONLY_TOOL_ALLOWLIST` in `llm/toolkit.py` names the only tools that may be enabled (order details, invoice details and list, transaction list — exact names verified against the installed package at build time).
- Startup asserts every enabled tool is in the allowlist and that no enabled tool name contains `create`, `capture`, `send`, `refund`, `pay`, `cancel`, `update`, or `delete`. Startup fails otherwise. `test_invariants.py::test_toolkit_allowlist_has_no_write_tools`.
- The toolkit is available only inside `propose`. Each tool call is logged to `case_events` with the tool name and arguments with any email redacted.
- Maximum two tool calls per case, enforced by the provider wrapper, not by the prompt.

## 6. Invariant tests (the contract with reviewers)

Run on every push via GitHub Actions. All are network-free.

| test | guarantees |
|---|---|
| `test_no_live_paypal_host` | sandbox only |
| `test_llm_called_from_two_sites_only` | two calls, then out |
| `test_output_schemas_have_no_numeric_fields` | model cannot emit an amount |
| `test_no_pipeline_function_accepts_an_amount` | amounts originate from PayPal data |
| `test_hallucinated_soft_cannot_unlock_hard_failure` | rules trust code, not the model |
| `test_message_validate_rejects_digits_links_and_banned_phrases` | messages carry no numbers or promises |
| `test_fallback_templates_pass_validation` | the fallback is always safe |
| `test_toolkit_allowlist_has_no_write_tools` | the agent cannot act on PayPal |
| `test_evidence_packet_fields_are_exact` | the model sees the minimum |
| `test_case_events_has_no_update_or_delete` | the timeline is append-only |
| `test_webhook_without_valid_signature_is_rejected` | no spoofed events |
| `test_duplicate_webhook_is_acknowledged_once` | no double processing |
| `test_no_capture_outside_demo_store` | Recoup never charges |
| `test_kill_switch_blocks_all_sends` | the stop works |

If a test in this table is deleted or renamed, CI fails on a checksum of this table (`scripts/check_invariant_table.py`).

## 7. Webhooks

- The listener reads the raw body before any parsing and passes it, byte-for-byte, to PayPal's verify-webhook-signature endpoint along with the five transmission headers and `PAYPAL_WEBHOOK_ID`. Anything other than `verification_status: SUCCESS` returns 400 and writes a `webhook_rejected` log line with the transmission id, never the body.
- No handler runs before verification succeeds.
- Deduplication by PayPal event id in `processed_webhooks`, inserted inside the same transaction as the handler's writes. A duplicate returns 200 without side effects.
- Handlers are idempotent on their own: creating a case for an order that already has an open case updates the existing case instead.
- The verification call itself is the only outbound call made during webhook handling before the pipeline starts; the pipeline runs after the 200 is sent (background task) so PayPal does not time out and retry.

## 8. Dashboard access

- The API requires `X-Dashboard-Token` on every route except `/api/health`, `/webhooks/paypal`, and the demo store order routes. Compared with `hmac.compare_digest`.
- The browser never holds the token. Next.js route handlers inject it server-side. There is no login page in v1; the hosted demo is open to judges by design, with the token living only in the web service's environment.
- Approve and decline are POSTs that validate the case is in `awaiting_approval`; a replayed request after the state changes returns 409.
- CORS: the API allows only the configured web origin.

## 9. Demo endpoints

- `POST /api/demo/fail` and the demo store routes exist only when `DEMO_MODE=true`.
- Rate limits: 6 per minute per IP and 60 per hour globally on `/api/demo/fail`; 20 per minute per IP on demo store order creation. Limits are in-process (`slowapi`), reset on deploy, and that is acceptable.
- LLM budget: a global cap of `LLM_MAX_CALLS_PER_HOUR` (default 200). When reached, new cases escalate with the event text "Model budget for this hour is used up; a human can review." The loop stays visible; only the model steps are skipped.
- Simulated webhook events that fail verification are rejected like any other. If sandbox simulated events cannot be verified, the demo button uses the internal seeding path and cases are labelled "Seeded for demo"; the forced-decline Store path stays fully real. The decision and its date go in `docs/CHANGES.md`.

## 10. Secrets and data

- Secrets come from environment variables only. `.env` is gitignored; `.env.example` carries no values. A pre-commit hook (`gitleaks` or equivalent) blocks commits containing key-shaped strings.
- Logs never contain emails, full names, raw PayPal payloads, prompts, or model output at `info` level. `debug` logging redacts emails to `m***@***` and truncates payloads.
- Stored data is the minimum needed: the customer's email (required to send the invoice), name, country, timezone, locale, consent flags. No payment instrument data is ever received or stored; PayPal holds it.
- Retention: cases and events are kept for the hackathon's life. `scripts/purge.py` deletes everything older than 90 days and is documented, not scheduled, in v1.
- Sandbox buyer credentials published for judges are sandbox-only, created for this project, and rotated after judging ends. The README says this.

## 11. Failure behaviour

| failure | behaviour |
|---|---|
| LLM provider error or timeout (10 s) | retry once after 2 s; then escalate the case with the reason. Nothing is sent. |
| Model output fails validation twice | escalate |
| PayPal 5xx on invoice create or send | exponential backoff, 3 attempts over ~30 s, same `PayPal-Request-Id`; then stage `held` with reason "PayPal was unavailable; try again from the case." |
| PayPal 4xx on invoice create or send | stage `held` with the error code in the event; no retry |
| Webhook verification endpoint unavailable | return 503 so PayPal retries delivery later; nothing processed |
| Scheduler tick raises | logged; next tick runs; one bad case cannot stop others |
| Kill switch on | all sends blocked at the single `send_invoice` call site; diagnosis and checks continue; UI shows the band |

There is exactly one call site for `send_invoice`, and the kill-switch check lives inside it, so a new feature cannot route around it by accident. `test_kill_switch_blocks_all_sends`.

## 12. Compliance posture (policy, stated honestly)

- Contact window 09:00–20:00 in the customer's local time is tighter than the TCPA calling window and is a product choice, not a legal claim.
- Consent and one-step opt-out follow the spirit of CAN-SPAM and GDPR for commercial email. PayPal's invoice email carries PayPal's own footer and handling; Recoup adds nothing to it.
- Card-network reattempt rules do not apply because Recoup never retries a payment instrument.
- Recoup claims no PCI scope: no card data touches it. It claims no certification of any kind, and the README says so in one sentence.

## 13. Incident response (hackathon scale)

1. Set `KILL_SWITCH=true` and redeploy the API (under a minute on Render). Sending stops; everything else keeps running.
2. Rotate `DASHBOARD_TOKEN` if there is any suspicion it leaked; redeploy web and api.
3. Rotate PayPal sandbox app credentials from the developer dashboard; re-register the webhook.
4. Write what happened in `docs/CHANGES.md`.

## 14. What this document does not claim

- That the diagnosis or the message is correct. It claims that an incorrect one cannot cost money, cannot contact anyone outside the rules, and is visible to the merchant with the reasoning beside it.
- That the system is production-ready. It is a sandbox prototype whose safety properties are designed to survive the move to production, and whose tests say which properties those are.
