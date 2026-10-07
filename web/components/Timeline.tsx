import { clock } from "@/lib/format";
import type { CaseDetail } from "@/lib/types";

export function Timeline({ events, timeZone }: { events: CaseDetail["events"]; timeZone: string }) {
  return (
    <ol className="border-t border-line">
      {events.map((e, i) => (
        <li key={i} className="grid grid-cols-[56px_1fr] gap-x-3 border-b border-line py-2">
          <time dateTime={e.at} className="font-mono text-[13px] text-ink-2">
            {clock(e.at, timeZone)}
          </time>
          <span>{e.text}</span>
        </li>
      ))}
    </ol>
  );
}
