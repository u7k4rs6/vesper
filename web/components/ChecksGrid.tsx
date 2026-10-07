import type { Verdict, VerdictKind } from "@/lib/types";

const MARK: Record<VerdictKind, { glyph: string; className: string; words: string }> = {
  allow: { glyph: "✓", className: "text-recovered", words: "Allowed" },
  defer: { glyph: "◷", className: "text-deferred", words: "Deferred" },
  approve: { glyph: "◷", className: "text-deferred", words: "Needs approval" },
  refuse: { glyph: "×", className: "text-refused", words: "Refused" },
};

/** The eight verdicts, every one with its reason. Rules that stepped in are highlighted. */
export function ChecksGrid({ verdicts }: { verdicts: Verdict[] }) {
  return (
    <ol className="grid border-t border-l border-line sm:grid-cols-2">
      {verdicts.map((v, i) => {
        const mark = MARK[v.verdict];
        const stepped = v.verdict !== "allow";
        const tint = v.verdict === "refuse" ? "bg-refused-soft" : stepped ? "bg-deferred-soft" : "bg-surface";
        return (
          <li key={v.rule_id} className={`border-r border-b border-line px-3 py-2.5 ${tint}`}>
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[11px] text-ink-3">{String(i + 1).padStart(2, "0")}</span>
              <span className={`font-medium ${mark.className}`} aria-label={mark.words}>
                {mark.glyph}
              </span>
              <span className="font-medium">{v.name}</span>
            </div>
            <p className="pl-[44px] text-[13px] leading-5 text-ink-2">{v.reason}</p>
          </li>
        );
      })}
    </ol>
  );
}
