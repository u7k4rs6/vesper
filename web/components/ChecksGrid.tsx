import type { Verdict } from "@/lib/types";

const SWATCH = { defer: "bg-deferred", approve: "bg-deferred", refuse: "bg-refused", allow: "bg-line" } as const;

/** Rules that stepped in, one line each; the ones that passed fold into a single expandable line. */
export function ChecksGrid({ verdicts }: { verdicts: Verdict[] }) {
  const stepped = verdicts.filter((v) => v.verdict !== "allow");
  const passed = verdicts.length - stepped.length;
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
          {stepped.length ? `${passed} other rules passed` : `All ${passed} rules passed`}
          <span className="ml-1.5 group-open:hidden">+</span>
          <span className="ml-1.5 hidden group-open:inline">−</span>
        </summary>
        <ol className="mt-2 grid gap-x-6 gap-y-1 text-[13px] leading-5 sm:grid-cols-2">
          {verdicts.map((v) => (
            <li key={v.rule_id} className="flex items-baseline gap-2">
              <span aria-hidden className={`size-1.5 shrink-0 ${SWATCH[v.verdict]}`} />
              <span className={v.verdict === "allow" ? "text-ink-2" : "font-medium"}>{v.name}</span>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
