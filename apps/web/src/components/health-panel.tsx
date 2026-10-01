import Link from 'next/link';
import type { HealthSnapshot, HealthState } from '../lib/health';
import { Card, DefinitionRow, Page, PageHeader } from './ui';
import { StatusPill } from './status-pill';

const labels: Record<HealthState, string> = {
  ok: 'Hazır',
  unavailable: 'Hazır değil',
  unreachable: 'Doğrulanamadı',
};

const pillStatus: Record<HealthState, string> = {
  ok: 'PASS',
  unavailable: 'ERROR',
  unreachable: 'CANCELLED',
};

export function HealthPanel({ health }: { health: HealthSnapshot }) {
  const ready = health.api === 'ok' && health.database === 'ok';
  return (
    <Page width="wide">
      <div className="grid gap-10 lg:grid-cols-[1.15fr_1fr] lg:items-start">
        <div>
          <PageHeader
            eyebrow={
              <span className="font-mono text-xs tracking-[0.18em] text-ink-500">CCE / M1</span>
            }
            title="Ortak dünyanın ilk adımı"
            description="Bu ekran uygulamanın temel bağlantılarını kontrol eder. Karakter tasarlama, onay ve inceleme akışı katkıcı portalında açıktır."
            actions={
              <>
                <Link href="/login" className="cce-btn cce-btn-secondary no-underline">
                  Giriş yap
                </Link>
                <Link href="/signup" className="cce-btn cce-btn-primary no-underline">
                  Katkıcı hesabı oluştur
                </Link>
              </>
            }
          />

          <div className="grid gap-4 sm:grid-cols-3">
            {[
              ['Taslak yaz', 'Karakterini tanımla, revizyonlarla ilerle.'],
              ['Owner inceler', 'Gerekçeli karar ve geri bildirim al.'],
              ['Dünya kurulur', 'Onaylı karakterler ileride ortak dünyada bir araya gelir.'],
            ].map(([title, body], index) => (
              <div key={title} className="cce-card px-4 py-4">
                <p className="font-mono text-xs text-ink-400">0{index + 1}</p>
                <p className="mt-1.5 font-display text-base font-semibold text-ink-900">{title}</p>
                <p className="mt-1 text-sm leading-relaxed text-ink-600">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <Card>
          <div className="border-b border-line px-5 py-4">
            <h2 className="font-display text-lg font-semibold text-ink-900">
              {ready ? 'Temel bağlantılar hazır' : 'Bağlantı kontrolü gerekiyor'}
            </h2>
            <p className="mt-1 text-sm text-ink-600">
              {ready
                ? 'Web arayüzü, backend ve veritabanı birbirini doğruladı.'
                : 'API veya yerel veritabanı erişimi henüz doğrulanamadı.'}
            </p>
          </div>
          <div className="px-5 py-2">
            <dl className="divide-y divide-line">
              {(
                [
                  ['Web arayüzü', 'ok'],
                  ['Backend API', health.api],
                  ['Veritabanı erişimi', health.database],
                ] as const
              ).map(([name, state]) => (
                <DefinitionRow key={name} term={name}>
                  <span className="flex items-center justify-end gap-2">
                    {labels[state]}
                    <StatusPill status={pillStatus[state]} />
                  </span>
                </DefinitionRow>
              ))}
            </dl>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4">
            <p className="font-mono text-[0.6875rem] text-ink-500">istek {health.requestId.slice(0, 8)}</p>
            <form action="/" method="get">
              <button type="submit" className="cce-btn cce-btn-secondary">
                Yeniden kontrol et
              </button>
            </form>
          </div>
        </Card>
      </div>
    </Page>
  );
}
