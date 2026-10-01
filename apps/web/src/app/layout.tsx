import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, Newsreader } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = Inter({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  variable: "--font-sans",
});

const display = Newsreader({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: {
    default: "Cognitive Character Engine",
    template: "%s · CCE",
  },
  description:
    "Destekçiler karakter tasarlar, World Owner onaylar, karakterler kalıcı bir dünyada birbirleriyle etkileşir.",
  robots: { index: false, follow: false },
};

function SiteHeader() {
  return (
    <header className="cce-no-print border-b border-line bg-surface/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-3.5">
        <Link
          href="/"
          className="flex items-baseline gap-2.5 rounded text-ink-900 no-underline"
        >
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-md bg-accent-700 font-display text-sm font-semibold text-white"
          >
            C
          </span>
          <span className="font-display text-[1.0625rem] font-semibold tracking-tight">
            Cognitive Character Engine
          </span>
        </Link>
        <p className="hidden text-xs text-ink-500 sm:block">
          Kalıcı karakterler için ortak dünya motoru
        </p>
      </div>
    </header>
  );
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="tr" className={`${sans.variable} ${display.variable}`}>
      <body className="min-h-screen antialiased">
        <a
          href="#main"
          className="cce-no-print sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-accent-700 focus:px-4 focus:py-2 focus:text-sm focus:text-white"
        >
          İçeriğe geç
        </a>
        <SiteHeader />
        {children}
        <footer className="cce-no-print mt-16 border-t border-line">
          <div className="mx-auto max-w-5xl px-6 py-6 text-xs leading-relaxed text-ink-500">
            <p>
              Bu arayüz erken aşamadadır. Ekranda görünen moderasyon sonuçları
              fixture ise gerçek içerik güvenliği taraması değildir.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
