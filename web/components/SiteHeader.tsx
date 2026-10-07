"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import { type CasePage, fetcher } from "@/lib/api";
import type { Health } from "@/lib/types";

export const AWAITING_KEY = "/cases?stage=awaiting_approval&limit=100";
const REPO = "https://github.com/u7k4rs6/vesper";

export function SiteHeader() {
  const pathname = usePathname();
  const { data: health } = useSWR<Health>("/health", fetcher, { refreshInterval: 15000 });
  const { data: awaiting } = useSWR<CasePage>(AWAITING_KEY, fetcher, { refreshInterval: 3000 });
  const waiting = awaiting?.cases.length ?? 0;
  const links = [
    { href: "/", label: "Demo", active: pathname === "/" },
    { href: "/floor", label: "Floor", active: pathname.startsWith("/floor") || pathname.startsWith("/cases") },
    { href: "/approvals", label: "Approvals", count: waiting, active: pathname.startsWith("/approvals") },
    { href: "/rules", label: "Rules", active: pathname.startsWith("/rules") },
  ];
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-baseline gap-3">
          <span className="font-mono text-[13px] font-medium tracking-[0.2em]">VESPER</span>
          <span className="label hidden sm:inline">PayPal recovery · sandbox</span>
        </Link>
        <nav className="ml-auto flex items-center gap-5 sm:gap-6">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={l.active ? "page" : undefined}
              className={`label flex items-center gap-1.5 pb-0.5 ${
                l.active ? "border-b border-ink text-ink" : "border-b border-transparent hover:text-ink"
              }`}
            >
              {l.label}
              {l.count ? (
                <span className="bg-deferred px-1.5 text-[10px] leading-4 text-white">{l.count}</span>
              ) : null}
            </Link>
          ))}
          <a href={REPO} className="label hidden hover:text-ink sm:inline" target="_blank" rel="noreferrer">
            Source ↗
          </a>
        </nav>
      </div>
      {health?.kill_switch && (
        <div className="border-t border-line bg-deferred-soft">
          <p className="mx-auto max-w-[1120px] px-4 py-2 sm:px-6">
            Sending is paused. Cases keep moving through diagnosis and checks, but no invoices go out.
          </p>
        </div>
      )}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-6 gap-y-1 px-4 py-6 sm:px-6">
        <span className="label">PayPal sandbox only. Nobody is ever charged.</span>
        <span className="label ml-auto">
          <a className="hover:text-ink" href={REPO} target="_blank" rel="noreferrer">
            github.com/u7k4rs6/vesper
          </a>{" "}
          · MIT
        </span>
      </div>
    </footer>
  );
}
