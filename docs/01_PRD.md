# Recoup — Product Requirements

**Status:** v1, frozen for the hackathon build. Changes go in `docs/CHANGES.md`, not here.
**Audience:** Claude Code. Read this file first, then `02_TECHNICAL_ARCHITECTURE.md`, `03_FRONTEND_SPEC.md`, `04_SECURITY.md`.

---

## 1. One sentence

When a PayPal payment fails, Recoup brings the customer back to pay — and it is never allowed to touch their money.

## 2. The problem

A payment that fails is usually a customer who wanted to pay. Cards get declined for soft reasons, 3DS gets abandoned, subscription renewals bounce on an expired card. Most merchants never see that customer again, because nobody follows up, or the follow-up is a blunt reminder sent at a bad hour to someone whose payment was never going to work.

Stripe merchants have had this solved for years: Smart Retries plus a whole category of dunning tools. PayPal merchants have almost nothing. Recoup is the dunning layer PayPal merchants never had.

## 3. Why fintech teams don't let AI near this, and how Recoup answers it

Language models hallucinate. A hallucinated retry breaks card-network rules. A hallucinated message promises a discount nobody authorised. A message at 2am breaks contact rules.

Recoup's answer is one rule, enforced in code: **the model proposes, deterministic code disposes.**

- The model is called exactly twice per case: once to diagnose, once to propose. Then it is out of the loop.
- The model can only choose from four fixed actions. None of them carries an amount.
- The model writes messages into slots. Every number, name, and link is inserted by code from the database.
- Recoup never charges anyone. Its only outbound money action is sending a PayPal invoice the customer may choose to pay.
- Eight rules in pure code check every action before it happens. Above a threshold, a human approves.

## 4. Users

**Primary:** a small or mid-size merchant on PayPal (one-time checkout and/or subscriptions) who loses revenue to failed payments and has no time to chase them. They open Recoup once a day, glance at two numbers, and occasionally approve a case.

**Secondary (hackathon):** a judge who opens the hosted demo, presses one button to make a payment fail, and watches the loop run end to end in under a minute.

## 5. Goals and non-goals

**Goals**
1. Recover failed PayPal payments by inviting the customer to pay again, safely.
2. Make every decision legible: a merchant can see why a message was sent, held, or refused.
3. Be impossible to misuse: no path from model output to a charge, an amount, or an unapproved send.
4. Be understood by a judge in one sentence and demonstrated in under a minute.

**Non-goals (v1)**
- No automatic retries against stored payment instruments.
- No SMS, WhatsApp, or custom email delivery. The PayPal invoice email is the only customer-facing channel.
- No discounts, coupons, or negotiation of any kind.
- No analytics, charts, cohorts, or revenue forecasting.
- No multi-merchant tenancy. One merchant per deployment.
- No live-environment support. Sandbox only (see `04_SECURITY.md` §2).

## 6. The loop

Every case moves through five stages, always visible in the UI:

```
Failed → Diagnosed → Proposed → Checked → Recovered
                                    ↘ Held / Escalated / Closed (terminal)
```

| Stage | Who does it | What happens |
|---|---|---|
| Failed | PayPal + code | A failure arrives (webhook or capture error). A case is created. |
| Diagnosed | Model (call 1) | Category (soft / hard / pending / unknown), likely cause, customer context, in plain English. |
| Proposed | Model (call 2) | One of four actions plus a slot-based message template in the customer's language. |
| Checked | Code | Eight rules run. Outcome: allow, defer, require approval, or refuse. |
| Recovered | PayPal + code | The customer pays the invoice. PayPal's webhook closes the case. |

Terminal branches: **Held** (a rule refused the action; the safe default was applied), **Escalated** (model asked for a human or validation failed twice), **Closed** (72-hour TTL expired, or the order was paid or refunded another way).

## 7. Inputs (how a case begins)

| Source | Trigger | v1 |
|---|---|---|
| `checkout_decline` | Capture on an approved order fails with a recoverable error (e.g. `INSTRUMENT_DECLINED`, `PAYER_ACTION_REQUIRED`). Forced in sandbox with PayPal's negative-testing header. | Yes |
| `capture_denied` | `PAYMENT.CAPTURE.DENIED` webhook. | Yes |
| `subscription_failed` | `BILLING.SUBSCRIPTION.PAYMENT.FAILED` webhook. | Yes |
| `capture_pending` | `PAYMENT.CAPTURE.PENDING` webhook (e.g. eCheck). Creates a case that can only wait. | Yes |
| `checkout_abandoned` | Order created, not approved within 15 minutes. | Phase 2 |

## 8. Actions (the only things the model may choose)

| Action | Meaning | Money? |
|---|---|---|
| `SEND_INVOICE` | Create and send a PayPal invoice for the failed amount, with a short note in the customer's language. | Customer decides. Recoup never charges. |
| `WAIT` | Do nothing yet; the payment may still clear (pending). Re-check on webhook or TTL. | No |
| `ESCALATE` | Hand the case to a human with the diagnosis attached. | No |
| `NONE` | Close the case. Hard failures land here. | No |

The amount on an invoice always comes from the case record, which came from PayPal. The model's output schema has no numeric field.

## 9. The eight rules (plain English)

Evaluated in order on every proposed action. All eight verdicts are shown in the UI.

1. **Hard failures are not chased.** If the failure is in the hard list (e.g. transaction refused, payer cannot pay, capture denied), outreach is refused and the case closes with a note to the merchant.
2. **Pending payments only wait.** If PayPal says the capture is pending, no invoice may be sent. The case waits.
3. **Consent is required.** No email to a customer who has not consented or has opted out.
4. **Contact window.** Messages go out between 09:00 and 20:00 in the *customer's* local time. Outside the window, the send is queued for 09:00, not cancelled. (Stricter than TCPA's 8am–9pm.)
5. **Frequency cap.** At most two touches per case and three per customer per rolling 30 days.
6. **Freeze.** If the order was paid another way, refunded, or has an open dispute, the case closes. Nothing is sent.
7. **Approval threshold.** Amounts at or above `APPROVAL_THRESHOLD` wait for a human.
8. **Message safety.** The template may contain only approved placeholders; no digits; no banned phrases (discount, refund, guarantee, urgent, final notice, and the like); length under 400 characters; language must match the customer's locale. If it fails, the deterministic fallback template is used instead.

Global, not a rule: a **kill switch** (`KILL_SWITCH=true`) stops all sends while the rest of the loop keeps running, and the UI shows a banner.

## 10. Screens

Three screens plus a demo store. No charts anywhere.

1. **Floor** — two numbers (Recovered today, Held back today) and a list of cases, each with the five-stage indicator.
2. **Case** — one case, top to bottom: summary, diagnosis, proposal, the eight checks, the message, timeline.
3. **Approvals** — cases waiting for a human; approve or decline.
4. **Rules** (read-only page) — the eight rules in plain English, so a judge can read them.

Demo-only: **Store** — a one-product checkout with PayPal buttons and a "Make this payment fail" toggle.

Full spec in `03_FRONTEND_SPEC.md`.

## 11. The judge's path (hosted demo)

1. Open the hosted URL. Land on the Floor.
2. Press **Fail a payment** in the header. Choose "Subscription renewal" or "Card capture denied".
3. Within seconds a new case appears at the top of the list and moves through Diagnosed → Proposed → Checked.
4. Open it. Read the diagnosis and the eight verdicts.
5. If allowed, the invoice has been sent. The case shows the payer link. Open it, pay with the sandbox buyer (credentials in the README). The case turns Recovered. The number on the Floor goes up.
6. Optionally open **Store**, toggle "Make this payment fail", check out with the sandbox buyer, and watch a real `INSTRUMENT_DECLINED` create a case.

The whole path must work with no local setup.

## 12. Success criteria for the hackathon

- A judge can trigger, follow, and recover a case in under 90 seconds without reading docs.
- Every PayPal interaction in the demo is a live sandbox call (orders, capture, invoicing, webhooks). No simulator, no mocks in the hosted build.
- The README opens with a GIF of the loop and a ten-line quickstart.
- The video is under three minutes and shows: a failure, the diagnosis, a rule refusing or deferring something, a recovery, the approvals screen.
- Zero paths from model output to an amount, a recipient, or a send. Tests enforce this (see `04_SECURITY.md` §6).

## 13. Submission checklist (maps to the hackathon requirements)

- [ ] Public GitHub repo, MIT license visible in the About section
- [ ] Hosted demo URL in the submission form
- [ ] README: description, features, tools used and how (PayPal Orders, Invoicing, Webhooks, Agent Toolkit; the LLM provider; Render; Postman collection)
- [ ] YouTube video, under 3 minutes, no third-party trademarks or music
- [ ] Sandbox buyer credentials for judges in the README (sandbox only, rotate after judging)

## 14. Scope by phase

**Phase 1 (must ship):** webhook listener, four sources (minus abandoned), two model calls, eight rules, invoicing, Floor + Case + Approvals + Rules, Fail-a-payment button, demo store with forced decline, Render deployment, tests for rules and safety invariants.

**Phase 2 (if time):** abandoned-checkout detection, Agent Toolkit read tools inside the propose call, multi-language fallback templates beyond English/Spanish/Hindi.

**Cut first if behind:** Approvals screen (fall back to auto-escalate above threshold), subscription path, multi-language.

**Never cut:** the live loop, the eight rules, the Held-back counter, the Fail-a-payment button.

## 15. Risks

| Risk | Mitigation |
|---|---|
| Simulated webhook events don't carry verifiable signatures | Verify every event via PayPal's verification API. If simulated events fail verification in sandbox, the demo button falls back to an internal seeding endpoint and the case is labelled "seeded". Decision recorded in `02_TECHNICAL_ARCHITECTURE.md` §7. |
| Judge can't pay the invoice | Invoice recipient for demo customers is always the configured sandbox buyer email. Payer link is shown on the case screen. |
| Model returns invalid JSON | Schema validation with one retry per stage; second failure escalates. |
| "The AI barely matters" | The diagnosis and the message are visibly the model's work; show the message in the customer's language on screen. |
| Looks like a Razorpay port | PayPal failure taxonomy, PayPal Invoicing as the only channel, Agent Toolkit in the loop, the Stripe-gap framing in the README's first paragraph. |

## 16. Vocabulary (use these words everywhere: code, UI, docs)

Case · Failed · Diagnosed · Proposed · Checked · Recovered · Held · Escalated · Closed · Rule · Verdict (allow / defer / approve / refuse) · Touch · Invoice · Kill switch.

Do not introduce synonyms (no "incident", "ticket", "attempt", "nudge").
