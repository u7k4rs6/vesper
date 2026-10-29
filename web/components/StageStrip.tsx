import { ACTOR_LABEL, STEPS, type StepState } from "@/lib/story";

const BAR: Record<StepState, string> = {
  todo: "bg-line",
  active: "bg-ink pulse",
  done: "bg-ink",
  waiting: "bg-deferred",
  stopped: "bg-refused",
  won: "bg-recovered",
};

/** The five steps, large. With `states` it tracks a live case; without, it explains the loop. */
export function StageStrip({ states, current }: { states?: StepState[]; current?: number }) {
  return (
    <ol className="grid grid-cols-5 border-y border-line">
      {STEPS.map((s, i) => {
        const state = states?.[i] ?? "todo";
        const on = current === i;
        return (
          <li key={s.key} className={`min-w-0 py-3 pr-1 sm:pr-2 ${i > 0 ? "pl-1.5 sm:pl-4" : ""}`}>
            <div className="flex items-baseline gap-2">
              <span className="hidden font-mono text-[11px] text-ink-3 sm:inline">{s.n}</span>
              <span className={`label !text-[10px] sm:!text-[11px] ${on ? "text-ink" : ""}`}>{s.short}</span>
            </div>
            <div className={`mt-2 h-[3px] ${states ? BAR[state] : "bg-ink"}`} />
            <p className="mt-2 hidden text-[13px] leading-5 text-ink-2 md:block">{s.caption}</p>
            <p className="mt-1 hidden md:block">
              <ActorTag actor={s.actor} />
            </p>
          </li>
        );
      })}
    </ol>
  );
}

const ACTOR_SWATCH = { paypal: "bg-paypal", model: "bg-model", code: "bg-ink", customer: "bg-recovered" } as const;

export function ActorTag({ actor }: { actor: keyof typeof ACTOR_SWATCH }) {
  return (
    <span className="label inline-flex items-center gap-1.5">
      <span aria-hidden className={`inline-block size-[7px] ${ACTOR_SWATCH[actor]}`} />
      {ACTOR_LABEL[actor]}
    </span>
  );
}
