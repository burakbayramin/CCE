'use client';

import { useEffect } from 'react';
import { Card, Mono, Page } from '../components/ui';

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // The digest is the only safe handle on a server-side failure; the message
    // itself can contain request data, so it is never rendered or logged here.
    console.error('cce:render-error', error.digest ?? 'no-digest');
  }, [error]);

  return (
    <Page width="narrow">
      <Card className="px-6 py-10 text-center">
        <div
          aria-hidden
          className="mx-auto grid size-12 place-items-center rounded-full bg-danger-50 text-danger-700"
        >
          <svg viewBox="0 0 24 24" fill="none" className="size-6" stroke="currentColor" strokeWidth="1.75">
            <path d="M12 8v5" strokeLinecap="round" />
            <circle cx="12" cy="16.5" r="0.75" fill="currentColor" />
            <path d="M10.3 3.9 2.6 17.4A2 2 0 0 0 4.3 20.4h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" strokeLinejoin="round" />
          </svg>
        </div>
        <h1 className="mt-5 font-display text-2xl font-semibold text-ink-900">
          Servis geçici olarak kullanılamıyor
        </h1>
        <p className="mx-auto mt-2.5 max-w-sm text-sm leading-relaxed text-ink-600">
          İşlem yapılmadı. Bağlantı veya sunucu düzeldiğinde aynı işlemi tekrar
          deneyebilirsin.
        </p>
        {error.digest && (
          <p className="mt-4 flex items-center justify-center gap-2 text-xs text-ink-500">
            Hata kodu <Mono>{error.digest}</Mono>
          </p>
        )}
        <button onClick={reset} className="cce-btn cce-btn-primary mt-6">
          Yeniden dene
        </button>
      </Card>
    </Page>
  );
}
