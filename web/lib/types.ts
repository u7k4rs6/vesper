// Mirrors the API JSON exactly (docs/02_TECHNICAL_ARCHITECTURE.md §3–4).

export type Stage =
  | "failed" | "diagnosed" | "proposed" | "checked" | "awaiting_approval" | "scheduled"
  | "sent" | "waiting" | "recovered" | "held" | "escalated" | "closed";

export type Source =
  | "checkout_decline" | "capture_denied" | "subscription_failed" | "capture_pending" | "checkout_abandoned" | "seeded";

export type VerdictKind = "allow" | "defer" | "approve" | "refuse";
export type Action = "SEND_INVOICE" | "WAIT" | "ESCALATE" | "NONE";

export interface CaseRow {
  id: string;
  stage: Stage;
  source: Source;
  first_name: string;
  place: string;
  amount: string;
  currency: string;
  created_at: string;
  reason_short: string | null;
  scheduled_for: string | null;
}

export interface Verdict {
  rule_id: string;
  name: string;
  verdict: VerdictKind;
  reason: string;
  scheduled_for: string | null;
}

export interface CaseDetail extends CaseRow {
  description: string;
  failure_code: string;
  failure_category_hint: "soft" | "hard" | "pending" | "unknown";
  closed_reason: string | null;
  recovered_at: string | null;
  customer: { first_name: string; place: string; country_code: string; timezone: string; locale: string };
  diagnosis: { category: string; cause: string; customer_context: string; confidence: "low" | "medium" | "high" } | null;
  proposal: { action: Action; rationale: string; message_template: string | null; language: string } | null;
  verdicts: Verdict[] | null;
  final: { outcome: VerdictKind; scheduled_for: string | null; refused_by: string | null; use_fallback: boolean } | null;
  message: {
    rendered: string;
    language: string;
    fallback_used: boolean;
    due_date: string;
    scheduled_for: string | null;
    sent_at: string | null;
    payer_link: string | null;
  } | null;
  events: { at: string; kind: string; text: string }[];
}

export interface Metrics {
  recovered_total: string;
  recovered_count: number;
  held_back_count: number;
  queued_count: number;
  currency: string;
}

export interface Health {
  ok: boolean;
  env: "sandbox";
  kill_switch: boolean;
  demo_mode: boolean;
}

export interface Settings {
  approval_threshold: string;
  currency: string;
  contact_window: { start: string; end: string };
  kill_switch: boolean;
  merchant_name: string;
  merchant_timezone: string;
  sandbox_buyer_email: string | null;
}

export interface Rule {
  id: string;
  name: string;
  description: string;
}

// The five-dot indicator. One function, so the Floor, Case and Approvals screens cannot drift apart.
export type Dot = "empty" | "filled" | "half" | "recovered" | "refused" | "closed";
export type Tone = "ink" | "deferred" | "recovered" | "refused" | "muted";

export interface StageView {
  dots: [Dot, Dot, Dot, Dot, Dot];
  label: string;
  tone: Tone;
  terminal: boolean;
}

const F: Dot = "filled";
const E: Dot = "empty";

export function stageToDots(stage: Stage): StageView {
  switch (stage) {
    case "failed":
      return { dots: [F, E, E, E, E], label: "Failed", tone: "ink", terminal: false };
    case "diagnosed":
      return { dots: [F, F, E, E, E], label: "Diagnosed", tone: "ink", terminal: false };
    case "proposed":
      return { dots: [F, F, F, E, E], label: "Proposed", tone: "ink", terminal: false };
    case "checked":
      return { dots: [F, F, F, F, E], label: "Checked", tone: "ink", terminal: false };
    case "sent":
      return { dots: [F, F, F, F, E], label: "Invoice sent", tone: "ink", terminal: false };
    case "awaiting_approval":
      return { dots: [F, F, F, "half", E], label: "Waiting for approval", tone: "deferred", terminal: false };
    case "scheduled":
      return { dots: [F, F, F, "half", E], label: "Queued for 09:00 local", tone: "deferred", terminal: false };
    case "waiting":
      return { dots: [F, F, F, "half", E], label: "Waiting for payment to clear", tone: "deferred", terminal: false };
    case "recovered":
      return { dots: [F, F, F, F, "recovered"], label: "Recovered", tone: "recovered", terminal: true };
    case "held":
      return { dots: [F, F, F, "refused", E], label: "Held", tone: "refused", terminal: true };
    case "escalated":
      return { dots: [F, F, F, "refused", E], label: "Escalated", tone: "refused", terminal: true };
    case "closed":
      return { dots: [F, F, F, "closed", E], label: "Closed", tone: "muted", terminal: true };
  }
}

export const SOURCE_WORDS: Record<Source, string> = {
  checkout_decline: "Card declined",
  capture_denied: "Capture denied",
  subscription_failed: "Subscription renewal failed",
  capture_pending: "Payment pending",
  checkout_abandoned: "Checkout abandoned",
  seeded: "Seeded for demo",
};

export const ACTION_WORDS: Record<Action, string> = {
  SEND_INVOICE: "Send an invoice",
  WAIT: "Wait",
  ESCALATE: "Hand to a human",
  NONE: "Do nothing",
};
