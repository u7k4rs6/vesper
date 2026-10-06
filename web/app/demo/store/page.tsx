import type { Metadata } from "next";
import { StoreCheckout } from "@/components/StoreCheckout";

export const metadata: Metadata = { title: "Vesper Demo Store" };

export default function StorePage() {
  const clientId = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID ?? "";
  return (
    <main className="max-w-[880px] px-4 py-10 sm:px-6">
      <h1 className="text-[22px] leading-7 font-semibold">Vesper Demo Store</h1>

      <section className="mt-10 flex items-baseline justify-between gap-4 border-b border-line pb-4">
        <div>
          <h2 className="text-base leading-6 font-semibold">Linen Throw</h2>
          <p className="text-[13px] leading-5 text-ink-2">Hand-woven, 130 × 170 cm.</p>
        </div>
        <p className="font-semibold">$89.00</p>
      </section>

      {clientId ? (
        <StoreCheckout clientId={clientId} />
      ) : (
        <p className="mt-8 text-refused">NEXT_PUBLIC_PAYPAL_CLIENT_ID is not set in web/.env.local.</p>
      )}

      <p className="mt-10 text-[13px] leading-5 text-ink-2">Pay with the sandbox buyer from the README.</p>
    </main>
  );
}
