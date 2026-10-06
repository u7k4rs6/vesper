import { Panel } from "@/components/Panel";
import { clock } from "@/lib/format";
import type { CaseDetail } from "@/lib/types";

export function Timeline({ events, timeZone }: { events: CaseDetail["events"]; timeZone: string }) {
  return (
    <Panel title="Timeline">
      <ol>
        {events.map((e, i) => (
          <li key={i} className="grid grid-cols-[3.25rem_1fr] gap-x-2">
            <time dateTime={e.at} className="text-ink-2">
              {clock(e.at, timeZone)}
            </time>
            <span>{e.text}</span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
