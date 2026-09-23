import Link from 'next/link';
import { login, signup } from '../app/(auth)/actions';
import { authConfig } from '../lib/supabase/config';

export function AuthForm({ mode, error, confirm }: { mode: 'login' | 'signup'; error: boolean; confirm?: boolean }) {
  const configured = Boolean(authConfig());
  return <main className="mx-auto max-w-lg px-6 py-20">
    <Link href="/" className="text-sm text-teal-700">CCE / Ana sayfa</Link>
    <h1 className="mt-6 text-3xl font-semibold">{mode === 'login' ? 'Giriş yap' : 'Katkıcı hesabı oluştur'}</h1>
    <p className="mt-4 text-slate-600">Katkıcılar dünyaya karakter önerebilir. Karakterlerle sohbet yetkisi yalnız World Owner’a aittir.</p>
    {!configured ? <p role="alert" className="mt-6">Yerel Auth yapılandırması eksik. README’deki kurulum adımlarını tamamla.</p> :
      <form action={mode === 'login' ? login : signup} className="mt-8 space-y-5">
        {error && <p role="alert">İşlem tamamlanamadı. Bilgilerini kontrol edip yeniden dene.</p>}
        {confirm && <p role="status">Hesabını doğrulamak için e-postanı kontrol et.</p>}
        <label className="block">E-posta<input className="mt-2 block w-full rounded border p-3" name="email" type="email" maxLength={254} autoComplete="email" required /></label>
        <label className="block">Şifre (en az 12 karakter)<input className="mt-2 block w-full rounded border p-3" name="password" type="password" minLength={12} maxLength={128} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required /></label>
        <button className="rounded bg-slate-900 px-5 py-3 text-white" type="submit">{mode === 'login' ? 'Giriş yap' : 'Kayıt ol'}</button>
      </form>}
    <Link className="mt-6 block text-teal-700" href={mode === 'login' ? '/signup' : '/login'}>{mode === 'login' ? 'Yeni hesap oluştur' : 'Mevcut hesapla giriş yap'}</Link>
  </main>;
}
