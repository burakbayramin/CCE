import Link from 'next/link';
import { requireIdentity } from '../../../lib/identity';
import { contributionApi, type Submission } from '../../../lib/contributions';
import { apiErrorMessage } from '../../../lib/api-errors';
import { Card, EmptyState, Notice, Page, PageHeader } from '../../../components/ui';
import { StatusPill } from '../../../components/status-pill';

export const dynamic = 'force-dynamic';

export default async function Drafts() {
  await requireIdentity();
  const result = await contributionApi<Submission[]>();
  const drafts = result.data ?? [];

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link href="/contributor" className="text-accent-700">
            Katkıcı portalı
          </Link>
        }
        title="Taslaklarım ve başvurularım"
        description="Taslak yaz, gönder, geri çek. Gönderilen revizyon değiştirilemez; Owner değişiklik istediğinde yeni bir revizyon açarsın."
        actions={
          <Link href="/contributor/drafts/new" className="cce-btn cce-btn-primary no-underline">
            Yeni taslak
          </Link>
        }
      />

      {result.error && (
        <Notice tone="danger" role="alert" title="Listelenemedi">
          {apiErrorMessage(result)}
        </Notice>
      )}

      {drafts.length === 0 && !result.error ? (
        <div className="mt-2">
          <EmptyState
            title="Henüz taslağın yok"
            description="İlk karakter önerini yaz. Metni kaydedebilir, avatar yükleyebilir ve hazır olduğunda incelemeye gönderebilirsin."
          >
            <Link href="/contributor/drafts/new" className="cce-btn cce-btn-primary no-underline">
              Yeni taslak
            </Link>
          </EmptyState>
        </div>
      ) : (
        <ul className="mt-2 space-y-3">
          {drafts.map(item => (
            <li key={item.id}>
              <Card className="px-5 py-4 transition-shadow hover:shadow-raised">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/contributor/drafts/${item.id}`}
                      className="font-display text-lg font-semibold text-ink-900 no-underline hover:text-accent-700"
                    >
                      {item.definition.name || 'İsimsiz taslak'}
                    </Link>
                    <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-ink-600">
                      {item.definition.introduction || 'Açıklama henüz yazılmadı.'}
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
