import { SiteFooter, SiteHeader } from "@/components/SiteHeader";

export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-[1120px] px-4 pb-20 sm:px-6">{children}</main>
      <SiteFooter />
    </>
  );
}
