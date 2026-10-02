# M1 Raporu — Foundation

**Aşama:** M1 — Foundation
**Durum:** Tamamlandı (2026-09-23)
**İlgili WADR'lar:** WADR-011 (teknoloji yığını), WADR-012 (veritabanı ve event şeması), WADR-013 (backend/worker/frontend mimarisi)

**Commit'ler**

| Commit | İçerik |
| --- | --- |
| `d3ea298` | M1 workspace araç ve bağımlılık sürümlerinin sabitlenmesi |
| `7d44fbc` | En az yetkili veritabanı temeli ve web → API health akışı |
| `3f49a46` | Foundation CI: sözleşme, veritabanı ve container build doğrulaması |
| `fc1179b` | Desteklenen action sürümlerinin ve Ubuntu runner'ın sabitlenmesi |
| `26f312b` | Doğrulanmış M1 tamamlanma kaydı |

**Doğrulama:** [Foundation CI 35835256902](https://github.com/burakbayramin/CCE/actions/runs/35835256902) — `checks`, `database`, `containers` üç job'ı da başarılı.

> Bu rapor yalnız M1'in o noktadaki durumunu anlatır. M1 kapsamında yazılan
> migration ve roller sonraki aşamalarda genişletilmiştir; "değiştirilmedi" ifadesi
> bugünkü hâli değil, bu aşamada bırakıldığı hâli ifade eder.

---

## 1. Hedef

Uygulamanın temiz bir ortamda kurulabilmesi ve **tek bir health akışının web → API →
veritabanı boyunca çalışması.** Bu aşamanın tek ölçülebilir işi bir özellik değil,
sonraki altı aşamanın üzerine kurulacağı zeminin doğrulanmış olmasıydı.

Plandaki günlük hedef şuydu: *"İlk günün hedefi M1'dir: temiz checkout'tan
kurulabilen, yerel veritabanına bağlanan API, basit web ekranı ve çalışan CI. GPU veya
gerçek model ilk günü bloke etmez."*

## 2. Teslim edilen iş

### M1.1 — Araç ve sürümler
Python 3.13, Node 22 ve pnpm sürümleri `.python-version`, `.node-version`,
`engines` ve `packageManager` alanlarıyla sabitlendi. `uv` sürümü backend paketinde
`required-version` ile, Supabase CLI sürümü `devDependencies` ile kilitlendi.
`uv.lock` ve `pnpm-lock.yaml` commit'lenerek sürüm kayması kapatıldı.

### M1.2 — Minimum repo
`apps/web`, `services/backend`, `supabase` ve CI/config dosyaları oluşturuldu.
Aşamada **kasıtlı olarak** kullanılmayan domain modülleri veya boş adapter
klasörleri üretilmedi (plan maddesi bunu açıkça yasaklıyordu).

### M1.3 — Veritabanı temeli
Supabase CLI SQL migration hattı kuruldu ve üç şema sınırı tanımlandı:

| Şema | Amaç |
| --- | --- |
| `public` | Data API'ye açık uygulama şeması |
| `world_private` | Dünya ve kişi state'i — Data API'ye kapalı |
| `ops_private` | Operasyon ve denetim — Data API'ye kapalı |

Rol ayrımı migration'da kuruldu ve **nologin** olarak tanımlandı. Rollere üyelik
yönü yalnız `postgres → cce_migrator` ile sınırlı; migration runner'ın dışında hiçbir
role üyelik verilmedi. `rolsuper`/`rolbypassrls`/`rolcreatedb`/`rolcreaterole`
taşıyan rollerin varlığı migration'ı hata durduracak şekilde denetleniyor.

Ayrıca default privilege'lar `anon`, `authenticated`, `service_role` ve `public`
için geri alındı — yani ileride eklenen tablolar Data API'ye **kendiliğinden
açılmaz**.

### M1.4 — Çalışan iskelet
- FastAPI `/health/live` (liveness) ve `/health/ready` (readiness)
- Web'de tek health görünümü
- Doğrulanmış yapılandırma (`Settings` — kimlik bilgisi içeren origin reddi dâhil)
- Correlation id'li JSON log; istek, durum ve süre. Token, cookie, gövde veya URL yok
- Test edilebilir `world_clock` arayüzü — tam dünya simülasyonu M5'e bırakıldı

### M1.5 — Geliştirme akışı
`.env.example`, `.gitignore`, README kurulum adımları ve yerel servis başlatma
düzeni. Secret veya gerçek kullanıcı verisi repoya girmedi.

### M1.6 — CI
Üç job: `checks` (backend lint/typecheck/test + frontend lint/typecheck/test/build +
OpenAPI drift), `database` (boş DB migration + pgTAP + gerçek rol testleri),
`containers` (iki container build). **Production deploy otomatikleşmedi.**
Action sürümleri SHA ile, runner `ubuntu-24.04` olarak sabitlendi.

## 3. Ölçek

| | M1 sonrası |
| --- | --- |
| Migration | 1 |
| Backend kaynak dosyası | 8 |
| Web kaynak dosyası | 7 |
| Backend test dosyası | 3 |
| pgTAP dosyası | 1 |
| Web test dosyası | 2 |

Tamamlanma anındaki koşu sayıları: **9 backend birim + 2 veritabanı entegrasyon,
15 pgTAP, 5 web testi.** Web portu 3100.

## 4. Doğrulama kanıtı

Temiz bir koşuda doğrulananlar:

- Kilitli kurulum (`pnpm install --frozen-lockfile`, `uv sync --locked`)
- Boş veritabanında migration uygulaması ve reset sonrası tekrarı
- Gerçek rol testleri — yetkiler katalogdan doğrulandı
- OpenAPI sözleşme drift kontrolü
- İki container'ın **non-root** çalışması ve health akışı (yerelde doğrulandı)
- Web → API → DB uçtan uca smoke
- DB erişilemezken readiness'in uygun hata döndürmesi
- README komutlarının fiilen denenmiş olması

## 5. Bu aşama ne demek, ne demek değil

**Demek:** Zemin doğrulanmış. Sürüm kayması kapatılmış, migration hattı çalışıyor,
CI boş bir veritabanından başarıyla geçiyor, ve web→API→DB yolu uçtan uca ölçülmüş
durumda.

**Dememek:** Hiçbir kullanıcı, karakter, başvuru veya oturum yok. Kimlik doğrulama
yok, yetki sözleşmesi yok, gerçek model yok. `world_clock` bir arayüzdür, dünya
simülasyonu değildir.

## 6. Sonraki aşamaya açtığı kapı

M1'in asıl değeri kodu değil, **güvenilir zemindi.** M2 buna şu üç şeyi yasladı:

1. Migration hattı ve rol ayrımı hazırdı — `identity_foundation` yeni roller eklemeden
   mevcut güvenlik modeline oturdu.
2. Yapılandırma doğrulaması hazırdı — `CCE_ENVIRONMENT` ve origin reddi doğrudan
   kullanıldı.
3. CI üç job'lıydı — M2'nin tarayıcı testleri ek job açmadan aynı pipeline'a girdi.

## 7. Sonradan sertleştirilen yüzeyler

M1'in koyduğu iki karar sonraki aşamalarda sıkılaştırıldı; ikisi de M1'i geçersiz
kılmıyor, gücünü artırıyor:

- **Şema sürümü kapısı** — readiness artık beklenen sürümü karşılaştırıyor ve uygulama
  açılışta doğruluyor. Bu aşamada sabit `1` idi; sürüm ilerledikçe karşılaştırılan
  değer ilerledi ve kapı gerçek bir güvenlik sınırı oldu.
- **Rol hijyeni** — `cce_migrator` üyeliğinin RLS'i atlatabilmesi yalnız açık bir
  `revoke` ile engellendi; `noinherit` tek başına yeterli olmadığı için bu yön
  tercih edildi.

Ayrıntı için `docs/ADVERSARIAL_REVIEW_2026-10-01.md`.