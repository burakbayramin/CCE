import Link from 'next/link';
import { logout } from '../app/(auth)/actions';
import type { components } from '../lib/api/generated/schema';

export function IdentityPanel({ identity }: { identity: components['schemas']['Identity'] | null }) {
  return <main className="mx-auto max-w-2xl px-6 py-20">
    <Link href="/" className="text-teal-700">CCE / Ana sayfa</Link>
    <h1 className="mt-6 text-3xl font-semibold">{identity?.role === 'world_owner' ? 'World Owner' : 'Katkıcı portalı'}</h1>
    {!identity ? <p role="alert" className="mt-6">Kimlik servisine ulaşılamadı. Yetkiler doğrulanmadan işlem yapılamaz.</p> : <>
      <p className="mt-6">Oturum ve güncel yetkilerin doğrulandı.</p>
      <p className="mt-3 text-sm text-slate-600">Hesap kimliği: {identity.user_id}</p>
      {identity.person_id && <p className="mt-3 text-sm">Dünya içi insan kimliği: {identity.person_id}</p>}
      <p className="mt-6 text-slate-600">Karakter başvurusu ve inceleme akışları M2’nin sonraki diliminde eklenecek. Sohbet henüz açık değil.</p>
    </>}
    <form action={logout} className="mt-8"><button className="rounded bg-slate-900 px-5 py-3 text-white">Çıkış yap</button></form>
  </main>;
}
