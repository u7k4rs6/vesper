export function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface px-4 py-4 sm:px-5">
      <h2 className="mb-2 text-base leading-6 font-semibold">{title}</h2>
      {children}
    </section>
  );
}
