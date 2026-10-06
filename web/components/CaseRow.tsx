import Link from "next/link";
import { StageDots } from "@/components/StageDots";
import { money, relativeTime } from "@/lib/format";
import type { CaseRow as Row, Tone } from "@/lib/types";
import { SOURCE_WORDS, stageToDots } from "@/lib/types";

export const TONE_CLASS: Record<Tone, string> = {
  ink: "text-ink",
  deferred: "text-deferred",
  recovered: "text-recovered",
  refused: "text-refused",
  muted: "text-ink-2",
};

export function CaseRow({ row, flash, actions }: { row: Row; flash?: boolean; actions?: React.ReactNode }) {
  const view = stageToDots(row.stage);
  // Fixed columns line up amounts and statuses on the Floor; rows with buttons need the room for the name.
  const amountCol = actions ? "" : "sm:w-24 sm:text-right";
  const statusCol = actions ? "" : "sm:w-52";
  const secondary = [SOURCE_WORDS[row.source], relativeTime(row.created_at)];
  if (row.reason_short) secondary.push(row.reason_short);
  return (
    <div className={`flex items-start gap-4 border-b border-line bg-surface ${flash ? "row-flash" : ""}`}>
      <Link href={`/cases/${row.id}`} className="flex min-w-0 flex-1 gap-4 px-4 py-3">
        <span className="pt-1">
          <StageDots stage={row.stage} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-baseline gap-x-4">
            <span className="min-w-0 flex-1 font-medium">
              {row.first_name} · {row.place}
            </span>
            <span className="flex basis-full items-baseline gap-4 sm:basis-auto">
              <span className={amountCol}>{money(row.amount, row.currency)}</span>
              <span className={`${statusCol} ${TONE_CLASS[view.tone]}`}>{view.label}</span>
            </span>
          </span>
          <span className="block text-[13px] leading-5 text-ink-2">{secondary.join(" · ")}</span>
        </span>
      </Link>
      {actions && <div className="flex shrink-0 items-center gap-2 py-3 pr-4">{actions}</div>}
    </div>
  );
}
