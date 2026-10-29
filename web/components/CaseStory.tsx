"use client";

import { ApprovalButtons } from "@/components/ApprovalPanel";
import { ChecksGrid } from "@/components/ChecksGrid";
import { ActorTag } from "@/components/StageStrip";
import { clock, money } from "@/lib/format";
import {
  notChasedLine,
  outcomeLine,
  proposedHeadline,
  STEPS,
  stepStates,
  type StepState,
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
    <p key="failed">
      {c.failure_code}
      <span className="text-ink-2">
        {" "}
        · {c.description} · {money(c.amount, c.currency)}
      </span>
    </p>,
    // 02 Diagnosed
    c.diagnosis ? (
      <p>{c.diagnosis.cause}</p>
    ) : states[1] === "active" ? (
      <p className="text-ink-2">Reading the evidence…</p>
    ) : states[1] === "stopped" ? (
      <p className="text-refused">{lastEvent(c, ["escalated"]) ?? "Stopped."}</p>
    ) : null,
    // 03 Proposed
    c.proposal ? (
      <>
        <p className="font-medium">{proposedHeadline(c)}</p>
        {c.message && (
          <>
            <blockquote lang={c.message.language} className="mt-2 border-l-2 border-line pl-3 text-ink-2">
              {c.message.rendered}
            </blockquote>
            <p className="label mt-1.5 pl-3.5">
              {c.message.fallback_used ? "Standard template" : "Words by Claude · numbers by code"}
            </p>
          </>
        )}
      </>
    ) : states[2] === "active" ? (
      <p className="text-ink-2">Choosing an action…</p>
    ) : states[2] === "stopped" ? (
      <p className="text-refused">{lastEvent(c, ["escalated"]) ?? "Stopped."}</p>
    ) : null,
    // 04 Checked
    c.verdicts ? (
      <>
        <p className="font-medium">{outcomeLine(c, settings?.approval_threshold)}</p>
        {c.stage === "awaiting_approval" && (
          <div className="mt-3">
            <ApprovalButtons caseId={c.id} />
          </div>
        )}
        <div className="mt-2">
          <ChecksGrid verdicts={c.verdicts} />
        </div>
      </>
    ) : states[3] === "active" ? (
      <p className="text-ink-2">Running the rules…</p>
    ) : null,
    // 05 Recovered
    c.stage === "recovered" ? (
      <p className="font-medium text-recovered">
        Paid{c.recovered_at ? ` at ${clock(c.recovered_at, tz)}` : ""}. Confirmed by PayPal.
      </p>
    ) : c.stage === "sent" && c.message?.payer_link ? (
      <button className="btn btn-primary" onClick={() => openInvoice(c.message!.payer_link!)}>
        Pay as the customer ↗
      </button>
    ) : c.stage === "scheduled" ? (
      <p className="text-ink-2">Sends at 09:00 their time.</p>
    ) : c.stage === "waiting" ? (
      <p className="text-ink-2">Waiting for the payment to clear.</p>
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
                {body[i]}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
