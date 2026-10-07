"use client";

import Link from "next/link";
import useSWR from "swr";
import { ApprovalButtons } from "@/components/ApprovalPanel";
import { CaseList } from "@/components/CaseList";
import { AWAITING_KEY } from "@/components/SiteHeader";
import { type CasePage, fetcher } from "@/lib/api";
import { money } from "@/lib/format";
import type { Settings } from "@/lib/types";

export default function ApprovalsPage() {
  const { data, error } = useSWR<CasePage>(AWAITING_KEY, fetcher, { refreshInterval: 3000 });
  const { data: settings } = useSWR<Settings>("/settings", fetcher);
  const threshold = settings ? money(settings.approval_threshold, settings.currency) : "the threshold";
  return (
    <>
      <section className="pt-12 pb-8">
        <p className="label">Rule 07 · Approval threshold</p>
        <h1 className="display mt-3 text-[40px] sm:text-[56px]">Waiting for you</h1>
        <p className="mt-3 max-w-[600px] text-ink-2">
          Payments at or above {threshold} never go out on their own. Approving re-checks the contact window,
          the frequency cap and any refund or dispute before PayPal sends anything.
        </p>
      </section>
      {error && <p className="mb-4 text-refused">Vesper couldn&apos;t reach the server. It will keep trying.</p>}
      {!data ? (
        <p className="label pulse">Loading…</p>
      ) : data.cases.length === 0 ? (
        <div className="border border-dashed border-ink/25 bg-surface/60 px-6 py-10 text-center">
          <p className="font-medium">Nothing needs approval.</p>
          <p className="mt-1 text-ink-2">
            <Link href="/" className="underline">Fail a big order on the demo</Link> to see one arrive here.
          </p>
        </div>
      ) : (
        <CaseList rows={data.cases} actions={(row) => <ApprovalButtons caseId={row.id} compact />} />
      )}
    </>
  );
}
