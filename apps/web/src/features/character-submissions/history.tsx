import type { Proposal, SubmissionHistory } from '../../lib/contributions';
import { PrivateAvatar } from '../../components/private-avatar';

export function ProposalHistory({ history }: { history: SubmissionHistory }) {
  return <section className="mt-10 border-t pt-6">
    <h2 className="text-xl font-semibold">Geri bildirim ve revizyon geçmişi</h2>
    {history.feedback.map(item => <article key={item.id} className="my-4 rounded border p-4">
      <p className="font-semibold">{item.decision}</p>
      <p className="whitespace-pre-wrap">{item.reason}</p>
      <p className="mt-2 text-xs">Revizyon: {item.revision_id}</p>
    </article>)}
    {!history.feedback.length && <p className="mt-3">Henüz karar geri bildirimi yok.</p>}
    {history.revisions.map((revision, index) => {
      const previous = history.revisions[index - 1]?.definition;
      const keys = Object.keys(revision.definition) as (keyof Proposal)[];
      const changed = keys.filter(key => !previous || JSON.stringify(previous[key]) !== JSON.stringify(revision.definition[key]));
      return <details key={revision.id} className="mt-4 rounded border p-4">
        <summary>Revizyon {revision.revision_number} — {revision.definition.name}</summary>
        <p className="my-2 text-xs">{revision.id} · {new Date(revision.created_at).toISOString()}</p>
        <PrivateAvatar id={revision.avatar_id} />
        {index > 0 && history.revisions[index - 1].avatar_id !== revision.avatar_id && <p>Avatar önceki gönderime göre değişti.</p>}
        <p>{previous ? 'Önceki gönderime göre değişen alanlar' : 'İlk gönderimin alanları'}</p>
        {changed.map(key => <div key={key} className="mt-3 border-t pt-2">
          <h3 className="font-semibold">{key}</h3>
          {previous && <pre className="whitespace-pre-wrap break-words text-sm">Önce: {JSON.stringify(previous[key], null, 2)}</pre>}
          <pre className="whitespace-pre-wrap break-words text-sm">Sonra: {JSON.stringify(revision.definition[key], null, 2)}</pre>
        </div>)}
        {!changed.length && <p>İçerik değişmemiş.</p>}
      </details>;
    })}
  </section>;
}
