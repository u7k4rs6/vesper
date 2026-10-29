// One case, told as five steps. Pure functions only, so the demo page, the Case page and the
// stage strip can never disagree about where a case is.
import { languageName, money } from "@/lib/format";
import type { CaseDetail, Stage } from "@/lib/types";
import { ACTION_WORDS, SOURCE_WORDS } from "@/lib/types";

export type StepState = "todo" | "active" | "done" | "waiting" | "stopped" | "won";
export type Actor = "paypal" | "model" | "code" | "customer";

export const STEPS = [
  { key: "failed", n: "01", title: "Failed", short: "Fail", actor: "paypal" as Actor, caption: "PayPal reports a failed payment" },
  { key: "diagnosed", n: "02", title: "Diagnosed", short: "Diagnose", actor: "model" as Actor, caption: "Claude reads the evidence" },
  { key: "proposed", n: "03", title: "Proposed", short: "Propose", actor: "model" as Actor, caption: "Claude picks one of four actions" },
  { key: "checked", n: "04", title: "Checked", short: "Check", actor: "code" as Actor, caption: "Eight rules in code decide" },
  { key: "recovered", n: "05", title: "Recovered", short: "Recover", actor: "customer" as Actor, caption: "The customer pays a PayPal invoice" },
] as const;

export const ACTOR_LABEL: Record<Actor, string> = {
  paypal: "PayPal",
  model: "Claude",
  code: "Code",
  customer: "Customer",
};

const TERMINAL_STOP: Stage[] = ["held", "escalated", "closed"];

/** The state of each of the five steps for a case at a given stage. */
export function stepStates(c: Pick<CaseDetail, "stage" | "diagnosis" | "proposal" | "verdicts">): StepState[] {
  const stopped = TERMINAL_STOP.includes(c.stage);
  const diagnosed: StepState = c.diagnosis ? "done" : c.stage === "failed" ? "active" : stopped ? "stopped" : "todo";
  const proposed: StepState = c.proposal
    ? "done"
    : c.stage === "diagnosed"
      ? "active"
      : stopped && c.diagnosis
        ? "stopped"
        : "todo";
  let checked: StepState = "todo";
  if (c.verdicts) {
    if (["awaiting_approval", "scheduled", "waiting"].includes(c.stage)) checked = "waiting";
    else if (stopped) checked = "stopped";
    else checked = "done";
  } else if (c.stage === "proposed" || c.stage === "checked") {
    checked = "active";
  } else if (stopped && c.proposal) {
    checked = "stopped";
  }
  let recovered: StepState = "todo";
  if (c.stage === "recovered") recovered = "won";
  else if (c.stage === "sent") recovered = "waiting";
  return ["done", diagnosed, proposed, checked, recovered];
}

/** The step a case is currently on, for the strip's highlight. */
export function currentStep(states: StepState[]): number {
  const live = states.findIndex((s) => s === "active" || s === "waiting" || s === "stopped");
  if (live >= 0) return live;
  const won = states.indexOf("won");
  return won >= 0 ? won : states.lastIndexOf("done");
}

const CLOSED_WORDS: Record<string, string> = {
  paid_elsewhere: "the order was paid another way",
  refunded: "the order was refunded",
  frozen: "a dispute was opened",
  expired: "nobody paid within 72 hours",
  no_action: "Claude chose not to contact the customer",
  invoice_cancelled: "the invoice was cancelled",
};

export function failedLine(c: CaseDetail): string {
  const what = `${c.failure_code} on ${c.description} for ${money(c.amount, c.currency)}`;
  // Seeded cases come from the demo button, not from PayPal; say so rather than borrow PayPal's voice.
  return c.source === "seeded"
    ? `A demo failure, shaped exactly as PayPal reports one: ${what}.`
    : `${SOURCE_WORDS[c.source]}: PayPal reported ${what}.`;
}

/** Why step 05 never happened, naming who stopped it. */
export function notChasedLine(c: CaseDetail): string | null {
  switch (c.stage) {
    case "held":
      return "Not chased: the rules stopped it, so the customer never heard from Vesper.";
    case "escalated":
      return "Not chased: handed to a person instead.";
    case "closed":
      return c.closed_reason === "no_action"
        ? "Not chased: Claude chose not to contact the customer."
        : `Not chased: ${CLOSED_WORDS[c.closed_reason ?? ""] ?? "the case closed"}.`;
    default:
      return null;
  }
}

export function proposedHeadline(c: CaseDetail): string | null {
  if (!c.proposal) return null;
  const words = ACTION_WORDS[c.proposal.action];
  return c.proposal.action === "SEND_INVOICE" && c.message
    ? `${words}, in ${languageName(c.message.language)}`
    : words;
}

/** One sentence on what the eight rules decided, and what happens next. */
export function outcomeLine(c: CaseDetail, threshold?: string): string | null {
  if (!c.verdicts) return null;
  const by = (id: string) => c.verdicts!.find((v) => v.rule_id === id);
  switch (c.stage) {
    case "awaiting_approval":
      return `${money(c.amount, c.currency)} is at or above your ${threshold ? money(threshold, c.currency) : "approval"} threshold, so a person decides.`;
    case "scheduled": {
      // R4's reason reads "It is 06:22 in Mexico City. Queued for 09:00." When the queueing happened later,
      // at approval time, the re-check's reason is in the timeline instead.
      const r4 = by("R4");
      const requeue = [...c.events].reverse().find((e) => e.kind === "scheduled" && e.text.includes("It is"));
      const reason = r4?.verdict === "defer" ? r4.reason : requeue?.text.slice(requeue.text.indexOf("It is"));
      return reason
        ? `${reason.split(".")[0]}, outside 09:00–20:00, so it is queued for 09:00 local time.`
        : "Queued; it goes out when the rules allow.";
    }
    case "waiting":
      return "The payment may still clear, so Vesper waits instead of messaging.";
    case "sent":
    case "recovered":
      return c.verdicts.some((v) => v.verdict === "approve")
        ? "You approved it, the rules re-checked timing and limits, and PayPal emailed the invoice."
        : "All eight rules allowed it. PayPal emailed the invoice to the customer.";
    case "held":
      return c.reason_short ? `Held: ${c.reason_short}. Nothing was sent.` : "Held. Nothing was sent.";
    case "escalated":
      return "Handed to a person. Nothing was sent.";
    case "closed":
      return `Closed: ${CLOSED_WORDS[c.closed_reason ?? ""] ?? "closed"}. Nothing was sent.`;
    default:
      return null;
  }
}

export function verdictCounts(c: CaseDetail): string | null {
  if (!c.verdicts) return null;
  const n = { allow: 0, defer: 0, approve: 0, refuse: 0 };
  for (const v of c.verdicts) n[v.verdict]++;
  const parts = [`${n.allow} allow`];
  if (n.defer) parts.push(`${n.defer} defer`);
  if (n.approve) parts.push(`${n.approve} need approval`);
  if (n.refuse) parts.push(`${n.refuse} refuse`);
  return parts.join(" · ");
}

/** Step states from the stage alone, for list rows that don't carry the full case. */
export function stageSteps(stage: Stage): StepState[] {
  const d: StepState = "done";
  switch (stage) {
    case "failed":
      return [d, "active", "todo", "todo", "todo"];
    case "diagnosed":
      return [d, d, "active", "todo", "todo"];
    case "proposed":
    case "checked":
      return [d, d, d, "active", "todo"];
    case "awaiting_approval":
    case "scheduled":
    case "waiting":
      return [d, d, d, "waiting", "todo"];
    case "sent":
      return [d, d, d, d, "waiting"];
    case "recovered":
      return [d, d, d, d, "won"];
    case "held":
    case "escalated":
    case "closed":
      return [d, d, d, "stopped", "todo"];
  }
}
