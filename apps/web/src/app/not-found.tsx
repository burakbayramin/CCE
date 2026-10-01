import Link from 'next/link';

export default function NotFound() {
  return <main className="mx-auto max-w-2xl px-6 py-20">
    <h1 className="text-2xl font-semibold">Sayfa bulunamadı</h1>
    <p className="mt-4">Aradığın sayfa silinmiş olabilir veya bu kayda erişim iznin olmayabilir.</p>
    <Link href="/" className="mt-6 inline-block text-teal-700">Ana sayfaya dön</Link>
  </main>;
}
