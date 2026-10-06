export function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <p className="text-ink-2">{label}</p>
      <p className="text-[40px] leading-[44px] font-semibold">{value}</p>
      <p className="text-[13px] leading-5 text-ink-2">{sub}</p>
    </div>
  );
}
