"use client";

import { ApprovalButtons } from "@/components/ApprovalPanel";
import { ChecksGrid } from "@/components/ChecksGrid";
import { ActorTag } from "@/components/StageStrip";
import { clock, languageName } from "@/lib/format";
import {
  failedLine,
  notChasedLine,
  outcomeLine,
  proposedHeadline,
  STEPS,
  stepStates,
  type StepState,
  verdictCounts,
} from "@/lib/story";
import type { CaseDetail, Settings } from "@/lib/types";

const MARKER: Record<StepState, string> = {
  todo: "border-line bg-surface",
  active: "border-ink bg-surface pulse",
  done: "border-ink bg-ink",
  waiting: "border-deferred bg-deferred",
  stopped: "border-refused bg-refused",
  won: "border-recovered bg-recovered",
};

const CHIP: Partial<Record<StepState, { text: string; className: string }>> = {
  active: { text: "Working…", className: "text-ink" },
  waiting: { text: "Waiting", className: "text-deferred" },
  stopped: { text: "Stopped here", className: "text-refused" },
  won: { text: "Done", className: "text-recovered" },
};

function lastEvent(c: CaseDetail, kinds: string[]): string | undefined {
  return [...c.events].reverse().find((e) => kinds.includes(e.kind))?.text;
}

export function openInvoice(url: string) {
  const w = window.open(url, "vesper-pay", "popup,width=520,height=780");
  if (!w) window.open(url, "_blank", "noopener");
}

/** A case as five steps, each saying what happened, who did it, and what comes next. */
export function CaseStory({ c, settings }: { c: CaseDetail; settings?: Settings }) {
  const states = stepStates(c);
  const tz = settings?.merchant_timezone ?? "UTC";

  const body = [
    // 01 Failed
    <>
      <p>{failedLine(c)}</p>
      <p className="mt-1 text-ink-2">
        The customer is {c.first_name}, in {c.place}.
      </p>
    </>,
    // 02 Diagnosed
    c.diagnosis ? (
      <>
        <p>{c.diagnosis.cause}</p>
        <p className="mt-2 text-ink-2">{c.diagnosis.customer_context}</p>
        <p className="label mt-2">Confidence: {c.diagnosis.confidence}</p>
      </>
    ) : states[1] === "active" ? (
      <p className="text-ink-2">
        Claude is reading the evidence: the failure code, the amount, the customer&apos;s first name, country and
        local time. Never their email, and never a PayPal id.
      </p>
    ) : states[1] === "stopped" ? (
      <p className="text-refused">{lastEvent(c, ["escalated"]) ?? "Stopped before a diagnosis."}</p>
    ) : null,
    // 03 Proposed
    c.proposal ? (
      <>
        <p className="font-medium">{proposedHeadline(c)}</p>
        <p className="mt-1 text-ink-2">{c.proposal.rationale}</p>
        {c.message && (
          <figure className="mt-3 border border-line bg-paper px-4 py-3">
            <figcaption className="label mb-1.5">
              Message on the invoice · {languageName(c.message.language)}
              {c.message.fallback_used ? " · standard template" : ""}
            </figcaption>
            <blockquote lang={c.message.language} className="text-[15px] leading-6">
              {c.message.rendered}
            </blockquote>
            <p className="mt-2 text-[13px] leading-5 text-ink-2">
              {c.message.fallback_used
                ? "Claude's draft failed the safety check, so Vesper's standard template was used instead."
                : "Claude wrote the words. Every name, amount and date was filled in by code."}
            </p>
          </figure>
        )}
      </>
    ) : states[2] === "active" ? (
      <p className="text-ink-2">
        Claude is choosing one of four actions: send an invoice, wait, hand to a person, or do nothing. None of
        them carries an amount.
      </p>
    ) : states[2] === "stopped" ? (
      <p className="text-refused">{lastEvent(c, ["escalated"]) ?? "Stopped before a proposal."}</p>
    ) : null,
    // 04 Checked
    c.verdicts ? (
      <>
        <p className="label">8 rules ran in code · {verdictCounts(c)}</p>
        <p className="mt-1 font-medium">{outcomeLine(c, settings?.approval_threshold)}</p>
        {c.stage === "awaiting_approval" && (
          <div className="mt-3">
            <ApprovalButtons caseId={c.id} />
          </div>
        )}
        <div className="mt-3">
          <ChecksGrid verdicts={c.verdicts} />
        </div>
      </>
    ) : states[3] === "active" ? (
      <p className="text-ink-2">Running the eight rules. They read PayPal&apos;s code, not the model&apos;s opinion.</p>
    ) : null,
    // 05 Recovered
    c.stage === "recovered" ? (
      <p className="font-medium text-recovered">
        Paid. PayPal confirmed it with a signed webhook
        {c.recovered_at ? ` at ${clock(c.recovered_at, tz)}` : ""}. Nobody was charged by Vesper.
      </p>
    ) : c.stage === "sent" ? (
      <>
        <p>
          PayPal emailed the invoice. Pay it as the customer to finish the loop: log in as the sandbox buyer, and
          this page turns Recovered on its own once PayPal confirms.
        </p>
        {c.message?.payer_link && (
          <button className="btn btn-primary mt-3" onClick={() => openInvoice(c.message!.payer_link!)}>
            Pay as the customer ↗
          </button>
        )}
      </>
    ) : c.stage === "scheduled" ? (
      <p className="text-ink-2">The invoice goes out when the window opens; the customer can pay it then.</p>
    ) : c.stage === "awaiting_approval" ? (
      <p className="text-ink-2">Once approved, PayPal emails the invoice and the customer can pay it.</p>
    ) : c.stage === "waiting" ? (
      <p className="text-ink-2">If the payment clears, PayPal tells Vesper and the case closes.</p>
    ) : notChasedLine(c) ? (
      <p className="text-ink-2">{notChasedLine(c)}</p>
    ) : null,
  ];

  return (
    <ol>
      {STEPS.map((s, i) => {
        const state = states[i];
        const chip = CHIP[state];
        const last = i === STEPS.length - 1;
        return (
          <li key={s.key} className="grid grid-cols-[40px_1fr] gap-x-3 sm:grid-cols-[56px_1fr] sm:gap-x-4">
            <div className="flex flex-col items-center">
              <span className="font-mono text-[11px] text-ink-3">{s.n}</span>
              <span className={`dot mt-1.5 size-3 border ${MARKER[state]}`} />
              {!last && <span className={`mt-1 w-px flex-1 ${state === "todo" ? "bg-line" : "bg-ink/40"}`} />}
            </div>
            <div className={`${last ? "" : "pb-7"} ${state === "todo" ? "opacity-45" : ""}`}>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h3 className="text-lg leading-7 font-semibold">{s.title}</h3>
                <ActorTag actor={s.actor} />
                {chip && <span className={`label ${chip.className}`}>{chip.text}</span>}
              </div>
              <div className="mt-1 max-w-[680px] reveal" key={`${s.key}-${state}`}>
                {body[i] ?? <p className="text-ink-3">{s.caption}.</p>}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
