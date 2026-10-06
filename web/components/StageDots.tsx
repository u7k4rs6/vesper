import type { Dot, Stage } from "@/lib/types";
import { stageToDots } from "@/lib/types";

const DOT_STYLE: Record<Dot, string> = {
  empty: "border border-line bg-surface",
  filled: "border border-ink bg-ink",
  half: "border border-deferred",
  recovered: "border border-recovered bg-recovered",
  refused: "",
  closed: "",
};

export function StageDots({ stage, size = "row", subLabel }: { stage: Stage; size?: "row" | "header"; subLabel?: string }) {
  const view = stageToDots(stage);
  const d = size === "row" ? 8 : 10;
  const label = subLabel ? `${view.label}, ${subLabel}` : view.label;
  return (
    <span
      role="img"
      aria-label={label}
      className="inline-flex items-center"
      style={{ height: size === "row" ? 16 : 20 }}
    >
      {view.dots.map((dot, i) => (
        <span key={i} className="inline-flex items-center">
          {i > 0 && <span aria-hidden className="h-px w-[6px] bg-line" />}
          {dot === "refused" || dot === "closed" ? (
            <span
              aria-hidden
              className={`flex items-center justify-center font-semibold ${dot === "refused" ? "text-refused" : "text-ink-2"}`}
              style={{ width: d, height: d, fontSize: d + 4, lineHeight: 1 }}
            >
              ×
            </span>
          ) : (
            <span
              aria-hidden
              className={`dot rounded-full ${DOT_STYLE[dot]}`}
              style={{
                width: d,
                height: d,
                background: dot === "half" ? "linear-gradient(90deg, var(--deferred) 50%, transparent 50%)" : undefined,
              }}
            />
          )}
        </span>
      ))}
    </span>
  );
}
