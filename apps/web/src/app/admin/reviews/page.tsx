import Link from 'next/link';
import { requireIdentity } from '../../../lib/identity';
import { reviewApi, type Submission } from '../../../lib/contributions';
import { apiErrorMessage } from '../../../lib/api-errors';
import { Card, EmptyState, Notice, Page, PageHeader } from '../../../components/ui';
import { StatusPill } from '../../../components/status-pill';

export const dynamic = 'force-dynamic';

const queueHint: Record<string, string> = {
  SUBMITTED: 'Incelenmeyi bekliyor.',
  UNDER_REVIEW: 'İnceleniyor veya moderasyon taraması sürüyor.',
  CHANGES_REQUESTED: 'Katkıcıdan yeni revizyon bekleniyor.',
  APPROVED: 'Onaylandı; aktivasyon henüz açık değil.',
  REJECTED: 'Reddedildi.',
  DRAFT: 'Henüz gönderilmedi.',
  WITHDRAWN: 'Katkıcı tarafından geri çekildi.',
};

export default async function ReviewQueue() {
  await requireIdentity(true);
  const result = await reviewApi<Submission[]>();
  const items = result.data ?? [];

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link href="/admin" className="text-accent-700">
            Owner portalı
          </Link>
        }
        title="Başvuru incelemeleri"
        description="Son güncellenen 100 başvuru. Onay yalnız incelediğin revizyona aittir; aktivasyon henüz açık değil."
      />

      {result.error && (
        <Notice tone="danger" role="alert" title="Kuyruk yüklenemedi">
          {apiErrorMessage(result)}
        </Notice>
      )}

      {items.length === 0 && !result.error ? (
        <div className="mt-2">
          <EmptyState
            title="İncelenecek başvuru yok"
            description="Katkıcılar bir karakter önerisini gönderdiğinde burada görünecek. Her karar gerekçeli olmalı."
          />
        </div>
      ) : (
        <ul className="mt-2 space-y-3">
          {items.map(item => (
            <li key={item.id}>
              <Card className="px-5 py-4 transition-shadow hover:shadow-raised">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/admin/reviews/${item.id}`}
                      className="font-display text-lg font-semibold text-ink-900 no-underline hover:text-accent-700"
                    >
                      {item.definition.name || 'İsimsiz'}
                    </Link>
                    <p className="mt-1 text-sm text-ink-600">
                      {queueHint[item.status] ?? ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    <StatusPill status={item.status} />
                    <span className="font-mono text-xs text-ink-500">Sürüm {item.version}</span>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
