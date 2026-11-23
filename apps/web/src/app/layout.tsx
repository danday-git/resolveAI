import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible_Mono, Host_Grotesk } from "next/font/google";
import { AppShell } from "@/components/Nav";
import "./globals.css";

const host = Host_Grotesk({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-host", display: "swap" });
const atkinson = Atkinson_Hyperlegible_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-atkinson", display: "swap", adjustFontFallback: false });

export const metadata: Metadata = {
  title: "ResolveAI",
  description: "Evidence-grounded incident investigation: cited answers, structured analysis and human-confirmed root cause reports.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, colorScheme: "dark light" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${host.variable} ${atkinson.variable}`} suppressHydrationWarning>
      <head>
        {/* Applies the stored theme before first paint, so the light theme never flashes dark. */}
        <script dangerouslySetInnerHTML={{ __html: `try{if(localStorage.getItem("theme")==="paper")document.documentElement.dataset.theme="paper"}catch(e){}` }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
