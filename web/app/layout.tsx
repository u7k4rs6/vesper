import type { Metadata } from "next";
// Bundled rather than fetched by next/font at build time, which failed about one clean build in three.
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-sans/latin-700.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vesper: win back failed PayPal payments",
  description:
    "When a PayPal payment fails, Vesper diagnoses it, proposes one safe next step, and checks it against eight rules in code. It never charges anyone.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
