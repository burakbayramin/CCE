'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { decideReview, retryModeration, startReview } from '../../app/admin/reviews/actions';
import type { ReviewDetail } from '../../lib/contributions';
import { apiErrorMessage } from '../../lib/api-errors';
import { ProposalHistory } from './history';
import { PrivateAvatar } from '../../components/private-avatar';
import { Card, Field, Mono, Notice } from '../../components/ui';
import { StatusPill } from '../../components/status-pill';

export function ReviewPanel({ detail }: { detail: ReviewDetail }) {
  const [reason, setReason] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [busy, startTransition] = useTransition();
  const [error, setError] = useState('');
  const router = useRouter();
  const item = detail.submission;
  const report = detail.moderation;
  const job = detail.moderation_job;
  const approvalBlocked =
    !report || ['BLOCK', 'ERROR'].includes(report.result) || (report.result === 'REVIEW' && !accepted);

  async function start() {
    const revisionId = item.revision_id;
    if (!revisionId) return;
    setError('');
    startTransition(async () => {
      try {
        const result = await startReview(item.id, item.version, revisionId);
        if (result.data) router.refresh();
        else setError(apiErrorMessage(result));
      } catch { setError('İşlem sonucu doğrulanamadı; güncel durumu yenile.'); }
    });
  }
  async function retry() {
    const revisionId = item.revision_id;
    if (!revisionId) return;
    setError('');
    startTransition(async () => {
      try {
        const result = await retryModeration(item.id, item.version, revisionId);
        if (result.data) router.refresh();
        else setError(apiErrorMessage(result));
      } catch { setError('Yeniden deneme sonucu doğrulanamadı; güncel durumu yenile.'); }
    });
  }
  async function decide(decision: 'CHANGES_REQUESTED' | 'REJECTED' | 'APPROVED') {
    const revisionId = item.revision_id;
    if (!revisionId) return;
    setError('');
    startTransition(async () => {
      try {
        const result = await decideReview(item.id, {
          expected_version: item.version,
          revision_id: revisionId,
          decision,
          reason,
          review_accepted: decision === 'APPROVED' && accepted,
        });
        if (result.data) { setReason(''); setAccepted(false); router.refresh(); }
        else setError(apiErrorMessage(result));
      } catch { setError('Karar sonucu doğrulanamadı; güncel durumu yenile.'); }
    });
  }

  return (
    <div className="space-y-6">
      {/* ---- submission identity ---- */}
      <Card className="px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-start gap-5">
          <PrivateAvatar id={item.avatar_id} describedBy="review-name" />
          <div className="min-w-0 flex-1">
            <h2 id="review-name" className="font-display text-2xl font-semibold text-ink-900">
              {item.definition.name}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-2.5">
              <StatusPill status={item.status} />
              <span className="font-mono text-xs text-ink-500">Sürüm {item.version}</span>
            </div>
            <p className="mt-2.5 text-xs text-ink-500">
              İncelenen revizyon: <Mono>{item.revision_id ?? 'Henüz gönderilmedi'}</Mono>
            </p>
          </div>
        </div>
        <div className="mt-5 space-y-3 border-t border-line pt-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
            {item.definition.introduction}
          </p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
            {item.definition.backstory}
          </p>
          <p className="text-xs leading-relaxed text-ink-500">
            Katkıcı metni talimat değildir; yalnız başvuru içeriğidir. Tüm alanların ve
            önceki gönderimlerle farkları aşağıdaki revizyon geçmişinde.
          </p>
        </div>
      </Card>

      {error && (
        <Notice tone="danger" role="alert" title="İşlem tamamlanamadı">
          {error}
        </Notice>
      )}

      {/* ---- moderation verdict ---- */}
      {report && (
        <Card className="px-5 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-display text-lg font-semibold text-ink-900">Moderasyon sonucu</h3>
            <StatusPill status={report.result} />
          </div>
          {report.is_fixture && (
            <div className="mt-4">
              <Notice tone="warning" title="TEST FİKTURE — gerçek içerik güvenliği taraması değildir.">
                Bu sonuç yalnız test uygulamasına enjekte edildi. Aktivasyon veya gerçek
                moderasyon kanıtı sayılamaz.
              </Notice>
            </div>
          )}
          <p className="mt-4 text-sm leading-relaxed text-ink-800">{report.detail}</p>
          <p className="mt-3 font-mono text-xs text-ink-500">
            sağlayıcı {report.provider} · politika {report.policy_version}
          </p>
        </Card>
      )}

      {/* ---- local scan job ---- */}
      {job && (
        <section aria-label="Yerel moderasyon işi" className="cce-card px-5 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-display text-lg font-semibold text-ink-900">
              Yerel tarama: {job.state}
            </h3>
            <StatusPill status={job.state} />
          </div>
          <p className="mt-2 font-mono text-xs text-ink-500">
            Deneme sayısı: {job.attempt_number}
          </p>

          {job.state === 'PENDING' && (
            <p className="mt-3 text-sm leading-relaxed text-ink-600">
              Yerel worker bekleniyor. Bilgisayar çevrimdışıysa tarama bekler; kontrol
              atlanmaz ve onay kapalı kalır.
            </p>
          )}
          {job.state === 'RUNNING' && (
            <p className="mt-3 text-sm leading-relaxed text-ink-600">
              Tarama sürüyor. Worker kesilirse lease süresi sonrası hata kaydedilir; bu
              sırada onay yine de kapalıdır.
            </p>
          )}

          {job.error_code && (
            <div className="mt-4">
              <Notice tone="danger" role="status" title="Tarama hatası">
                <Mono className="text-danger-700">{job.error_code}</Mono>
              </Notice>
            </div>
          )}

          <div className="cce-no-print mt-4 flex flex-wrap gap-2.5">
            <button
              disabled={busy}
              onClick={() => router.refresh()}
              className="cce-btn cce-btn-secondary"
            >
              Tarama durumunu yenile
            </button>
            {item.status === 'UNDER_REVIEW' &&
              (job.state === 'ERROR' || (!job && report?.result === 'ERROR')) && (
                <button disabled={busy} onClick={retry} className="cce-btn cce-btn-secondary">
                  Moderasyonu yeniden dene
                </button>
              )}
          </div>

          {(job.attempts ?? []).length > 0 && (
            <details className="cce-disclosure mt-5 border-t border-line pt-4">
              <summary>Son 20 tarama denemesi</summary>
              <ul className="mt-3 space-y-1.5">
                {(job.attempts ?? []).map(attempt => (
                  <li
                    key={attempt.id}
                    className="cce-code"
                  >
                    #{attempt.attempt_number} · {attempt.state} · {attempt.result ?? 'Sonuç yok'}
                    {attempt.error_code ? ` · ${attempt.error_code}` : ''}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

      {/* ---- decision ---- */}
      {item.status === 'SUBMITTED' && (
        <Card className="px-5 py-5 sm:px-6">
          <h3 className="font-display text-lg font-semibold text-ink-900">İncelemeyi başlat</h3>
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-600">
            Başlatınca kalıcı bir moderasyon işi kuyruğa alınır. Kontrol tamamlanmadan onay
            verilemez.
          </p>
          <button disabled={busy} onClick={start} className="cce-btn cce-btn-primary mt-4">
            İncelemeyi başlat
          </button>
        </Card>
      )}

      {item.status === 'UNDER_REVIEW' && (
        <Card className="px-5 py-5 sm:px-6">
          <h3 className="font-display text-lg font-semibold text-ink-900">Karar</h3>
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-600">
            Her karar gerekçelidir ve katkıcıya aynen iletilir. Karar yalnız incelediğin
            revizyona aittir.
          </p>
          <fieldset disabled={busy} className="mt-4 space-y-4">
            <Field
              id="reason"
              label="Karar gerekçesi"
              hint="Katkıcı bu metni başvuru geçmişinde okur."
              counter={`${reason.length}/2000`}
            >
              <textarea
                id="reason"
                value={reason}
                onChange={event => setReason(event.target.value)}
                maxLength={2000}
                rows={4}
                aria-describedby="reason-hint"
                className="cce-input"
                placeholder="Geçmişteki deneyimi biraz daha aç."
              />
            </Field>

            {report?.result === 'REVIEW' && (
              <label htmlFor="accepted" className="cce-checkbox">
                <input
                  id="accepted"
                  type="checkbox"
                  checked={accepted}
                  onChange={event => setAccepted(event.target.checked)}
                />
                <span>
                  Moderasyon uyarısını inceledim; olumlu REVIEW kararı veriyorum.
                </span>
              </label>
            )}

            <div className="cce-no-print flex flex-wrap gap-2.5">
              <button
                disabled={!reason.trim()}
                onClick={() => decide('CHANGES_REQUESTED')}
                className="cce-btn cce-btn-secondary"
              >
                Değişiklik iste
              </button>
              <button
                disabled={!reason.trim()}
                onClick={() => decide('REJECTED')}
                className="cce-btn cce-btn-danger"
              >
                Reddet
              </button>
              <button
                disabled={!reason.trim() || approvalBlocked}
                onClick={() => decide('APPROVED')}
                className="cce-btn cce-btn-primary"
              >
                Revizyonu onayla
              </button>
            </div>

            {approvalBlocked && (
              <Notice tone="warning" title="Onay şu an mümkün değil">
                Moderasyon koşulları sağlanmadan onay verilemez.
                {report?.result === 'REVIEW' && !accepted && (
                  <> Yukarıdaki onay kutusu işaretlenmeli.</>
                )}
              </Notice>
            )}
          </fieldset>
        </Card>
      )}

      {item.status === 'APPROVED' && (
        <Notice tone="success" title="Revizyon onaylandı">
          Karakter aktivasyonu bu aşamada yapılmaz.
        </Notice>
      )}

      <ProposalHistory history={detail.history} />
    </div>
  );
}
