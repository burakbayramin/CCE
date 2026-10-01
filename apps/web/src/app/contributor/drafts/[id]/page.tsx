import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  contributionApi,
  type Submission,
  type SubmissionHistory,
} from '../../../../lib/contributions';
import { apiErrorMessage } from '../../../../lib/api-errors';
import { ProposalHistory } from '../../../../features/character-submissions/history';
import { ProposalForm } from '../../../../features/character-submissions/proposal-form';
import { Notice, Page, PageHeader } from '../../../../components/ui';

export const dynamic = 'force-dynamic';

export default async function DraftDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await contributionApi<Submission>(`/${encodeURIComponent(id)}`);
  if (result.status === 404) notFound();
  const history = result.data
    ? await contributionApi<SubmissionHistory>(`/${encodeURIComponent(id)}/history`)
    : null;

  return (
    <Page width="wide">
      <PageHeader
        eyebrow={
          <Link href="/contributor/drafts" className="text-accent-700">
            Taslaklarım
          </Link>
        }
        title="Karakter önerisi"
        description="Metni ve avatarı düzenle, kaydet ve incelemeye gönder. Gönderimden sonra bu revizyon kilitlenir."
      />

      {result.data ? (
        <div className="space-y-6">
          <ProposalForm
            key={`${result.data.id}:${result.data.version}`}
            item={result.data}
            creationKey={result.data.id}
          />
          {history?.data && <ProposalHistory history={history.data} />}
          {history?.error && (
            <Notice tone="warning" title="Geçmiş yüklenemedi">
              {apiErrorMessage(history)}
            </Notice>
          )}
        </div>
      ) : (
        <Notice tone="danger" role="alert" title="Öneri açılamadı">
          {apiErrorMessage(result)}
        </Notice>
      )}
    </Page>
  );
}
