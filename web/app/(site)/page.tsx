import Link from "next/link";
import { Suspense } from "react";
import { DemoLive } from "@/components/DemoLive";
import { StageStrip } from "@/components/StageStrip";

const GUARANTEES = [
  { n: "2", text: "model calls per case, then the model is out of the loop" },
  { n: "0", text: "amounts written by the model; its output has no number fields" },
  { n: "8", text: "rules in plain code run before any customer hears anything" },
  { n: "0", text: "charges, ever. The only thing Vesper sends is an invoice" },
];

// Server-rendered, so the headline and guarantees are in the HTML before any JavaScript runs.
export default function DemoPage() {
  return (
    <>
      <section className="pt-14 pb-10 sm:pt-20">
        <p className="label">A PayPal recovery agent with guardrails</p>
        <h1 className="display mt-4 text-[44px] sm:text-[72px] lg:text-[84px]">
          A payment failed.
          <br />
          Watch Vesper win it back.
        </h1>
        <p className="mt-6 max-w-[620px] text-lg leading-7 text-ink-2">
          Vesper reads why a PayPal payment failed, proposes one safe next step, and checks it against eight rules
          in code before the customer hears anything. The model proposes; code decides. Nobody is ever charged.
        </p>
      </section>

      <Suspense fallback={<DemoLiveFallback />}>
        <DemoLive />
      </Suspense>

      <section className="pt-16">
        <h2 className="label mb-4 text-ink">What the code guarantees</h2>
        <div className="grid border-t border-l border-line bg-surface sm:grid-cols-2 lg:grid-cols-4">
          {GUARANTEES.map((g) => (
            <div key={g.text} className="border-r border-b border-line px-5 py-5">
              <p className="display text-[56px]">{g.n}</p>
              <p className="mt-3 text-ink-2">{g.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[13px] leading-5 text-ink-2">
          Each is enforced by a test that runs on every push.{" "}
          <Link href="/rules" className="underline hover:text-ink">
            Read the eight rules
          </Link>{" "}
          or{" "}
          <Link href="/floor" className="underline hover:text-ink">
            see every case on the Floor
          </Link>
          .
        </p>
      </section>
    </>
  );
}

function DemoLiveFallback() {
  return (
    <>
      <StageStrip />
      <p className="label pulse pt-12">Loading the live demo…</p>
    </>
  );
}
