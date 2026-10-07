"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { money } from "@/lib/format";
import type { Rule, Settings } from "@/lib/types";

export default function RulesPage() {
  const { data } = useSWR<{ rules: Rule[] }>("/rules", fetcher);
  const { data: settings } = useSWR<Settings>("/settings", fetcher);
  return (
    <>
      <section className="pt-12 pb-8">
        <p className="label">Step 04 · Checked</p>
        <h1 className="display mt-3 text-[40px] sm:text-[56px]">
          The model proposes.
          <br />
          These eight rules decide.
        </h1>
        <p className="mt-4 max-w-[620px] text-ink-2">
          Every rule runs on every proposal, in plain code, before anything is sent, and every case shows each
          verdict with its reason. They read PayPal&apos;s own failure code, never the model&apos;s opinion of it.
        </p>
      </section>
      {!data ? (
        <p className="label pulse">Loading…</p>
      ) : (
        <ol className="grid border-t border-l border-line bg-surface md:grid-cols-2">
          {data.rules.map((r, i) => (
            <li key={r.id} className="border-r border-b border-line px-5 py-5">
              <span className="font-mono text-[11px] text-ink-3">{String(i + 1).padStart(2, "0")}</span>
              <h2 className="mt-1 text-lg leading-7 font-semibold">{r.name}</h2>
              <p className="mt-1 text-ink-2">{r.description}</p>
            </li>
          ))}
        </ol>
      )}
      {settings && (
        <p className="mt-6 max-w-[700px] text-ink-2">
          Also: a kill switch pauses all sending without stopping diagnosis. Threshold today:{" "}
          {money(settings.approval_threshold, settings.currency)}. Contact window: {settings.contact_window.start}–
          {settings.contact_window.end} in the customer&apos;s local time.
        </p>
      )}
    </>
  );
}
