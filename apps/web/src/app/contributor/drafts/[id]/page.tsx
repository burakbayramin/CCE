import Link from 'next/link';
import { contributionApi, type Submission } from '../../../../lib/contributions';
import { ProposalForm } from '../../../../features/character-submissions/proposal-form';
export const dynamic = 'force-dynamic';
export default async function DraftDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await contributionApi<Submission>(`/${encodeURIComponent(id)}`);
  return <main className="mx-auto max-w-3xl px-6 py-16"><Link href="/contributor/drafts">Taslaklarım</Link><h1 className="mt-6 text-3xl">Karakter önerisi</h1>{result.data ? <ProposalForm key={`${result.data.id}:${result.data.version}`} item={result.data} creationKey={result.data.id} /> : <p role="alert" className="mt-6">{result.error}</p>}</main>;
}
