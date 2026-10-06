"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

type Kind = "subscription" | "capture_denied";

export function FailPaymentButton() {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("Fail a payment");
  const busy = label !== "Fail a payment";
  const wrapper = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => wrapper.current && !wrapper.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function show(text: string, ms: number) {
    setLabel(text);
    setTimeout(() => setLabel("Fail a payment"), ms);
  }

  async function fail(kind: Kind) {
    setOpen(false);
    show("Failing…", 1500);
    try {
      await api.failPayment(kind);
    } catch (e) {
      show(e instanceof ApiError && e.status === 429 ? "Try again in a minute" : "Could not fail a payment", 5000);
    }
  }

  return (
    <div ref={wrapper} className="relative ml-auto">
      <button
        className="rounded-md bg-action px-3 py-1.5 font-medium text-white disabled:opacity-70"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={busy}
        onClick={() => setOpen((o) => !o)}
      >
        {label}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-10 mt-2 w-56 rounded-lg border border-line bg-surface py-1">
          <button role="menuitem" className="block w-full px-4 py-2 text-left hover:bg-paper" onClick={() => fail("subscription")}>
            Subscription renewal
          </button>
          <button role="menuitem" className="block w-full px-4 py-2 text-left hover:bg-paper" onClick={() => fail("capture_denied")}>
            Card capture denied
          </button>
        </div>
      )}
    </div>
  );
}
