"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

type PayPalButtons = { render: (el: HTMLElement) => Promise<void>; close?: () => Promise<void> };
type PayPalNamespace = {
  Buttons: (opts: {
    style?: Record<string, string>;
    createOrder: () => Promise<string>;
    onApprove: (data: { orderID: string }) => Promise<void>;
    onError: (err: unknown) => void;
  }) => PayPalButtons;
};

declare global {
  interface Window {
    paypal?: PayPalNamespace;
  }
}

type Outcome =
  | { kind: "idle" }
  | { kind: "working" }
  | { kind: "paid" }
  | { kind: "failed"; caseId: string }
  | { kind: "error"; message: string };

const SDK_ID = "paypal-sdk";

function loadSdk(clientId: string): Promise<PayPalNamespace> {
  if (window.paypal) return Promise.resolve(window.paypal);
  return new Promise((resolve, reject) => {
    const existing = document.getElementById(SDK_ID) as HTMLScriptElement | null;
    const script = existing ?? document.createElement("script");
    script.addEventListener("load", () => (window.paypal ? resolve(window.paypal) : reject(new Error("no sdk"))));
    script.addEventListener("error", () => reject(new Error("sdk failed to load")));
    if (!existing) {
      script.id = SDK_ID;
      script.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=USD&intent=capture`;
      document.body.appendChild(script);
    }
  });
}

export function StoreCheckout({ clientId }: { clientId: string }) {
  const [forceDecline, setForceDecline] = useState(true);
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });
  const forceRef = useRef(forceDecline);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    forceRef.current = forceDecline;
  }, [forceDecline]);

  useEffect(() => {
    let buttons: PayPalButtons | undefined;
    let cancelled = false;
    loadSdk(clientId)
      .then((paypal) => {
        if (cancelled || !container.current) return;
        buttons = paypal.Buttons({
          style: { layout: "vertical", shape: "rect", label: "pay" },
          createOrder: async () => (await api.createStoreOrder()).order_id,
          onApprove: async ({ orderID }) => {
            setOutcome({ kind: "working" });
            try {
              const result = await api.captureStoreOrder(orderID, forceRef.current);
              setOutcome(result.status === "failed" ? { kind: "failed", caseId: result.case_id } : { kind: "paid" });
            } catch (e) {
              setOutcome({ kind: "error", message: e instanceof ApiError ? e.message : "The payment could not be completed." });
            }
          },
          onError: () => setOutcome({ kind: "error", message: "PayPal could not start the checkout." }),
        });
        return buttons.render(container.current);
      })
      .catch(() => setOutcome({ kind: "error", message: "The PayPal buttons could not load." }));
    return () => {
      cancelled = true;
      buttons?.close?.().catch(() => {});
    };
  }, [clientId]);

  return (
    <div className="mt-8">
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          className="mt-[5px] size-4 accent-[var(--action)]"
          checked={forceDecline}
          onChange={(e) => setForceDecline(e.target.checked)}
        />
        <span>
          Make this payment fail
          <span className="block text-[13px] leading-5 text-ink-2">Sandbox negative test: INSTRUMENT_DECLINED</span>
        </span>
      </label>

      <div ref={container} className="mt-6 max-w-[400px]" />

      <div className="mt-6" aria-live="polite">
        {outcome.kind === "working" && <p className="text-ink-2">Completing the payment…</p>}
        {outcome.kind === "paid" && <p>Paid. Thank you.</p>}
        {outcome.kind === "failed" && (
          <p>
            The payment could not be completed. Vesper opened a case.{" "}
            <Link className="text-action underline" href={`/cases/${outcome.caseId}`}>
              Watch it on the Floor →
            </Link>
          </p>
        )}
        {outcome.kind === "error" && <p className="text-refused">{outcome.message}</p>}
      </div>
    </div>
  );
}
