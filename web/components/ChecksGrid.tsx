import type { Verdict } from "@/lib/types";

const SWATCH = { defer: "bg-deferred", approve: "bg-deferred", refuse: "bg-refused", allow: "bg-line" } as const;

/** Rules that stepped in, each with its reason; the ones that allowed it fold into one expandable list, reasons included. */
export function ChecksGrid({ verdicts }: { verdicts: Verdict[] }) {
  const stepped = verdicts.filter((v) => v.verdict !== "allow");
  const passed = verdicts.filter((v) => v.verdict === "allow");
  return (
    <div>
      {stepped.map((v) => (
        <p key={v.rule_id} className="flex items-baseline gap-2.5 py-0.5">
          <span aria-hidden className={`size-2 shrink-0 translate-y-[-1px] ${SWATCH[v.verdict]}`} />
          <span>
            <span className="font-medium">{v.name}</span>
            <span className="text-ink-2"> · {v.reason}</span>
          </span>
        </p>
      ))}
      <details className="group mt-1">
        <summary className="label cursor-pointer list-none hover:text-ink">
          {stepped.length ? `${passed.length} other rules allowed it` : `All ${passed.length} rules allowed it`} · see why
          <span className="ml-1.5 group-open:hidden">+</span>
          <span className="ml-1.5 hidden group-open:inline">−</span>
        </summary>
        <ol className="mt-2 space-y-1 text-[13px] leading-5">
          {passed.map((v) => (
            <li key={v.rule_id}>
              <span className="font-medium">{v.name}</span>
              <span className="text-ink-2"> · {v.reason}</span>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
