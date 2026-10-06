"use client";

import Link from "next/link";
import { use } from "react";
import useSWR from "swr";
import { TONE_CLASS } from "@/components/CaseRow";
import { ChecksTable } from "@/components/ChecksTable";
import { MessagePanel } from "@/components/MessagePanel";
import { Panel } from "@/components/Panel";
import { StageDots } from "@/components/StageDots";
import { Timeline } from "@/components/Timeline";
import { ApiError, fetcher } from "@/lib/api";
import { lowerFirst, money, relativeTime } from "@/lib/format";
import type { CaseDetail, Settings } from "@/lib/types";
import { ACTION_WORDS, SOURCE_WORDS, stageToDots } from "@/lib/types";

const CLOSED_WORDS: Record<string, string> = {
  paid_elsewhere: "paid another way",
  refunded: "the order was refunded",
  frozen: "a dispute was opened",
  expired: "no payment within the time limit",
  no_action: "the model proposed doing nothing",
  invoice_cancelled: "the invoice was cancelled",
};

function terminalNote(c: CaseDetail): string | null {
  if (c.stage === "held" && c.reason_short) return `Held: ${lowerFirst(c.reason_short)}.`;
  if (c.stage === "escalated" && c.reason_short) return `Escalated: ${lowerFirst(c.reason_short)}.`;
  if (c.stage === "closed") return `Closed: ${CLOSED_WORDS[c.closed_reason ?? ""] ?? "closed"}.`;
  return null;
}

export default function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: c, error } = useSWR<CaseDetail>(`/cases/${encodeURIComponent(id)}`, fetcher, {
    refreshInterval: (latest) => (latest && stageToDots(latest.stage).terminal ? 0 : 2000),
  });
  const { data: settings } = useSWR<Settings>("/settings", fetcher);

  if (error instanceof ApiError && error.status === 404) {
    return (
      <>
        <Link href="/" className="text-action">← Floor</Link>
        <p className="mt-6">This case does not exist.</p>
      </>
    );
  }
  if (!c) {
    return error ? (
      <p className="text-refused">Vesper couldn&apos;t reach the server. It will keep trying.</p>
    ) : (
      <p className="text-ink-2">Loading…</p>
    );
  }

  const view = stageToDots(c.stage);
  const note = terminalNote(c);
  const toolkitCalls = c.events.filter((e) => e.kind === "toolkit_call");

  return (
    <>
      <Link href="/" className="text-action">← Floor</Link>

      <header className="mt-6 mb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4">
          <h1 className="text-[22px] leading-7 font-semibold">
            {c.first_name} · {c.place}
          </h1>
          <p className="text-[22px] leading-7 font-semibold">{money(c.amount, c.currency)}</p>
        </div>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <p className="text-[13px] leading-5 text-ink-2">
            {SOURCE_WORDS[c.source]} · {relativeTime(c.created_at, "long")}
          </p>
          <p className="flex items-center gap-2">
            <StageDots stage={c.stage} size="header" />
            <span className={TONE_CLASS[view.tone]}>{view.label}</span>
          </p>
        </div>
        {note && <p className="mt-2 text-ink-2">{note}</p>}
      </header>

      <div className="flex flex-col gap-4">
        <Panel title="What happened">
          {c.diagnosis ? (
            <>
              <p>{c.diagnosis.cause}</p>
              <p className="mt-3">{c.diagnosis.customer_context}</p>
              <p className="mt-3 text-ink-2">Confidence: {c.diagnosis.confidence}</p>
            </>
          ) : (
            <p className="text-ink-2">
              PayPal reported {c.failure_code}. {c.stage === "failed" ? "Diagnosing…" : "No diagnosis was made."}
            </p>
          )}
        </Panel>

        <Panel title="What Vesper proposed">
          {c.proposal ? (
            <>
              <p className="font-medium">{ACTION_WORDS[c.proposal.action]}</p>
              <p className="mt-1">{c.proposal.rationale}</p>
              {toolkitCalls.map((e, i) => (
                <p key={i} className="mt-1 text-ink-2">{e.text}</p>
              ))}
            </>
          ) : (
            <p className="text-ink-2">{c.diagnosis && c.stage !== "escalated" ? "Proposing…" : "No proposal was made."}</p>
          )}
        </Panel>

        <Panel title="Checks">
          <ChecksTable verdicts={c.verdicts} />
        </Panel>

        <MessagePanel c={c} />

        <Timeline events={c.events} timeZone={settings?.merchant_timezone ?? "UTC"} />
      </div>
    </>
  );
}
