# Recoup — Frontend Spec

**Read `01_PRD.md` and `02_TECHNICAL_ARCHITECTURE.md` §3–4 first.** The frontend is a thin client over the API. It holds no secrets, makes no PayPal calls (except the JS SDK on the demo store), and contains no business logic beyond display.

The brief in one line: **three screens, two numbers, one list, no charts.** If a screen feels like it needs a graph, the answer is a sentence.

---

## 1. Design plan

### Subject
A back office for a merchant. The emotional register is a calm, well-kept ledger: things happened, here is what we did about them, here is what we chose not to do. Not a trading floor, not a security console.

### Tokens

**Color** (light only; respect `prefers-color-scheme: dark` with a single inverted palette, no second design)

| token | hex | use |
|---|---|---|
| `--paper` | `#F7F7F5` | page background |
| `--surface` | `#FFFFFF` | rows, panels |
| `--ink` | `#14181C` | primary text |
| `--ink-2` | `#5C6670` | secondary text, labels |
| `--line` | `#DADFE3` | 1px borders, dividers |
| `--recovered` | `#1D7A55` | recovered state, the only celebratory color |
| `--deferred` | `#A86A00` | queued / waiting |
| `--refused` | `#B3261E` | held / refused / escalated |
| `--action` | `#0B5FFF` | buttons, links — used sparingly |

No gradients. No shadows. No tinted near-black. Status colors appear only on the stage indicator, the verdict marks, and status text; never as fills behind whole rows or cards.

**Type**
One family: **IBM Plex Sans** (Google Fonts), fallback `system-ui, sans-serif`. Weights 400, 500, 600. Enable tabular figures on every number: `font-variant-numeric: tabular-nums`.

| role | size / line | weight |
|---|---|---|
| Big number (Floor) | 40 / 44 | 600 |
| Page title | 22 / 28 | 600 |
| Section title | 16 / 24 | 600 |
| Body | 15 / 24 | 400 |
| Secondary | 13 / 20 | 400, `--ink-2` |

Sentence case everywhere. No all-caps labels. No tiny uppercase eyebrows. No monospace.

**Layout**
Max content width 880px, left-aligned, 24px page gutters (16px on mobile). Vertical rhythm on an 8px grid. Rows are separated by 1px `--line`, not by boxes. Panels (on the Case screen) are plain `--surface` with a 1px border and 8px radius; no shadow.

**Principles**
1. Every screen answers one question. Floor: "how are we doing today?" Case: "what happened to this one?" Approvals: "what needs me?"
2. Words over widgets. A verdict is a sentence, not a badge.
3. The one memorable element is the five-dot stage indicator. Everything else stays quiet.
4. Motion only when something changes: a dot fills, a row settles. Nothing animates on page load.

### Review against the generic default
A generic version of this brief would be a dark dashboard with KPI cards, a line chart of recoveries, badge chips in six colors, and a data table with sort arrows. We are not building that. The Floor has no cards and no chart; the list has no sort controls; status is a dot and a sentence. The dark mode is an inversion of the same palette, not a design.

## 2. Navigation

A single top bar on every screen (except the demo store):

```
┌──────────────────────────────────────────────────────────────────────┐
│ Recoup        Floor   Approvals (2)   Rules            [Fail a payment] │
└──────────────────────────────────────────────────────────────────────┘
```

- Wordmark left, three text links, the demo button right. The Approvals link shows a count only when > 0.
- `Fail a payment` renders only when `/api/health` reports `demo_mode: true`.
- When `kill_switch` is true, a full-width band appears under the bar: **"Sending is paused. Cases keep moving through diagnosis and checks, but no invoices go out."** Background `--paper`, 1px `--line` top and bottom, text `--ink`. No red.

Routes (Next.js App Router):

| route | screen |
|---|---|
| `/` | Floor |
| `/cases/[id]` | Case |
| `/approvals` | Approvals |
| `/rules` | Rules |
| `/demo/store` | Store (own minimal layout, no top bar) |

## 3. Floor (`/`)

```
┌──────────────────────────────────────────────────────────────┐
│  Recovered today                 Held back today             │
│  $1,248.00                       7                           │
│  from 9 payments                 messages not sent, 3 queued │
│                                                              │
│  Cases                                                       │
│  ──────────────────────────────────────────────────────────  │
│  ●●●●○  Marta · Madrid        $89.00   Queued for 09:00 local│
│         Card declined · 2 min ago                            │
│  ──────────────────────────────────────────────────────────  │
│  ●●●●●  Rohan · Bengaluru    $29.00   Recovered             │
│         Subscription renewal failed · 14 min ago             │
│  ──────────────────────────────────────────────────────────  │
│  ●●●●◌  Chen · Singapore      $640.00  Waiting for approval  │
│         Card declined · 31 min ago                           │
│  ──────────────────────────────────────────────────────────  │
│  ●●●●×  Alex · Austin         $19.00   Held                 │
│         Capture denied · 1 h ago · Hard failures aren't chased│
└──────────────────────────────────────────────────────────────┘
```

**Two numbers** sit side by side at the top (stack on mobile). Under each, one line of secondary text. No icons, no sparkline, no delta arrow.

- Recovered today: `recovered_total` formatted in `currency`; sub-line "from {recovered_count} payments".
- Held back today: `held_back_count`; sub-line "messages not sent, {queued_count} queued" where queued is the number of cases currently `scheduled`.

**Case list**: newest first, 50 per page, "Show more" at the bottom. Each row is one tap target to `/cases/[id]`:

- Left: the stage indicator (§7).
- Line 1: `{first_name} · {city or country}`, amount right-aligned, then the status label.
- Line 2 (secondary): `{source in words} · {relative time}` and, for held or escalated cases, the refusing rule's name after another middle separator.

Source in words: Card declined · Capture denied · Subscription renewal failed · Payment pending · Checkout abandoned · Seeded for demo.

**Live updates**: SWR polls `/api/cases` and `/api/metrics/today` every 3 s. A row whose stage changed since the last poll fills its next dot with a 240 ms ease and the row background flashes `--paper` → `--surface` once over 600 ms. A new case enters at the top with a 240 ms height expansion. That is all the motion on this screen.

**Empty state**: "No cases yet. Press Fail a payment to watch one move through." (demo mode) or "No failed payments yet. Recoup is listening." (otherwise).

## 4. Case (`/cases/[id]`)

A single column of plain panels, in this exact order. Nothing collapses; a judge should scroll once and understand everything.

```
← Floor

Marta · Madrid                                             $89.00
Card declined · 2 minutes ago                     ●●●●○ Queued for 09:00 local

┌ What happened ───────────────────────────────────────────────┐
│ Her card was declined when we tried to collect $89.00 for the │
│ Linen Throw. PayPal reported INSTRUMENT_DECLINED, which is    │
│ usually a temporary issue with the card rather than a refusal.│
│                                                               │
│ Marta is in Madrid, where it is 02:14. She has not been      │
│ contacted about this before.                                  │
│ Confidence: high                                              │
└───────────────────────────────────────────────────────────────┘

┌ What Recoup proposed ────────────────────────────────────────┐
│ Send an invoice                                               │
│ A soft decline with a willing customer; one invitation to pay │
│ again, in Spanish, is the right move.                         │
│ Checked order details with PayPal                              │
└───────────────────────────────────────────────────────────────┘

┌ Checks ──────────────────────────────────────────────────────┐
│ ✓ Hard failures are not chased     This was a soft decline.   │
│ ✓ Pending payments only wait       Not pending.               │
│ ✓ Consent required                 Marta has agreed to email. │
│ ◔ Contact window                   It is 02:14 in Madrid. Queued for 09:00. │
│ ✓ Frequency cap                    First message for this case.│
│ ✓ Freeze                           No dispute or refund.      │
│ ✓ Approval threshold               Below $500.00.             │
│ ✓ Message safety                   Passed.                    │
└───────────────────────────────────────────────────────────────┘

┌ Message ─────────────────────────────────────────────────────┐
│ Spanish · goes out with the PayPal invoice at 09:00 local     │
│                                                               │
│ Hola Marta, no pudimos completar el pago de 89,00 US$ por     │
│ Linen Throw. Si aún lo quieres, puedes pagar con este enlace  │
│ hasta el 12 de octubre. Gracias — Recoup Demo Store           │
│                                                               │
│ Numbers and names were inserted by Recoup, not written by the │
│ model.                                                        │
└───────────────────────────────────────────────────────────────┘

┌ Timeline ────────────────────────────────────────────────────┐
│ 02:12  Payment failed: INSTRUMENT_DECLINED on order 7WH…      │
│ 02:12  Diagnosed as a soft decline                            │
│ 02:12  Proposed: send an invoice                              │
│ 02:12  Checked order details with PayPal                      │
│ 02:12  Checked: queued for 09:00 Madrid time by Contact window│
└───────────────────────────────────────────────────────────────┘
```

Panel rules:
- **What happened** = `diagnosis.cause` + `diagnosis.customer_context` + "Confidence: {level}". Plain paragraphs.
- **What Recoup proposed** = action in words (Send an invoice / Wait / Hand to a human / Do nothing) + `proposal.rationale` + one line per `toolkit_call` event ("Checked order details with PayPal").
- **Checks** = eight rows, one per rule, in rule order. Mark: `✓` allow (`--ink-2`), `◔` defer (`--deferred`), `○` approve/waiting (`--deferred`), `×` refuse (`--refused`). Then the rule name, then the reason sentence. Marks are text glyphs, not icons.
- **Message** = header line "{Language} · {status}", the rendered note as it will appear on the invoice, then the fixed footnote sentence. When `fallback_used`, the header adds "· standard template used". When the case is `sent`, `recovered` or has a payer link, add a plain link "Open the PayPal invoice" (`--action`). Hidden entirely for WAIT / NONE / held cases with no message.
- **Timeline** = `case_events` oldest first, `HH:MM` in the merchant's timezone, then `text`. No icons.
- **Approval**: if `awaiting_approval`, a panel appears between Checks and Message:

```
┌ Needs your approval ─────────────────────────────────────────┐
│ $640.00 is at or above your $500.00 threshold.                │
│ [Approve and send]   [Don't send]                             │
└───────────────────────────────────────────────────────────────┘
```
Both buttons confirm inline (the button text changes to "Approved — sending…" / "Held"), then the panel is replaced by the updated Checks and Timeline on the next poll. No modal.

- Terminal cases show a one-line note under the header: "Held: hard failures are not chased." / "Escalated: the model's answer could not be validated twice." / "Closed: paid another way." in `--ink-2`.

## 5. Approvals (`/approvals`)

Same list component as the Floor, filtered to `awaiting_approval`, with the two buttons inline at the right of each row. Header: "Waiting for you". Empty state: "Nothing needs approval."

Rule of thumb for this screen: a merchant should be able to clear it from a phone in ten seconds.

## 6. Rules (`/rules`)

A plain page. Title "The eight rules". Then, for each rule: its name as a section title and its plain-English description from `/api/rules` as one paragraph. Above the list, two sentences: "Recoup's model proposes; this code decides. Every rule below runs before anything is sent, and you can see each verdict on every case."

Under the eight: "Also: a kill switch pauses all sending without stopping diagnosis. Threshold today: $500.00. Contact window: 09:00–20:00 in the customer's local time." pulled from `/api/settings`.

## 7. The stage indicator (component `StageDots`)

Five 8px circles connected by a 1px `--line`, 6px apart. Fill rules from the stage mapping in `02_TECHNICAL_ARCHITECTURE.md` §3:

- Filled dots use `--ink` for stages 1–4 and `--recovered` for dot 5 when recovered.
- Dot 4 in a waiting/queued/approval sub-state renders as a half-filled circle in `--deferred`.
- Terminal non-recovered (held, escalated, closed) renders dot 4 as `×` in `--refused` (closed uses `--ink-2`) and dot 5 empty.
- `aria-label` reads the status in words: "Checked, queued for 09:00 local".

It appears at 16px tall in list rows and 20px tall in the Case header. Nowhere else.

## 8. Store (`/demo/store`)

A deliberately plain one-product page, so the failure is the only thing happening:

```
Recoup Demo Store

Linen Throw                                  $89.00
Hand-woven, 130 × 170 cm.

[ ] Make this payment fail   (sandbox negative test: INSTRUMENT_DECLINED)

[ PayPal buttons ]

Pay with the sandbox buyer from the README.
```

- Buttons from the PayPal JS SDK with `client-id = NEXT_PUBLIC_PAYPAL_CLIENT_ID`, `currency = USD`, `intent = capture`.
- `createOrder` → `POST /api/demo/store/orders` (proxied). `onApprove` → `POST /api/demo/store/orders/{id}/capture?force_decline={toggle}`.
- On `status: "failed"`: show "The payment could not be completed. Recoup opened a case." with a link "Watch it on the Floor →" to `/cases/{case_id}`. On success: "Paid. Thank you." No confetti.
- The toggle is checked by default in demo mode so a judge who clicks straight through sees the failure.

## 9. Data layer

- All API calls go through Next.js route handlers under `/app/api/proxy/[...path]/route.ts`, which forward to `NEXT_PUBLIC_API_URL` and add `X-Dashboard-Token` from the server-side env. The browser never sees the token.
- `lib/api.ts` exposes typed fetchers; `lib/types.ts` mirrors the API JSON exactly, including the stage enum and the stage→dots mapping (`stageToDots(stage, subState)`), kept in one function so it cannot drift between screens.
- SWR with `refreshInterval: 3000` on Floor and Approvals; `2000` on an open Case that is not terminal; off on terminal cases and the Rules page.
- Relative times via `Intl.RelativeTimeFormat`; currency via `Intl.NumberFormat` with the case currency.

## 10. Copy

Exact strings, so they stay consistent across screens:

| key | text |
|---|---|
| metric.recovered | Recovered today |
| metric.recovered.sub | from {n} payments |
| metric.held | Held back today |
| metric.held.sub | messages not sent, {n} queued |
| action.send | Send an invoice |
| action.wait | Wait |
| action.escalate | Hand to a human |
| action.none | Do nothing |
| status.queued | Queued for 09:00 local |
| status.sent | Invoice sent |
| status.waiting | Waiting for payment to clear |
| status.approval | Waiting for approval |
| status.recovered | Recovered |
| status.held | Held |
| status.escalated | Escalated |
| status.closed | Closed |
| approve.title | Needs your approval |
| approve.body | {amount} is at or above your {threshold} threshold. |
| approve.yes | Approve and send |
| approve.no | Don't send |
| message.footnote | Numbers and names were inserted by Recoup, not written by the model. |
| banner.kill | Sending is paused. Cases keep moving through diagnosis and checks, but no invoices go out. |
| demo.button | Fail a payment |
| demo.choice.sub | Subscription renewal |
| demo.choice.cap | Card capture denied |
| empty.floor.demo | No cases yet. Press Fail a payment to watch one move through. |
| empty.floor | No failed payments yet. Recoup is listening. |
| empty.approvals | Nothing needs approval. |
| error.generic | Recoup couldn't reach the server. It will keep trying. |

Voice: active, specific, sentence case, no exclamation marks, no apologies.

## 11. The Fail-a-payment control

Clicking the button opens a small popover anchored to it (not a modal) with two choices: **Subscription renewal** and **Card capture denied**. Choosing one calls `POST /api/demo/fail`, closes the popover, and the button reads "Failing…" for 1.5 s. The new case arrives via the next poll. If the API returns 429, the button shows "Try again in a minute" for 5 s. No toast system anywhere in the app.

## 12. Quality floor

- Keyboard: every row and button focusable, visible focus ring (2px `--action`, 2px offset).
- `prefers-reduced-motion`: disable the dot fill and row flash transitions; content still updates.
- Contrast: all text ≥ 4.5:1 on its background. Status colors above are chosen to pass on `--surface`.
- Responsive: at < 640px the two numbers stack, list rows wrap amount under the name, Case panels go full width. Nothing is hidden on mobile.
- No client-side storage. No analytics scripts. No external requests except the API proxy, Google Fonts, and the PayPal JS SDK on the Store.

## 13. Component inventory

`TopBar` · `KillSwitchBand` · `Metric` · `CaseRow` · `CaseList` · `StageDots` · `Panel` · `ChecksTable` · `MessagePanel` · `ApprovalPanel` · `Timeline` · `FailPaymentButton` · `StoreCheckout`. Thirteen components. If a fourteenth seems necessary, check whether it is a sentence.

## 14. What not to build

Charts, sparklines, KPI cards with deltas, filters and sort controls, a settings page, dark-mode toggle UI, toasts, modals, onboarding tours, tooltips on everything, icons for status, skeleton loaders beyond a single quiet "Loading…" line.
