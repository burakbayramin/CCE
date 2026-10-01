import Link from 'next/link';
import { login, signup } from '../app/(auth)/actions';
import { authConfig } from '../lib/supabase/config';
import { Card, Notice, Page, PageHeader } from './ui';

export function AuthForm({
  mode,
  error,
  confirm,
}: {
  mode: 'login' | 'signup';
  error: boolean;
  confirm?: boolean;
}) {
  const configured = Boolean(authConfig());
  const isSignup = mode === 'signup';

  return (
    <Page width="narrow">
      <PageHeader
        eyebrow={
          <span className="font-mono text-xs tracking-[0.18em] text-ink-500">
            {isSignup ? 'YENİ HESAP' : 'YETKİLİ GİRİŞ'}
          </span>
        }
        title={isSignup ? 'Katkıcı hesabı oluştur' : 'Giriş yap'}
        description="Katkıcılar dünyaya karakter önerebilir. Karakterlerle sohbet ve dünya üzerinde etki yetkisi yalnız World Owner'a aittir."
      />

      <Card className="px-5 py-6 sm:px-7 sm:py-8">
        {!configured ? (
          <Notice tone="warning" title="Yerel Auth yapılandırması eksik">
            README&apos;deki kurulum adımlarını tamamla. `apps/web/.env.local` içindeki
            publishable key eksik olduğu için giriş çalışmıyor.
          </Notice>
        ) : (
          <form action={isSignup ? signup : login} className="space-y-5">
            {error && (
              <Notice tone="danger" role="alert" title="İşlem tamamlanamadı">
                Bilgilerini kontrol edip yeniden dene. Şifrenin en az 12 karakter olması gerekir.
              </Notice>
            )}
            {confirm && (
              <Notice tone="info" role="status" title="E-postanı kontrol et">
                Hesabını doğrulamak için gönderilen bağlantıyı aç. Doğrulamadan önce giriş yapamazsın.
              </Notice>
            )}

            <div>
              <label htmlFor="email" className="text-sm font-semibold text-ink-800">
                E-posta
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                maxLength={254}
                autoFocus
                className="cce-input mt-1.5"
                placeholder="ornek@eposta.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="text-sm font-semibold text-ink-800">
                Şifre
                <span className="ml-1.5 font-normal text-ink-500">(en az 12 karakter)</span>
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete={isSignup ? 'new-password' : 'current-password'}
                className="cce-input mt-1.5"
                placeholder="••••••••••••"
              />
              {isSignup && (
                <p className="mt-1.5 text-xs text-ink-500">
                  Uzun bir cümle, kısa bir parolanın çok daha güvenlisidir.
                </p>
              )}
            </div>

            <button type="submit" className="cce-btn cce-btn-primary w-full">
              {isSignup ? 'Kayıt ol' : 'Giriş yap'}
            </button>
          </form>
        )}
      </Card>

      <p className="mt-6 text-center text-sm text-ink-600">
        {isSignup ? 'Zaten hesabın var mı?' : 'Henüz hesabın yok mu?'}{' '}
        <Link href={isSignup ? '/login' : '/signup'} className="font-semibold text-accent-700">
          {isSignup ? 'Mevcut hesapla giriş yap' : 'Yeni hesap oluştur'}
        </Link>
      </p>
    </Page>
  );
}
