"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { api, ApiError } from "@/lib/api";

type State = "idle" | "approving" | "declining" | "approved" | "declined" | "error";

/** Approve / Don't send. Confirms inline (no modal); the next poll shows what happened. */
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
  const size = compact ? "!px-3 !py-2" : "";
  return (
    <span className="flex flex-wrap items-center gap-2">
      <button className={`btn btn-primary ${size}`} disabled={busy} onClick={() => act("approve")}>
        {state === "approving" || state === "approved" ? "Approved, sending…" : "Approve and send"}
      </button>
      <button className={`btn btn-ghost ${size}`} disabled={busy} onClick={() => act("decline")}>
        {state === "declining" || state === "declined" ? "Held" : "Don't send"}
      </button>
      {state === "error" && <span className="text-refused">Vesper couldn&apos;t reach the server.</span>}
    </span>
  );
}
