"use client";

import useSWR from "swr";
import { ApprovalButtons } from "@/components/ApprovalPanel";
import { CaseList } from "@/components/CaseList";
import { AWAITING_KEY } from "@/components/TopBar";
import { type CasePage, fetcher } from "@/lib/api";

export default function ApprovalsPage() {
  const { data, error } = useSWR<CasePage>(AWAITING_KEY, fetcher, { refreshInterval: 3000 });
  return (
    <>
      <h1 className="mb-4 text-[22px] leading-7 font-semibold">Waiting for you</h1>
      {error && <p className="mb-4 text-refused">Vesper couldn&apos;t reach the server. It will keep trying.</p>}
      {!data ? (
        <p className="text-ink-2">Loading…</p>
      ) : data.cases.length === 0 ? (
        <p className="text-ink-2">Nothing needs approval.</p>
      ) : (
        <CaseList rows={data.cases} actions={(row) => <ApprovalButtons caseId={row.id} compact />} />
      )}
    </>
  );
}
