import type { HealthSnapshot, HealthState } from "../lib/health";
import Link from 'next/link';

const labels: Record<HealthState, string> = {
  ok: "Hazır",
  unavailable: "Hazır değil",
  unreachable: "Doğrulanamadı",
};

export function HealthPanel({ health }: { health: HealthSnapshot }) {
  const ready = health.api === "ok" && health.database === "ok";
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-16">
      <p className="mb-5 text-xs font-semibold tracking-[0.24em] text-teal-700">CCE / FOUNDATION</p>
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Cognitive Character Engine</h1>
      <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-600">
        Ortak dünyanın ilk adımı. Bu ekran uygulamanın temel bağlantılarını kontrol eder.
      </p>
      <section aria-label="Bağlantı durumu" className="mt-10 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-medium">{ready ? "Temel bağlantılar hazır" : "Bağlantı kontrolü gerekiyor"}</h2>
        <dl className="mt-6 divide-y divide-slate-100">
          {([
            ["Web arayüzü", "ok"],
            ["Backend API", health.api],
            ["Veritabanı erişimi", health.database],
          ] as const).map(([name, state]) => (
            <div key={name} className="flex items-center justify-between gap-4 py-4">
              <dt className="text-slate-600">{name}</dt>
              <dd className={state === "ok" ? "font-medium text-teal-700" : "font-medium text-amber-700"}>
                {labels[state]}
              </dd>
            </div>
          ))}
        </dl>
        {!ready && <p className="mt-3 text-sm text-slate-600">API veya yerel veritabanı erişimi henüz doğrulanamadı.</p>}
        <form action="/" method="get">
          <button type="submit" className="mt-6 cursor-pointer rounded-lg bg-slate-900 px-5 py-3 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-700">Yeniden kontrol et</button>
        </form>
      </section>
      <p className="mt-6 text-sm text-slate-500">M1 · Altyapı kurulumu</p>
      <Link href="/login" className="mt-4 text-teal-700">Giriş / Katkıcı kaydı</Link>
    </main>
  );
}
