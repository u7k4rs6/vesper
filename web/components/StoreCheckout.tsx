"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

type PayPalButtons = { render: (el: HTMLElement) => Promise<void>; close?: () => Promise<void> };
type PayPalNamespace = {
  Buttons: (opts: {
    style?: Record<string, string | number>;
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

const SDK_ID = "paypal-sdk";
const TONE = { ink: "text-ink", refused: "text-refused", recovered: "text-recovered" } as const;

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

/** PayPal's own buttons for the $89 product, with the forced-decline toggle. Reports the case it opened. */
export function StoreCheckout({ clientId, onCase }: { clientId: string; onCase: (caseId: string) => void }) {
  const [forceDecline, setForceDecline] = useState(true);
  const [note, setNote] = useState<{ text: string; tone: "ink" | "refused" | "recovered" } | null>(null);
  const forceRef = useRef(forceDecline);
  const onCaseRef = useRef(onCase);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    forceRef.current = forceDecline;
    onCaseRef.current = onCase;
  }, [forceDecline, onCase]);

  useEffect(() => {
    let buttons: PayPalButtons | undefined;
    let cancelled = false;
    loadSdk(clientId)
      .then((paypal) => {
        if (cancelled || !container.current) return;
        buttons = paypal.Buttons({
          style: { layout: "vertical", shape: "rect", label: "pay", height: 40 },
          createOrder: async () => (await api.createStoreOrder()).order_id,
          onApprove: async ({ orderID }) => {
            setNote({ text: "Capturing the payment with PayPal…", tone: "ink" });
            try {
              const result = await api.captureStoreOrder(orderID, forceRef.current);
              if (result.status === "failed") {
                setNote({ text: "PayPal declined it. Vesper opened a case below.", tone: "refused" });
                onCaseRef.current(result.case_id);
              } else {
                setNote({ text: "Paid. No case needed, nothing for Vesper to do.", tone: "recovered" });
              }
            } catch (e) {
              setNote({ text: e instanceof ApiError ? e.message : "The payment could not be completed.", tone: "refused" });
            }
          },
          onError: () => setNote({ text: "PayPal could not start the checkout.", tone: "refused" }),
        });
        return buttons.render(container.current);
      })
      .catch(() => setNote({ text: "The PayPal buttons could not load.", tone: "refused" }));
    return () => {
      cancelled = true;
      buttons?.close?.().catch(() => {});
    };
  }, [clientId]);

  return (
    <div>
      <label className="flex cursor-pointer items-start gap-2.5">
        <input
          type="checkbox"
          className="mt-[5px] size-4 accent-[var(--ink)]"
          checked={forceDecline}
          onChange={(e) => setForceDecline(e.target.checked)}
        />
        <span>
          Make the payment fail
          <span className="block text-[13px] leading-5 text-ink-2">
            PayPal&apos;s sandbox returns a real INSTRUMENT_DECLINED.
          </span>
        </span>
      </label>
      <div ref={container} className="mt-3 min-h-[44px]" />
      {note && (
        <p aria-live="polite" className={`mt-2 text-[13px] leading-5 ${TONE[note.tone]}`}>
          {note.text}
        </p>
      )}
    </div>
  );
}
