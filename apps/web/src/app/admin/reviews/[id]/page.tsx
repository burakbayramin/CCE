import Link from 'next/link';
import { notFound } from 'next/navigation';
import { requireIdentity } from '../../../../lib/identity';
import { reviewApi, type ReviewDetail, type StoredDefinition } from '../../../../lib/contributions';
import { ReviewPanel } from '../../../../features/character-submissions/review-panel';
import { DefinitionPanel } from '../../../../features/character-submissions/definition-panel';
import { apiErrorMessage } from '../../../../lib/api-errors';

export const dynamic = 'force-dynamic';
export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  await requireIdentity(true);
  const { id } = await params;
  const result = await reviewApi<ReviewDetail>(`/${encodeURIComponent(id)}`);
  if (result.status === 404) notFound();
  const compiled = result.data?.submission.status === 'APPROVED'
    ? await reviewApi<StoredDefinition | null>(`/${encodeURIComponent(id)}/definition`) : null;
  return <main className="mx-auto max-w-3xl px-6 py-16">
    <Link href="/admin/reviews">İnceleme listesi</Link>
    <h1 className="mt-6 text-3xl">Başvuru incelemesi</h1>
    {result.data ? <ReviewPanel key={result.data.submission.id} detail={result.data} /> : <p role="alert">{apiErrorMessage(result)}</p>}
    {result.data?.submission.status === 'APPROVED' && (compiled?.error
      ? <p role="alert">{apiErrorMessage(compiled)}</p>
      : <DefinitionPanel item={result.data.submission} definition={compiled?.data ?? null} />)}
  </main>;
}
