"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import { FailPaymentButton } from "@/components/FailPaymentButton";
import { KillSwitchBand } from "@/components/KillSwitchBand";
import { type CasePage, fetcher } from "@/lib/api";
import type { Health } from "@/lib/types";

export const AWAITING_KEY = "/cases?stage=awaiting_approval&limit=100";

export function TopBar() {
  const pathname = usePathname();
  const { data: health } = useSWR<Health>("/health", fetcher, { refreshInterval: 15000 });
  const { data: awaiting } = useSWR<CasePage>(AWAITING_KEY, fetcher, { refreshInterval: 3000 });
  const count = awaiting?.cases.length ?? 0;
  const links = [
    { href: "/", label: "Floor", active: pathname === "/" || pathname.startsWith("/cases") },
    { href: "/approvals", label: count > 0 ? `Approvals (${count})` : "Approvals", active: pathname.startsWith("/approvals") },
    { href: "/rules", label: "Rules", active: pathname.startsWith("/rules") },
  ];
  return (
    <header>
      <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-surface px-4 py-3 sm:px-6">
        <Link href="/" className="font-semibold">
          Vesper
        </Link>
        {links.map((l) => (
          <Link key={l.href} href={l.href} className={l.active ? "text-ink" : "text-ink-2 hover:text-ink"}>
            {l.label}
          </Link>
        ))}
        {health?.demo_mode && <FailPaymentButton />}
      </nav>
      {health?.kill_switch && <KillSwitchBand />}
    </header>
  );
}
