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
  const secondary = [SOURCE_WORDS[row.source], relativeTime(row.created_at)];
  if (row.reason_short) secondary.push(row.reason_short);
  return (
    <div className={`flex flex-wrap items-center gap-x-4 border-b border-line bg-surface hover:bg-paper/60 ${flash ? "row-flash" : ""}`}>
      <Link href={`/cases/${row.id}`} className="grid min-w-0 flex-1 grid-cols-[86px_1fr] items-center gap-x-4 px-4 py-3.5 sm:grid-cols-[86px_1fr_110px_210px] sm:px-5">
        <StageDots stage={row.stage} />
        <span className="min-w-0">
          <span className="block truncate font-medium">
            {row.first_name} · {row.place}
          </span>
          <span className="block truncate text-[13px] leading-5 text-ink-2">{secondary.join(" · ")}</span>
        </span>
        <span className="col-start-2 font-mono sm:col-start-auto sm:text-right">{money(row.amount, row.currency)}</span>
        <span className={`label col-start-2 sm:col-start-auto ${TONE_CLASS[view.tone]}`}>{view.label}</span>
      </Link>
      {actions && <div className="flex shrink-0 items-center gap-2 px-4 pb-3 sm:py-3">{actions}</div>}
    </div>
  );
}
