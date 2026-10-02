import Link from 'next/link';
import { logout } from '../app/(auth)/actions';
import type { components } from '../lib/api/generated/schema';
import { Card, Mono, Notice, Page, PageHeader } from './ui';
import { StatusPill } from './status-pill';

export function IdentityPanel({ identity }: { identity: components['schemas']['Identity'] }) {
  const owner = identity.role === 'world_owner';

  return (
    <Page>
      <PageHeader
        eyebrow={
          <span className="font-mono text-xs tracking-[0.18em] text-ink-500">
            {owner ? 'WORLD OWNER' : 'KATKIÇI'}
          </span>
        }
        title={owner ? 'World Owner portalı' : 'Katkıcı portalı'}
        meta={<StatusPill status={owner ? 'APPROVED' : 'DRAFT'} />}
        description="Oturum ve güncel yetkilerin doğrulandı."
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <Card className="px-5 py-5">
          <h2 className="font-display text-base font-semibold text-ink-900">Karakter önerilerin</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-600">
            Taslak yaz, gönder, geri çek. Gönderilen revizyon değiştirilemez; Owner değişiklik
            istediğinde yeni bir revizyon açarsın.
          </p>
          <Link
            href="/contributor/drafts"
            className="cce-btn cce-btn-primary mt-4 no-underline"
          >
            Karakter taslaklarım ve başvurularım
          </Link>
        </Card>

        {owner && (
          <Card className="px-5 py-5">
            <h2 className="font-display text-base font-semibold text-ink-900">
              İnceleme kuyruğu
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-600">
              Gönderilen başvuruları incele, gerekçeli karar ver. Onay yalnız incelediğin
              revizyona aittir.
            </p>
            <Link href="/admin/reviews" className="cce-btn cce-btn-secondary mt-4 no-underline">
              Başvuru incelemeleri
            </Link>
          </Card>
        )}
      </div>

      {owner && (
        <Card className="mt-5 px-5 py-5">
          <h2 className="font-display text-base font-semibold text-ink-900">
            Kendi karakterini oluştur
          </h2>
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-600">
            Owner olarak karakter önerebilirsin. <strong>Katılımcıyla aynı yapılandırılmış
            formu ve aynı doğrulama hattını</strong> kullanırsın; doğrulama, moderasyon
            taraması veya değiştirilemez revizyon hattında hiçbir adım atlanmaz. Kendi
            başvurunu onaylarken doğrulama yeniden çalışır ve audit kaydına gerçek aktörün
            yazılır. <code className="font-mono text-xs">BLOCK</code> sonucu kendi
            karakterinde de geçerlidir.
          </p>
          <Link
            href="/contributor/drafts/new"
            className="cce-btn cce-btn-secondary mt-4 no-underline"
          >
            Yeni karakter taslağı aç
          </Link>
        </Card>
      )}

      <div className="mt-6 space-y-5">
        <Notice tone="neutral" title="Bu sürümde henüz açık olanlar">
          Medya yükleme ve başvuru akışı çalışıyor. Karakter aktivasyonu, sohbet ve dünya
          içi etkileşim henüz açık değil.
        </Notice>

        <Card className="px-5 py-4">
          <h2 className="font-display text-base font-semibold text-ink-900">Hesap kimliği</h2>
          <dl className="mt-3 space-y-2.5">
            <div>
              <dt className="text-sm text-ink-600">Hesap UUID</dt>
              <dd className="mt-0.5">
                <Mono>{identity.user_id}</Mono>
              </dd>
            </div>
            {identity.person_id && (
              <div>
                <dt className="text-sm text-ink-600">Dünya içi insan kimliği</dt>
                <dd className="mt-0.5">
                  <Mono>{identity.person_id}</Mono>
                </dd>
              </div>
            )}
          </dl>
        </Card>

        <form action={logout} className="cce-no-print">
          <button type="submit" className="cce-btn cce-btn-secondary">
            Çıkış yap
          </button>
        </form>
      </div>
    </Page>
  );
}
