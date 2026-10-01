import type { Proposal, SubmissionHistory } from '../../lib/contributions';
import { PrivateAvatar } from '../../components/private-avatar';
import { Card, Mono, Notice } from '../../components/ui';
import { StatusPill } from '../../components/status-pill';

const decisionTone = {
  CHANGES_REQUESTED: 'warning',
  REJECTED: 'danger',
  APPROVED: 'success',
} as const;

export function ProposalHistory({ history }: { history: SubmissionHistory }) {
  return (
    <Card className="px-5 py-5 sm:px-6">
      <h2 className="font-display text-lg font-semibold text-ink-900">
        Geri bildirim ve revizyon geçmişi
      </h2>

      {history.feedback.length === 0 ? (
        <p className="mt-3 text-sm text-ink-600">Henüz karar geri bildirimi yok.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {history.feedback.map(item => (
            <li
              key={item.id}
              className={`rounded-lg border px-4 py-3 ${
                decisionTone[item.decision as keyof typeof decisionTone] === 'danger'
                  ? 'border-danger-100 bg-danger-50'
                  : decisionTone[item.decision as keyof typeof decisionTone] === 'warning'
                    ? 'border-clay-100 bg-clay-50'
                    : 'border-success-100 bg-success-50'
              }`}
            >
              <div className="flex flex-wrap items-center gap-2.5">
                <StatusPill status={item.decision} />
              </div>
              <p className="mt-2.5 whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                {item.reason}
              </p>
              <p className="mt-2 text-xs text-ink-500">
                Revizyon: <Mono>{item.revision_id}</Mono>
              </p>
            </li>
          ))}
        </ul>
      )}

      {history.revisions.length > 0 && (
        <div className="mt-6 border-t border-line pt-5">
          <h3 className="font-display text-base font-semibold text-ink-900">
            Gönderilen revizyonlar
          </h3>
          <ul className="mt-3 space-y-2.5">
            {history.revisions.map((revision, index) => {
              const previous = history.revisions[index - 1]?.definition;
              const keys = Object.keys(revision.definition) as (keyof Proposal)[];
              const changed = keys.filter(
                key =>
                  !previous ||
                  JSON.stringify(previous[key]) !== JSON.stringify(revision.definition[key]),
              );
              return (
                <li key={revision.id} className="rounded-lg border border-line bg-paper-sunk/40">
                  <details className="cce-disclosure px-4 py-3">
                    <summary>
                      Revizyon {revision.revision_number} — {revision.definition.name}
                    </summary>
                    <div className="mt-3 space-y-4 border-t border-line pt-3">
                      <p className="text-xs text-ink-500">
                        <Mono>{revision.id}</Mono>
                        {index > 0 &&
                          history.revisions[index - 1].avatar_id !== revision.avatar_id && (
                            <span className="ml-2 text-clay-700">Avatar önceki gönderime göre değişti.</span>
                          )}
                      </p>
                      <PrivateAvatar id={revision.avatar_id} size="sm" />
                      <p className="text-xs font-semibold text-ink-600">
                        {previous ? 'Önceki gönderime göre değişen alanlar' : 'İlk gönderimin alanları'}
                      </p>
                      {changed.length === 0 ? (
                        <p className="text-sm text-ink-600">İçerik değişmemiş.</p>
                      ) : (
                        changed.map(key => (
                          <div key={key} className="border-t border-line pt-2">
                            <h4 className="font-mono text-xs font-semibold text-ink-700">{key}</h4>
                            {previous && (
                              <pre className="cce-code mt-1.5">
                                Önce: {JSON.stringify(previous[key], null, 2)}
                              </pre>
                            )}
                            <pre className="cce-code mt-1.5">
                              Sonra: {JSON.stringify(revision.definition[key], null, 2)}
                            </pre>
                          </div>
                        ))
                      )}
                    </div>
                  </details>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {history.feedback.length === 0 && history.revisions.length === 0 && (
        <div className="mt-4">
          <Notice tone="neutral">Bu başvuru henüz gönderilmedi.</Notice>
        </div>
      )}
    </Card>
  );
}
