"use client";

import { useState } from "react";
import { StoreCheckout } from "@/components/StoreCheckout";
import { api, ApiError } from "@/lib/api";
import type { Settings } from "@/lib/types";

type Kind = "subscription" | "big_order";

function FailButton({ kind, label, onCase }: { kind: Kind; label: string; onCase: (id: string) => void }) {
  const [state, setState] = useState<"idle" | "busy" | "limited" | "error">("idle");
  async function go() {
    setState("busy");
    try {
      const r = await api.failPayment(kind);
      if (r.case_id) onCase(r.case_id);
      setState("idle");
    } catch (e) {
      setState(e instanceof ApiError && e.status === 429 ? "limited" : "error");
      setTimeout(() => setState("idle"), 5000);
    }
  }
  return (
    <>
      <button className="btn btn-primary w-full" disabled={state === "busy"} onClick={go}>
        {state === "busy" ? "Failing it…" : label}
      </button>
      {state === "limited" && <p className="mt-2 text-[13px] text-refused">That&apos;s the limit for now. Try again in a minute.</p>}
      {state === "error" && <p className="mt-2 text-[13px] text-refused">Vesper couldn&apos;t reach the server. Try again.</p>}
    </>
  );
}

function Card({ n, title, children, id }: { n: string; title: string; children: React.ReactNode; id?: string }) {
  return (
    <article id={id} className="flex flex-col border border-line bg-surface p-5 scroll-mt-24">
      <span className="font-mono text-[11px] text-ink-3">{n}</span>
      <h3 className="mt-1 text-xl leading-7 font-semibold tracking-[-0.01em]">{title}</h3>
      {children}
    </article>
  );
}

export function ScenarioCards({ settings, onCase }: { settings?: Settings; onCase: (id: string) => void }) {
  const clientId = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID ?? "";
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card n="01" title="A renewal bounces">
        <p className="mt-2 flex-1 text-ink-2">
A $29 subscription renewal fails.
        </p>
        <div className="mt-4" />
        <FailButton kind="subscription" label="Fail a renewal" onCase={onCase} />
      </Card>

      <Card n="02" title="A card declines at checkout" id="checkout">
        <p className="mt-2 text-ink-2">
Buy the $89 Linen Throw. PayPal declines it for real.
        </p>
        {settings?.sandbox_buyer_email && (
          <p className="mt-3 border border-line bg-paper px-3 py-2 text-[13px] leading-5">
            <span className="label block">Log in to PayPal as</span>
            <span className="font-mono text-[12px] break-all">{settings.sandbox_buyer_email}</span>
          </p>
        )}
        <div className="mt-4 flex-1">
          {clientId ? (
            <StoreCheckout clientId={clientId} onCase={onCase} />
          ) : (
            <p className="text-refused">The PayPal client ID is not configured.</p>
          )}
        </div>
      </Card>

      <Card n="03" title="A big order needs you">
        <p className="mt-2 flex-1 text-ink-2">
A $640 order fails. Over $500, you decide.
        </p>
        <div className="mt-4" />
        <FailButton kind="big_order" label="Fail a big order" onCase={onCase} />
      </Card>
    </div>
  );
}
