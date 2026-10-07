"use client";

import Link from "next/link";
import useSWR from "swr";
import useSWRInfinite from "swr/infinite";
import { CaseList } from "@/components/CaseList";
import { AWAITING_KEY } from "@/components/SiteHeader";
import { type CasePage, fetcher } from "@/lib/api";
import { money } from "@/lib/format";
import type { Metrics } from "@/lib/types";

const PAGE = 50;

function Stat({ value, label, sub, tone = "" }: { value: string; label: string; sub: string; tone?: string }) {
  return (
    <div className="border-r border-b border-line px-5 py-5">
      <p className={`display text-[44px] sm:text-[52px] ${tone}`}>{value}</p>
      <p className="label mt-3 text-ink">{label}</p>
      <p className="mt-1 text-[13px] leading-5 text-ink-2">{sub}</p>
    </div>
  );
}

export default function Floor() {
  const { data: m, error: metricsError } = useSWR<Metrics>("/metrics/today", fetcher, { refreshInterval: 3000 });
  const { data: awaiting } = useSWR<CasePage>(AWAITING_KEY, fetcher, { refreshInterval: 3000 });
  const { data: pages, error, size, setSize, isLoading } = useSWRInfinite<CasePage>(
    (index, previous) => {
      if (previous && !previous.next_cursor) return null;
      return index === 0 ? `/cases?limit=${PAGE}` : `/cases?limit=${PAGE}&cursor=${previous!.next_cursor}`;
    },
    fetcher,
    { refreshInterval: 3000 },
  );
  const rows = pages?.flatMap((p) => p.cases) ?? [];
  const hasMore = Boolean(pages?.[pages.length - 1]?.next_cursor);
  const waiting = awaiting?.cases.length ?? 0;

  return (
    <>
      <section className="pt-12 pb-8">
        <p className="label">The merchant&apos;s view</p>
        <h1 className="display mt-3 text-[40px] sm:text-[56px]">Floor</h1>
        <p className="mt-3 max-w-[560px] text-ink-2">
          Every failed payment, and what Vesper did about it. Updates live.
        </p>
      </section>

      {(error || metricsError) && <p className="mb-4 text-refused">Vesper couldn&apos;t reach the server. It will keep trying.</p>}

      <div className="grid grid-cols-2 border-t border-l border-line bg-surface lg:grid-cols-4">
        <Stat
          value={m ? money(m.recovered_total, m.currency) : "—"}
          label="Recovered today"
          sub={m ? `from ${m.recovered_count} ${m.recovered_count === 1 ? "payment" : "payments"}` : ""}
          tone={m && Number(m.recovered_total) > 0 ? "text-recovered" : ""}
        />
        <Stat value={m ? String(m.held_back_count) : "—"} label="Held back today" sub="messages the rules stopped or delayed" />
        <Stat value={m ? String(m.queued_count) : "—"} label="Queued" sub="waiting for 09:00 in the customer's time zone" tone={m?.queued_count ? "text-deferred" : ""} />
        <Stat value={awaiting ? String(waiting) : "—"} label="Waiting for you" sub="at or above the approval threshold" tone={waiting ? "text-deferred" : ""} />
      </div>

      <div className="mt-10 mb-3 flex items-baseline justify-between">
        <h2 className="label text-ink">Cases</h2>
        <Link href="/" className="label hover:text-ink">
          Make one fail →
        </Link>
      </div>
      {isLoading && !pages ? (
        <p className="label pulse">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="border border-dashed border-ink/25 bg-surface/60 px-6 py-10 text-center">
          <p className="font-medium">No cases yet.</p>
          <p className="mt-1 text-ink-2">
            <Link href="/" className="underline">Fail a payment on the demo</Link> to watch one move through.
          </p>
        </div>
      ) : (
        <>
          <CaseList rows={rows} />
          {hasMore && (
            <button className="btn btn-ghost mt-4" onClick={() => setSize(size + 1)}>
              Show more
            </button>
          )}
        </>
      )}
    </>
  );
}
