import Link from 'next/link';
import { Card, Page } from '../components/ui';

export default function NotFound() {
  return (
    <Page width="narrow">
      <Card className="px-6 py-12 text-center">
        <p className="font-mono text-xs tracking-[0.2em] text-ink-400">404</p>
        <h1 className="mt-3 font-display text-2xl font-semibold text-ink-900">
          Sayfa bulunamadı
        </h1>
        <p className="mx-auto mt-2.5 max-w-sm text-sm leading-relaxed text-ink-600">
          Aradığın sayfa silinmiş olabilir veya bu kayda erişim iznin olmayabilir.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2.5">
          <Link href="/" className="cce-btn cce-btn-secondary no-underline">
            Ana sayfa
          </Link>
          <Link href="/contributor/drafts" className="cce-btn cce-btn-primary no-underline">
            Taslaklarım
          </Link>
        </div>
      </Card>
    </Page>
  );
}
