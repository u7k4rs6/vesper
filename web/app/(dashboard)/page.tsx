"use client";

import useSWR from "swr";
import useSWRInfinite from "swr/infinite";
import { CaseList } from "@/components/CaseList";
import { Metric } from "@/components/Metric";
import { type CasePage, fetcher } from "@/lib/api";
import { money } from "@/lib/format";
import type { Health, Metrics } from "@/lib/types";

const PAGE = 50;

export default function Floor() {
  const { data: health } = useSWR<Health>("/health", fetcher);
  const { data: metrics, error: metricsError } = useSWR<Metrics>("/metrics/today", fetcher, { refreshInterval: 3000 });
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

  return (
    <>
      {(error || metricsError) && <p className="mb-6 text-refused">Vesper couldn&apos;t reach the server. It will keep trying.</p>}

      <div className="grid gap-6 sm:grid-cols-2">
        <Metric
          label="Recovered today"
          value={metrics ? money(metrics.recovered_total, metrics.currency) : "—"}
          sub={metrics ? `from ${metrics.recovered_count} ${metrics.recovered_count === 1 ? "payment" : "payments"}` : ""}
        />
        <Metric
          label="Held back today"
          value={metrics ? String(metrics.held_back_count) : "—"}
          sub={metrics ? `messages not sent, ${metrics.queued_count} queued` : ""}
        />
      </div>

      <h1 className="mt-10 mb-3 text-base leading-6 font-semibold">Cases</h1>
      {isLoading && !pages ? (
        <p className="text-ink-2">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-ink-2">
          {health?.demo_mode
            ? "No cases yet. Press Fail a payment to watch one move through."
            : "No failed payments yet. Vesper is listening."}
        </p>
      ) : (
        <>
          <CaseList rows={rows} />
          {hasMore && (
            <button className="mt-4 text-action underline" onClick={() => setSize(size + 1)}>
              Show more
            </button>
          )}
        </>
      )}
    </>
  );
}
