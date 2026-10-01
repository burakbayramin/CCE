'use client';

import { useEffect } from 'react';

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Server error messages are intentionally redacted; the digest is the
    // correlation key, without exposing the underlying exception to visitors.
    console.error('CCE page error', { digest: error.digest ?? null });
  }, [error.digest]);
  return <main className="mx-auto max-w-2xl px-6 py-20" role="alert">
    <h1 className="text-2xl font-semibold">Servis geçici olarak kullanılamıyor</h1>
    <p className="mt-4">İşlem yapılmadı. Bağlantı veya sunucu düzeldikten sonra yeniden dene.</p>
    <button className="mt-6 rounded border px-4 py-2" onClick={reset}>Yeniden dene</button>
  </main>;
}
