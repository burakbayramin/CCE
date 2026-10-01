import Link from 'next/link';
import { randomUUID } from 'node:crypto';
import { requireIdentity } from '../../../../lib/identity';
import { ProposalForm } from '../../../../features/character-submissions/proposal-form';
import { Page, PageHeader } from '../../../../components/ui';

export const dynamic = 'force-dynamic';

export default async function NewDraft() {
  await requireIdentity();
  return (
    <Page width="wide">
      <PageHeader
        eyebrow={
          <Link href="/contributor/drafts" className="text-accent-700">
            Taslaklarım
          </Link>
        }
        title="Yeni karakter taslağı"
        description="Karakterin kimliğini, sesini ve iç dünyasını yaz. Kaydettiğinde bir taslak oluşur; istediğinde düzenleyip incelemeye gönderebilirsin."
      />
      <ProposalForm creationKey={randomUUID()} />
    </Page>
  );
}
