// Typed fetchers. Every call goes through the server-side proxy, which adds the dashboard token.
import type { CaseDetail, CaseRow, Health, Metrics, Rule, Settings } from "@/lib/types";

const BASE = "/api/proxy";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, body?.error?.code ?? "unknown", body?.error?.message ?? "Request failed.");
  }
  return body as T;
}

export type CaptureResult = { status: "completed" } | { status: "failed"; case_id: string };
export type CasePage = { cases: CaseRow[]; next_cursor: string | null };

export const api = {
  health: () => call<Health>("/health"),
  metrics: () => call<Metrics>("/metrics/today"),
  cases: (query = "") => call<CasePage>(`/cases${query}`),
  case: (id: string) => call<CaseDetail>(`/cases/${encodeURIComponent(id)}`),
  rules: () => call<{ rules: Rule[] }>("/rules"),
  settings: () => call<Settings>("/settings"),
  approve: (id: string) => call<{ stage: string }>(`/cases/${encodeURIComponent(id)}/approve`, { method: "POST" }),
  decline: (id: string) => call<{ stage: string }>(`/cases/${encodeURIComponent(id)}/decline`, { method: "POST" }),
  failPayment: (kind: "subscription" | "capture_denied") =>
    call<{ ok: boolean }>("/demo/fail", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind }),
    }),
  createStoreOrder: () => call<{ order_id: string }>("/demo/store/orders", { method: "POST" }),
  captureStoreOrder: (orderId: string, forceDecline: boolean) =>
    call<CaptureResult>(
      `/demo/store/orders/${encodeURIComponent(orderId)}/capture?force_decline=${forceDecline}`,
      { method: "POST" },
    ),
};

// SWR keys double as fetch paths.
export const fetcher = <T,>(path: string) => call<T>(path);
