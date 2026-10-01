/** Raw state-machine codes are the product's auditable vocabulary; the UI shows
 * them verbatim and layers colour on top rather than translating them away. */
export type SubmissionStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'CHANGES_REQUESTED'
  | 'REJECTED'
  | 'APPROVED'
  | 'WITHDRAWN';

/**
 * Renders the status code as the element's entire text content. The e2e suite
 * locates states with `getByText(code, { exact: true })` and
 * `locator('strong').filter({ hasText: /^CODE$/ })`, so no decoration may be
 * added inside the <strong>.
 */
export function StatusPill({ status }: { status: SubmissionStatus | string }) {
  return <strong className="cce-pill" data-status={status}>{status}</strong>;
}

const statusTone: Record<SubmissionStatus, 'info' | 'success' | 'warning' | 'danger' | 'neutral'> = {
  DRAFT: 'neutral',
  SUBMITTED: 'info',
  UNDER_REVIEW: 'warning',
  CHANGES_REQUESTED: 'warning',
  REJECTED: 'danger',
  APPROVED: 'success',
  WITHDRAWN: 'neutral',
};

/** One sentence explaining what the state means and what the contributor can
 * do next. Every branch is written from the actor's point of view. */
export function statusGuidance(status: string) {
  switch (status) {
    case 'DRAFT':
      return 'Taslak senin kontrolünde. İstediğin zaman düzenle ve incelemeye gönderebilirsin.';
    case 'SUBMITTED':
      return 'World Owner incelemeyi başlattığında burada durum değişecek. Gönderilen revizyon artık değiştirilemez.';
    case 'UNDER_REVIEW':
      return 'Owner başvuruyu inceliyor. Onay, ret veya değişiklik isteyebilir.';
    case 'CHANGES_REQUESTED':
      return 'Owner gerekçeli değişiklik istedi. Açıklamayı oku, sonra yeni bir revizyon taslağı aç.';
    case 'APPROVED':
      return 'Bu revizyon onaylandı. Karakter aktivasyonu henüz açık değil; dünya içine henüz katılmadı.';
    case 'REJECTED':
      return 'Başvuru reddedildi. Gerekçeyi okuyup yeni bir taslak açabilirsin.';
    case 'WITHDRAWN':
      return 'Geri çekilen başvuru yeniden açılmaz. Yeni bir taslak oluşturabilirsin.';
    default:
      return null;
  }
}

export function statusNoticeTone(status: string) {
  return statusTone[status as SubmissionStatus] ?? 'neutral';
}
