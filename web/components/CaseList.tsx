"use client";

import { useEffect, useRef, useState } from "react";
import { CaseRow } from "@/components/CaseRow";
import type { CaseRow as Row, Stage } from "@/lib/types";

/** Flashes rows whose stage changed since the last poll; rows that arrive after the first load expand in. */
export function CaseList({ rows, actions }: { rows: Row[]; actions?: (row: Row) => React.ReactNode }) {
  const seen = useRef<Map<string, Stage> | null>(null);
  const [flashing, setFlashing] = useState<Set<string>>(new Set());
  const [entering, setEntering] = useState<Set<string>>(new Set());

  useEffect(() => {
    const prev = seen.current;
    const next = new Map(rows.map((r) => [r.id, r.stage] as const));
    seen.current = next;
    if (prev === null) return; // first load: nothing animates
    const changed = new Set(rows.filter((r) => prev.has(r.id) && prev.get(r.id) !== r.stage).map((r) => r.id));
    const added = new Set(rows.filter((r) => !prev.has(r.id)).map((r) => r.id));
    if (changed.size) setFlashing(changed);
    if (added.size) setEntering(added);
    if (!changed.size && !added.size) return;
    const t = setTimeout(() => {
      setFlashing(new Set());
      setEntering(new Set());
    }, 650);
    return () => clearTimeout(t);
  }, [rows]);

  return (
    <div className="border-t border-line">
      {rows.map((row) => (
        <div key={row.id} className={entering.has(row.id) ? "row-enter" : undefined}>
          <div>
            <CaseRow row={row} flash={flashing.has(row.id)} actions={actions?.(row)} />
          </div>
        </div>
      ))}
    </div>
  );
}
