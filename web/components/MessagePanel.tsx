import { Panel } from "@/components/Panel";
import { languageName } from "@/lib/format";
import type { CaseDetail } from "@/lib/types";

function status(c: CaseDetail): string {
  switch (c.stage) {
    case "scheduled":
      return "goes out with the PayPal invoice at 09:00 local";
    case "awaiting_approval":
      return "goes out with the PayPal invoice once you approve it";
    case "sent":
      return "sent with the PayPal invoice";
    case "recovered":
      return "sent with the PayPal invoice and paid";
    case "held":
    case "escalated":
    case "closed":
      return "not sent";
    default:
      return "goes out with the PayPal invoice";
  }
}

export function MessagePanel({ c }: { c: CaseDetail }) {
  const m = c.message;
  if (!m) return null;
  const header = [languageName(m.language), status(c)];
  if (m.fallback_used) header.push("standard template used");
  return (
    <Panel title="Message">
      <p className="text-[13px] leading-5 text-ink-2">{header.join(" · ")}</p>
      <p className="mt-3 whitespace-pre-line" lang={m.language}>
        {m.rendered}
      </p>
      <p className="mt-3 text-[13px] leading-5 text-ink-2">
        Numbers and names were inserted by Vesper, not written by the model.
      </p>
      {m.payer_link && (
        <p className="mt-3">
          <a className="text-action underline" href={m.payer_link} target="_blank" rel="noreferrer">
            Open the PayPal invoice
          </a>
        </p>
      )}
    </Panel>
  );
}
