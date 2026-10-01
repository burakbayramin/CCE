import Link from 'next/link';
import { contributionApi, type Submission } from '../../../lib/contributions';
import { apiErrorMessage } from '../../../lib/api-errors';
export const dynamic = 'force-dynamic';
export default async function Drafts() {
  const result = await contributionApi<Submission[]>();
  return <main className="mx-auto max-w-3xl px-6 py-16"><Link href="/contributor" className="text-teal-700">Hesabım</Link><h1 className="my-6 text-3xl font-semibold">Taslaklarım ve başvurularım</h1><Link href="/contributor/drafts/new" className="inline-block rounded bg-slate-900 px-5 py-3 text-white">Yeni taslak</Link>
    {result.error ? <p role="alert" className="mt-6">{apiErrorMessage(result)}</p> : <ul className="mt-8 space-y-4">{result.data?.map(item => <li key={item.id} className="rounded border p-4"><Link href={`/contributor/drafts/${item.id}`} className="font-medium text-teal-800">{item.definition.name || 'İsimsiz taslak'}</Link><p className="mt-2 text-sm">{item.status} · Sürüm {item.version}</p></li>)}</ul>}
    {result.data?.length === 0 && <p className="mt-6">Henüz taslağın yok.</p>}
  </main>;
}
