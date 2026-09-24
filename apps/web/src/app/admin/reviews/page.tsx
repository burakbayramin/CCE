import Link from 'next/link';
import { requireIdentity } from '../../../lib/identity';
import { reviewApi, type Submission } from '../../../lib/contributions';

export const dynamic = 'force-dynamic';
export default async function ReviewQueue() {
  const identity = await requireIdentity(true);
  if (!identity) return <main role="alert">Owner yetkisi doğrulanamadı.</main>;
  const result = await reviewApi<Submission[]>();
  return <main className="mx-auto max-w-3xl px-6 py-16">
    <Link href="/admin">Owner portalı</Link>
    <h1 className="mt-6 text-3xl">Başvuru incelemeleri</h1>
    <p className="mt-4">Son güncellenen 100 başvuru. Onay, yalnız incelenen revizyona aittir; aktivasyon henüz açık değil.</p>
    {result.error && <p role="alert" className="mt-6">{result.error}</p>}
    {result.data?.map(item => <article key={item.id} className="mt-5 rounded border p-4">
      <Link href={`/admin/reviews/${item.id}`} className="text-teal-700">{item.definition.name || 'İsimsiz'}</Link>
      <p>{item.status} · Sürüm {item.version}</p>
    </article>)}
    {result.data?.length === 0 && <p className="mt-6">Henüz gönderilmiş başvuru yok.</p>}
  </main>;
}
