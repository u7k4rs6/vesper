"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef } from "react";
import useSWR from "swr";
import { CaseStory } from "@/components/CaseStory";
import { ScenarioCards } from "@/components/ScenarioCards";
import { StageDots } from "@/components/StageDots";
import { StageStrip } from "@/components/StageStrip";
import { fetcher } from "@/lib/api";
import { money } from "@/lib/format";
import { currentStep, stepStates } from "@/lib/story";
import type { CaseDetail, Settings } from "@/lib/types";
import { stageToDots } from "@/lib/types";

/** The live part of the demo: the strip, the scenario cards and the case as it unfolds. */
export function DemoLive() {
  const router = useRouter();
  const params = useSearchParams();
  const caseId = params.get("case");
  const liveRef = useRef<HTMLElement>(null);
  const { data: settings } = useSWR<Settings>("/settings", fetcher);
  const { data: live } = useSWR<CaseDetail>(caseId ? `/cases/${encodeURIComponent(caseId)}` : null, fetcher, {
    refreshInterval: (c) => (c && stageToDots(c.stage).terminal ? 0 : 1500),
  });

  const watch = useCallback(
    (id: string) => router.replace(`/?case=${encodeURIComponent(id)}#case`, { scroll: false }),
    [router],
  );

  useEffect(() => {
    if (caseId) liveRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [caseId]);

  const states = live ? stepStates(live) : undefined;

  return (
    <>
      <StageStrip states={states} current={states ? currentStep(states) : undefined} />

      <section className="pt-12">
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <h2 className="label text-ink">Start here · pick a failure</h2>
        </div>
        <ScenarioCards settings={settings} onCase={watch} />
      </section>

      <section id="case" ref={liveRef} className="scroll-mt-20 pt-12">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="label text-ink">Live case</h2>
          {live && (
            <Link href={`/cases/${live.id}`} className="label hover:text-ink">
              Full case →
            </Link>
          )}
        </div>
        {!caseId ? (
          <div className="border border-dashed border-ink/25 bg-surface/60 px-6 py-12 text-center">
            <p className="text-lg font-medium">Pick a failure. The case appears here.</p>
          </div>
        ) : !live ? (
          <p className="label pulse">Opening the case…</p>
        ) : (
          <div className="border border-line bg-surface">
            <header className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-line px-5 py-4 sm:px-6">
              <p className="text-2xl leading-8 font-semibold tracking-[-0.01em]">
                {live.first_name} · {live.place}
              </p>
              <p className="flex items-center gap-4">
                <StageDots stage={live.stage} size="header" />
                <span className="font-mono text-2xl leading-8">{money(live.amount, live.currency)}</span>
              </p>
            </header>
            <div className="px-5 py-6 sm:px-6">
              <CaseStory c={live} settings={settings} />
            </div>
          </div>
        )}
      </section>

    </>
  );
}
