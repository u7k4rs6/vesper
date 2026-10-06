"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { Panel } from "@/components/Panel";
import { api, ApiError } from "@/lib/api";
import { money } from "@/lib/format";

type State = "idle" | "approving" | "declining" | "approved" | "declined" | "error";

/** Approve / Don't send. Confirms inline (no modal); the next poll replaces it with the updated case. */
export function ApprovalButtons({ caseId, compact = false }: { caseId: string; compact?: boolean }) {
  const [state, setState] = useState<State>("idle");
  const { mutate } = useSWRConfig();
  const refresh = () => mutate((key) => typeof key === "string" && (key.startsWith("/cases") || key.startsWith("/metrics")));

  async function act(kind: "approve" | "decline") {
    setState(kind === "approve" ? "approving" : "declining");
    try {
      await (kind === "approve" ? api.approve(caseId) : api.decline(caseId));
      setState(kind === "approve" ? "approved" : "declined");
    } catch (e) {
      // 409: someone else already acted; the refresh shows what happened.
      setState(e instanceof ApiError && e.status === 409 ? "idle" : "error");
    }
    refresh();
  }

  const busy = state !== "idle" && state !== "error";
  const pad = compact ? "px-3 py-1" : "px-4 py-2";
  return (
    <span className="flex flex-wrap items-center gap-2">
      <button
        className={`rounded-md bg-action font-medium text-white disabled:opacity-70 ${pad}`}
        disabled={busy}
        onClick={() => act("approve")}
      >
        {state === "approving" || state === "approved" ? "Approved — sending…" : "Approve and send"}
      </button>
      <button
        className={`rounded-md border border-line bg-surface disabled:opacity-70 ${pad}`}
        disabled={busy}
        onClick={() => act("decline")}
      >
        {state === "declining" || state === "declined" ? "Held" : "Don't send"}
      </button>
      {state === "error" && <span className="text-refused">Vesper couldn&apos;t reach the server.</span>}
    </span>
  );
}

export function ApprovalPanel({
  caseId,
  amount,
  currency,
  threshold,
}: {
  caseId: string;
  amount: string;
  currency: string;
  threshold: string | undefined;
}) {
  return (
    <Panel title="Needs your approval">
      <p>
        {money(amount, currency)} is at or above your {threshold ? money(threshold, currency) : "approval"} threshold.
      </p>
      <div className="mt-3">
        <ApprovalButtons caseId={caseId} />
      </div>
    </Panel>
  );
}
