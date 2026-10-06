"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import { KillSwitchBand } from "@/components/KillSwitchBand";
import { fetcher } from "@/lib/api";
import type { Health } from "@/lib/types";

const LINKS = [
  { href: "/", label: "Floor" },
  { href: "/rules", label: "Rules" },
];

export function TopBar() {
  const pathname = usePathname();
  const { data: health } = useSWR<Health>("/health", fetcher, { refreshInterval: 15000 });
  return (
    <header>
      <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line bg-surface px-4 py-3 sm:px-6">
        <Link href="/" className="font-semibold">
          Vesper
        </Link>
        {LINKS.map((l) => {
          const active = l.href === "/" ? pathname === "/" || pathname.startsWith("/cases") : pathname.startsWith(l.href);
          return (
            <Link key={l.href} href={l.href} className={active ? "text-ink" : "text-ink-2 hover:text-ink"}>
              {l.label}
            </Link>
          );
        })}
      </nav>
      {health?.kill_switch && <KillSwitchBand />}
    </header>
  );
}
