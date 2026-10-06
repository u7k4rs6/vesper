import { TopBar } from "@/components/TopBar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopBar />
      <main className="max-w-[880px] px-4 py-8 sm:px-6">{children}</main>
    </>
  );
}
