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
      <body className="flex min-h-dvh flex-col antialiased">
        <a
          href="#main"
          className="cce-no-print sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-accent-700 focus:px-4 focus:py-2 focus:text-sm focus:text-white"
        >
          İçeriğe geç
        </a>
        <SiteHeader />
        {/* Grows to fill the viewport so a short page still pins the footer to
            the bottom; a long page simply pushes it below the fold. */}
        <div className="flex-1">{children}</div>
        <footer className="cce-no-print mt-auto border-t border-line bg-paper-sunk/50">
          <div className="mx-auto flex max-w-5xl flex-wrap items-baseline justify-between gap-x-8 gap-y-2 px-6 py-6">
            <p className="max-w-xl text-xs leading-relaxed text-ink-500">
              Bu arayüz erken aşamadadır. Ekranda görünen moderasyon sonuçları
              fixture ise gerçek içerik güvenliği taraması değildir.
            </p>
            <p className="font-mono text-[0.6875rem] text-ink-400">M1 · M2 · M3.2</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
