import Link from 'next/link';
import { notFound } from 'next/navigation';
import { requireIdentity } from '../../../../lib/identity';
import {
  reviewApi,
  type ReviewDetail,
  type StoredDefinition,
  type ActivatedCharacter,
  type CharacterCapacity,
  type DefinitionChange,
  type LifecycleChange,
} from '../../../../lib/contributions';
import { apiErrorMessage } from '../../../../lib/api-errors';
import { ReviewPanel } from '../../../../features/character-submissions/review-panel';
import { DefinitionPanel } from '../../../../features/character-submissions/definition-panel';
import { DefinitionChangePanel } from '../../../../features/character-submissions/definition-change-panel';
import { ActivationPanel } from '../../../../features/character-submissions/activation-panel';
import { Notice, Page, PageHeader } from '../../../../components/ui';

export const dynamic = 'force-dynamic';

export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  await requireIdentity(true);
  const { id } = await params;
  const result = await reviewApi<ReviewDetail>(`/${encodeURIComponent(id)}`);
  if (result.status === 404) notFound();
  const approved = result.data?.submission.status === 'APPROVED';
  const [compiled, activated, capacity, lifecycle, changes] = approved
    ? await Promise.all([
        reviewApi<StoredDefinition | null>(`/${encodeURIComponent(id)}/definition`),
        reviewApi<ActivatedCharacter | null>(`/${encodeURIComponent(id)}/activation`),
        reviewApi<CharacterCapacity>('/capacity'),
        reviewApi<LifecycleChange[]>(`/${encodeURIComponent(id)}/lifecycle`),
        reviewApi<DefinitionChange[]>(`/${encodeURIComponent(id)}/definition-changes`),
      ])
    : [null, null, null, null, null];

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
            <DefinitionChangePanel
              item={result.data.submission}
              current={compiled.data}
              activated={activated?.data ?? null}
              changes={changes?.data ?? []}
              loadError={changes?.error ? apiErrorMessage(changes) : ''}
              fixtureCommandsEnabled={
                process.env.CCE_ENVIRONMENT === 'test' && compiled.data.artifact.source.is_fixture
              }
            />
          )}
          {approved && compiled?.data && (
            <ActivationPanel
              key={`${activated?.data?.id ?? 'pending'}:${activated?.data?.lifecycle_version ?? 0}`}
              item={result.data.submission}
              definition={compiled.data}
              activated={activated?.data ?? null}
              capacity={capacity?.data ?? null}
              history={lifecycle?.data ?? []}
              loadError={activated?.error ? apiErrorMessage(activated) : capacity?.error ? apiErrorMessage(capacity) : lifecycle?.error ? apiErrorMessage(lifecycle) : ''}
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
