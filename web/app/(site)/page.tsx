"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef } from "react";
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

const GUARANTEES = [
  { n: "2", text: "model calls per case, then the model is out of the loop" },
  { n: "0", text: "amounts written by the model; its output has no number fields" },
  { n: "8", text: "rules in plain code run before any customer hears anything" },
  { n: "0", text: "charges, ever. The only thing Vesper sends is an invoice" },
];

function Demo() {
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
      <section className="pt-14 pb-10 sm:pt-20">
        <p className="label">A PayPal recovery agent with guardrails</p>
        <h1 className="display mt-4 text-[44px] sm:text-[72px] lg:text-[84px]">
          A payment failed.
          <br />
          Watch Vesper win it back.
        </h1>
        <p className="mt-6 max-w-[620px] text-lg leading-7 text-ink-2">
          Vesper reads why a PayPal payment failed, proposes one safe next step, and checks it against eight rules
          in code before the customer hears anything. The model proposes; code decides. Nobody is ever charged.
        </p>
      </section>

      <StageStrip states={states} current={states ? currentStep(states) : undefined} />

      <section className="pt-12">
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <h2 className="label text-ink">Start here · pick a failure</h2>
          <span className="label hidden sm:inline">Everything below is live PayPal sandbox</span>
        </div>
        <ScenarioCards settings={settings} onCase={watch} />
      </section>

      <section id="case" ref={liveRef} className="scroll-mt-20 pt-12">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="label text-ink">Live case</h2>
          {live && (
            <Link href={`/cases/${live.id}`} className="label hover:text-ink">
              Open full case with timeline →
            </Link>
          )}
        </div>
        {!caseId ? (
          <div className="border border-dashed border-ink/25 bg-surface/60 px-6 py-12 text-center">
            <p className="text-lg font-medium">Your case will appear here.</p>
            <p className="mt-1 text-ink-2">Pick a failure above. It fills in step by step, in about twenty seconds.</p>
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

      <section className="pt-16">
        <h2 className="label mb-4 text-ink">What the code guarantees</h2>
        <div className="grid border-t border-l border-line bg-surface sm:grid-cols-2 lg:grid-cols-4">
          {GUARANTEES.map((g) => (
            <div key={g.text} className="border-r border-b border-line px-5 py-5">
              <p className="display text-[56px]">{g.n}</p>
              <p className="mt-3 text-ink-2">{g.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[13px] leading-5 text-ink-2">
          Each is enforced by a test that runs on every push.{" "}
          <Link href="/rules" className="underline hover:text-ink">
            Read the eight rules
          </Link>{" "}
          or{" "}
          <Link href="/floor" className="underline hover:text-ink">
            see every case on the Floor
          </Link>
          .
        </p>
      </section>
    </>
  );
}

export default function DemoPage() {
  return (
    <Suspense fallback={<p className="label pt-20">Loading…</p>}>
      <Demo />
    </Suspense>
  );
}
