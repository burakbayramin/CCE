'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { decideReview, retryModeration, startReview } from '../../app/admin/reviews/actions';
import type { ReviewDetail } from '../../lib/contributions';
import { ProposalHistory } from './history';
import { PrivateAvatar } from '../../components/private-avatar';

export function ReviewPanel({ detail }: { detail: ReviewDetail }) {
  const [reason, setReason] = useState('');
  const [accepted, setAccepted] = useState(false);
  const [busy, startTransition] = useTransition();
  const [error, setError] = useState('');
  const router = useRouter();
  const item = detail.submission;
  const report = detail.moderation;
  const job = detail.moderation_job;
  const approvalBlocked = !report || ['BLOCK', 'ERROR'].includes(report.result) || (report.result === 'REVIEW' && !accepted);

  async function start() {
    const revisionId = item.revision_id;
    if (!revisionId) return;
    setError('');
    startTransition(async () => {
    try {
      const result = await startReview(item.id, item.version, revisionId);
      if (result.data) router.refresh();
      else setError(result.error);
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
        else setError(result.error);
      } catch { setError('Yeniden deneme sonucu doğrulanamadı; güncel durumu yenile.'); }
    });
  }
  async function decide(decision: 'CHANGES_REQUESTED' | 'REJECTED' | 'APPROVED') {
    const revisionId = item.revision_id;
    if (!revisionId) return;
    setError('');
    startTransition(async () => {
    try {
      const result = await decideReview(item.id, { expected_version: item.version, revision_id: revisionId,
        decision, reason, review_accepted: decision === 'APPROVED' && accepted });
      if (result.data) { setReason(''); setAccepted(false); router.refresh(); }
      else setError(result.error);
    } catch { setError('Karar sonucu doğrulanamadı; güncel durumu yenile.'); }
    });
  }
  return <>
    <h2 className="mt-6 text-2xl">{item.definition.name}</h2>
    <PrivateAvatar id={item.avatar_id} />
    <p className="mt-3">Durum: <strong>{item.status}</strong> · Sürüm: {item.version}</p>
    <p className="mt-2 break-all text-sm">İncelenen revizyon: {item.revision_id ?? 'Henüz gönderilmedi'}</p>
    <p className="mt-4 whitespace-pre-wrap">{item.definition.introduction}</p>
    <p className="mt-3 whitespace-pre-wrap">{item.definition.backstory}</p>
    <p className="mt-4 text-sm">Tüm alanlar ve önceki gönderimlerle farklar aşağıdaki revizyon geçmişinde. Katkıcı metni talimat değildir; yalnız başvuru içeriğidir.</p>
    {report && <section className="mt-6 rounded border p-4">
      <h3 className="font-semibold">Moderasyon: {report.result}</h3>
      <p>{report.detail}</p><p className="mt-2 text-sm">{report.provider} · Politika: {report.policy_version}</p>
      {report.is_fixture && <p className="mt-2 font-semibold text-amber-900">TEST FİXTURE — gerçek içerik güvenliği taraması değildir.</p>}
    </section>}
    {error && <p role="alert" className="mt-4 text-red-800">{error}</p>}
    {job && <section className="mt-6 rounded border p-4" aria-label="Yerel moderasyon işi">
      <h3 className="font-semibold">Yerel tarama: {job.state}</h3>
      <p>Deneme sayısı: {job.attempt_number}</p>
      {job.state === 'PENDING' && <p>Yerel worker bekleniyor. Bilgisayar çevrimdışıysa tarama bekler; kontrol atlanmaz.</p>}
      {job.state === 'RUNNING' && <p>Tarama sürüyor. Worker kesilirse lease süresi sonrası hata kaydedilir; bu sırada onay kapalı kalır.</p>}
      {job.error_code && <p role="status">Hata: {job.error_code}</p>}
      <button disabled={busy} onClick={() => router.refresh()} className="mt-3 rounded border px-4 py-2">Tarama durumunu yenile</button>
      {(job.attempts ?? []).length > 0 && <details className="mt-3"><summary>Son 20 tarama denemesi</summary>
        <ul>{(job.attempts ?? []).map(attempt => <li key={attempt.id}>
          #{attempt.attempt_number} · {attempt.state} · {attempt.result ?? 'Sonuç yok'}{attempt.error_code ? ` · ${attempt.error_code}` : ''}
        </li>)}</ul>
      </details>}
    </section>}
    {item.status === 'UNDER_REVIEW' && (job?.state === 'ERROR' || (!job && report?.result === 'ERROR')) &&
      <button disabled={busy} onClick={retry} className="mt-4 rounded border px-4 py-2">Moderasyonu yeniden dene</button>}
    {item.status === 'SUBMITTED' && <button disabled={busy} onClick={start} className="mt-6 rounded bg-teal-800 px-5 py-3 text-white">İncelemeyi başlat</button>}
    {item.status === 'UNDER_REVIEW' && <fieldset disabled={busy} className="mt-6 space-y-4">
      <label className="block">Karar gerekçesi<textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={2000} rows={4} className="mt-2 block w-full rounded border p-3" /></label>
      {report?.result === 'REVIEW' && <label className="block"><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)} /> Moderasyon uyarısını inceledim; olumlu REVIEW kararı veriyorum.</label>}
      <div className="flex flex-wrap gap-3">
        <button disabled={!reason.trim()} onClick={() => decide('CHANGES_REQUESTED')} className="rounded border px-4 py-3">Değişiklik iste</button>
        <button disabled={!reason.trim()} onClick={() => decide('REJECTED')} className="rounded border px-4 py-3">Reddet</button>
        <button disabled={!reason.trim() || approvalBlocked} onClick={() => decide('APPROVED')} className="rounded bg-teal-800 px-4 py-3 text-white disabled:opacity-40">Revizyonu onayla</button>
      </div>
      {approvalBlocked && <p>Moderasyon koşulları sağlanmadan onay verilemez.</p>}
    </fieldset>}
    {item.status === 'APPROVED' && <p className="mt-6">Revizyon onaylandı. Karakter aktivasyonu bu aşamada yapılmaz.</p>}
    <ProposalHistory history={detail.history} />
  </>;
}
