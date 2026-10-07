"use client";

import Link from "next/link";
import { use } from "react";
import useSWR from "swr";
import { TONE_CLASS } from "@/components/CaseRow";
import { CaseStory } from "@/components/CaseStory";
import { StageStrip } from "@/components/StageStrip";
import { Timeline } from "@/components/Timeline";
import { ApiError, fetcher } from "@/lib/api";
import { money, relativeTime } from "@/lib/format";
import { currentStep, stepStates } from "@/lib/story";
import type { CaseDetail, Settings } from "@/lib/types";
import { SOURCE_WORDS, stageToDots } from "@/lib/types";

export default function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: c, error } = useSWR<CaseDetail>(`/cases/${encodeURIComponent(id)}`, fetcher, {
    refreshInterval: (latest) => (latest && stageToDots(latest.stage).terminal ? 0 : 2000),
  });
  const { data: settings } = useSWR<Settings>("/settings", fetcher);

  if (error instanceof ApiError && error.status === 404) {
    return (
      <div className="pt-12">
        <Link href="/floor" className="label hover:text-ink">← Floor</Link>
        <p className="mt-6 text-lg">This case does not exist.</p>
      </div>
    );
  }
  if (!c) {
    return error ? (
      <p className="pt-12 text-refused">Vesper couldn&apos;t reach the server. It will keep trying.</p>
    ) : (
      <p className="label pulse pt-12">Loading…</p>
    );
  }

  const view = stageToDots(c.stage);
  const states = stepStates(c);

  return (
    <>
      <div className="pt-10">
        <Link href="/floor" className="label hover:text-ink">← Floor</Link>
      </div>
      <header className="pt-5 pb-8">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <h1 className="display text-[40px] sm:text-[52px]">
            {c.first_name} · {c.place}
          </h1>
          <p className="font-mono text-[28px] sm:text-[34px]">{money(c.amount, c.currency)}</p>
        </div>
        <p className="mt-3 flex flex-wrap items-baseline gap-x-3 text-ink-2">
          <span>{SOURCE_WORDS[c.source]}</span>
          <span>·</span>
          <span>{relativeTime(c.created_at, "long")}</span>
          <span>·</span>
          <span className={`label ${TONE_CLASS[view.tone]}`}>{view.label}</span>
        </p>
      </header>

      <StageStrip states={states} current={currentStep(states)} />

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_320px]">
        <section className="border border-line bg-surface px-5 py-6 sm:px-6">
          <CaseStory c={c} settings={settings} />
        </section>
        <aside>
          <h2 className="label mb-3 text-ink">Timeline</h2>
          <Timeline events={c.events} timeZone={settings?.merchant_timezone ?? "UTC"} />
          <p className="mt-3 text-[13px] leading-5 text-ink-2">
            Append-only. Times are the merchant&apos;s ({settings?.merchant_timezone ?? "UTC"}).
          </p>
        </aside>
      </div>
    </>
  );
}
