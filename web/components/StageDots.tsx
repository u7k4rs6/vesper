import { stageSteps, type StepState } from "@/lib/story";
import type { Stage } from "@/lib/types";
import { stageToDots } from "@/lib/types";

const CELL: Record<StepState, string> = {
  todo: "bg-line",
  active: "bg-ink pulse",
  done: "bg-ink",
  waiting: "bg-deferred",
  stopped: "bg-refused",
  won: "bg-recovered",
};

/** The five steps as five small bars: the compact form of the stage strip. */
export function StageDots({ stage, size = "row" }: { stage: Stage; size?: "row" | "header" }) {
  const states = stageSteps(stage);
  const w = size === "row" ? "w-[14px]" : "w-[22px]";
  return (
    <span role="img" aria-label={stageToDots(stage).label} className="inline-flex items-center gap-[3px]">
      {states.map((s, i) => (
        <span key={i} className={`dot h-[6px] ${w} ${CELL[s]}`} />
      ))}
    </span>
  );
}
