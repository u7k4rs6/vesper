import type { Verdict, VerdictKind } from "@/lib/types";

const MARK: Record<VerdictKind, { glyph: string; className: string; words: string }> = {
  allow: { glyph: "✓", className: "text-ink-2", words: "Allowed" },
  defer: { glyph: "◔", className: "text-deferred", words: "Deferred" },
  approve: { glyph: "○", className: "text-deferred", words: "Needs approval" },
  refuse: { glyph: "×", className: "text-refused", words: "Refused" },
};

export function ChecksTable({ verdicts }: { verdicts: Verdict[] | null }) {
  if (!verdicts) return <p className="text-ink-2">Not checked yet.</p>;
  return (
    <ul>
      {verdicts.map((v) => {
        const mark = MARK[v.verdict];
        return (
          <li key={v.rule_id} className="grid grid-cols-[1.25rem_1fr] gap-x-2 py-1 sm:grid-cols-[1.25rem_15rem_1fr]">
            <span className={mark.className} aria-label={mark.words}>
              {mark.glyph}
            </span>
            <span>{v.name}</span>
            <span className="col-start-2 text-ink-2 sm:col-start-3">{v.reason}</span>
          </li>
        );
      })}
    </ul>
  );
}
