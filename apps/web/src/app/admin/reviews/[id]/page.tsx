import Link from 'next/link';
import { notFound } from 'next/navigation';
import { requireIdentity } from '../../../../lib/identity';
import {
  reviewApi,
  type ReviewDetail,
  type StoredDefinition,
  type ActivatedCharacter,
  type CharacterCapacity,
} from '../../../../lib/contributions';
import { apiErrorMessage } from '../../../../lib/api-errors';
import { ReviewPanel } from '../../../../features/character-submissions/review-panel';
import { DefinitionPanel } from '../../../../features/character-submissions/definition-panel';
import { ActivationPanel } from '../../../../features/character-submissions/activation-panel';
import { Notice, Page, PageHeader } from '../../../../components/ui';

export const dynamic = 'force-dynamic';

export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  await requireIdentity(true);
  const { id } = await params;
  const result = await reviewApi<ReviewDetail>(`/${encodeURIComponent(id)}`);
  if (result.status === 404) notFound();
  const approved = result.data?.submission.status === 'APPROVED';
  const [compiled, activated, capacity] = approved
    ? await Promise.all([
        reviewApi<StoredDefinition | null>(`/${encodeURIComponent(id)}/definition`),
        reviewApi<ActivatedCharacter | null>(`/${encodeURIComponent(id)}/activation`),
        reviewApi<CharacterCapacity>('/capacity'),
      ])
    : [null, null, null];

  return (
    <Page width="wide">
      <PageHeader
        eyebrow={
          <Link href="/admin/reviews" className="text-accent-700">
            İnceleme listesi
          </Link>
        }
        title="Başvuru incelemesi"
        description="Gönderilen revizyonu oku, moderasyon sonucunu değerlendir ve gerekçeli bir karar ver."
      />

      {result.data ? (
        <div className="space-y-6">
          <ReviewPanel key={result.data.submission.id} detail={result.data} />
          {result.data.submission.status === 'APPROVED' &&
            (compiled?.error ? (
              <Notice tone="warning" title="Tanım yüklenemedi">
                {apiErrorMessage(compiled)}
              </Notice>
            ) : (
              <DefinitionPanel
                item={result.data.submission}
                definition={compiled?.data ?? null}
              />
            ))}
          {approved && compiled?.data && (
            <ActivationPanel
              item={result.data.submission}
              definition={compiled.data}
              activated={activated?.data ?? null}
              capacity={capacity?.data ?? null}
              loadError={activated?.error ? apiErrorMessage(activated) : capacity?.error ? apiErrorMessage(capacity) : ''}
              fixtureCommandsEnabled={
                process.env.CCE_ENVIRONMENT === 'test' && compiled.data.artifact.source.is_fixture
              }
            />
          )}
        </div>
      ) : (
        <Notice tone="danger" role="alert" title="Başvuru açılamadı">
          {apiErrorMessage(result)}
        </Notice>
      )}
    </Page>
  );
}
