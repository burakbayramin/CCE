import { randomUUID } from 'node:crypto';
import Link from 'next/link';
import { requireIdentity } from '../../../../lib/identity';
import { ProposalForm } from '../../../../features/character-submissions/proposal-form';
export const dynamic = 'force-dynamic';
export default async function NewDraft() {
  const identity = await requireIdentity();
  return <main className="mx-auto max-w-3xl px-6 py-16"><Link href="/contributor/drafts">Taslaklarım</Link><h1 className="mt-6 text-3xl">Yeni karakter taslağı</h1>{identity ? <ProposalForm creationKey={randomUUID()} /> : <p role="alert">Kimlik doğrulanamadı. İşlem yapılamaz.</p>}</main>;
}
