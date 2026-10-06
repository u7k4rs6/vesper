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
      <h1 className="text-[22px] leading-7 font-semibold">The eight rules</h1>
      <p className="mt-3">
        Vesper&apos;s model proposes; this code decides. Every rule below runs before anything is sent, and you can see
        each verdict on every case.
      </p>
      {!data ? (
        <p className="mt-6 text-ink-2">Loading…</p>
      ) : (
        <ol className="mt-6 flex flex-col gap-5">
          {data.rules.map((r) => (
            <li key={r.id}>
              <h2 className="text-base leading-6 font-semibold">{r.name}</h2>
              <p>{r.description}</p>
            </li>
          ))}
        </ol>
      )}
      {settings && (
        <p className="mt-8 text-ink-2">
          Also: a kill switch pauses all sending without stopping diagnosis. Threshold today:{" "}
          {money(settings.approval_threshold, settings.currency)}. Contact window: {settings.contact_window.start}–
          {settings.contact_window.end} in the customer&apos;s local time.
        </p>
      )}
    </>
  );
}
