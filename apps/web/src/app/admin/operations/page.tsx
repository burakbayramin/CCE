import Link from 'next/link';
import { requireIdentity } from '../../../lib/identity';
import { operationsApi } from '../../../lib/contributions';
import { apiErrorMessage } from '../../../lib/api-errors';
import { OperationsPanel } from './operations-panel';
import { Notice, Page, PageHeader } from '../../../components/ui';
import type { components } from '../../../lib/api/generated/schema';

export const dynamic = 'force-dynamic';

export default async function OperationsPage() {
  await requireIdentity(true);
  const result = await operationsApi<components['schemas']['OperationsView']>('/snapshot');
  const snapshot = result.data ?? { workers: [], held: [] };

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link href="/admin" className="text-accent-700">
            Owner portalı
          </Link>
        }
        title="Operasyon"
        description="Worker canlılığı ve karakteri tutan rezervasyonlar. Bu ekran içerik göstermez; yalnız varlık ve durum."
        actions={
          <Link href="/admin/reviews" className="cce-btn cce-btn-secondary no-underline">
            İnceleme listesi
          </Link>
        }
      />

      {!result.data && (
        <Notice tone="danger" role="alert" title="Operasyon görünümü yüklenemedi">
          {apiErrorMessage(result)}
        </Notice>
      )}

      {result.data && <OperationsPanel snapshot={snapshot} />}
    </Page>
  );
}