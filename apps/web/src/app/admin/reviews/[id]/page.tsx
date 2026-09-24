import Link from 'next/link';
import { requireIdentity } from '../../../../lib/identity';
import { reviewApi, type ReviewDetail } from '../../../../lib/contributions';
import { ReviewPanel } from '../../../../features/character-submissions/review-panel';

export const dynamic = 'force-dynamic';
export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const identity = await requireIdentity(true);
  if (!identity) return <main role="alert">Owner yetkisi doğrulanamadı.</main>;
  const { id } = await params;
  const result = await reviewApi<ReviewDetail>(`/${encodeURIComponent(id)}`);
  return <main className="mx-auto max-w-3xl px-6 py-16">
    <Link href="/admin/reviews">İnceleme listesi</Link>
    <h1 className="mt-6 text-3xl">Başvuru incelemesi</h1>
    {result.data ? <ReviewPanel key={result.data.submission.id} detail={result.data} /> : <p role="alert">{result.error}</p>}
  </main>;
}
