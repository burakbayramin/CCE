<div align="center">

<img src=".github/assets/cce.jpg" alt="Cognitive Character Engine karakter çizimi" width="220">

[English](README.md) · **Türkçe**

# Cognitive Character Engine

**Kalıcı AI karakterlerin yaşadığı ortak dünya motoru.**

Destekçiler UI üzerinden karakter tasarlar, bir World Owner her şeyi onaylar ve
aktifleştirir; karakterler birbirleriyle özerk etkileşim, ilişki ve hafıza geliştirir.

[![Foundation CI](https://github.com/burakbayramin/CCE/actions/workflows/ci.yml/badge.svg)](https://github.com/burakbayramin/CCE/actions/workflows/ci.yml)
![Python 3.13](https://img.shields.io/badge/Python-3.13.3-3776AB?logo=python&logoColor=white)
![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL%2017-3FCF8E?logo=supabase&logoColor=white)
![uv](https://img.shields.io/badge/uv-0.10.3-2A2A2A?logo=uv&logoColor=white)

[Başa dön ↑](#cognitive-character-engine)

</div>

---

## 📑 İçindekiler

| Bölüm | İçerik |
| :-- | :-- |
| [Ürün](#-ürün) | Ne inşa ediliyor, roller, sınırlar |
| [Durum](#-durum) | Milestone tablosu ve bugünün sınırı |
| [Mimari](#-mimari) | Katmanlar, veri akışı, depo haritası |
| [Hızlı başlangıç](#-hızlı-başlangıç) | 10 dakikada çalışan lokal yığın |
| [Moderasyon worker](#-moderasyon-worker) | Worker kimliği, env, çalıştırma |
| [Doğrulama](#-doğrulama) | Günlük kontroller ve test yığınları |
| [Veri modeli ve güvenlik](#-veri-modeli-ve-güvenlik) | Şema, roller, RLS sınırları |
| [CI](#-ci) | Pipeline kapsamı |
| [Dokümanlar](#-dokümanlar) | WADR, plan, teknik dayanaklar |

---

## 🌍 Ürün

Cognitive Character Engine, proje yöneticisinin AI karakterlerle konuşabildiği ve
karakterlerin birbirleriyle ilişki kuran kalıcı bir yapay dünya motorudur.
Katkıcılar karakter tasarlar; **onay ve yayın yetkisi yalnızca World Owner'dadır.**

### Roller

| Rol | Yapabildiği | Yapamadığı |
| :-- | :-- | :-- |
| 🧑‍💻 **World Owner** | Karakter oluşturur, başvuruları inceler ve gerekçeli ret/ değişiklik talebi verir, onaylanan tanımı derler, onaylar | Kendi incelemesini atlayamaz; audit gerçek actor ile yazılır |
| 🧑 **Contributor** | Hesap açar, taslak hazırlar, avatar yükler, başvuruyu gönderir/geri çeker, yeni revizyon üretir | Canlı karakterlerle konuşamaz, canlı state'i değiştiremez |
| 🤖 **AI Karakter** | Onaylandıktan sonra dünyada aktif varlık olur, diğerleriyle etkileşir, ilişki/mood/goal geliştirir | Katkıcı tarafından doğrudan kontrol edilemez |

> [!NOTE]
> World Owner'ın yönetici yetkisi ile dünya içindeki **insan kimliği** ayrı kavramlardır.
> İnsan katılımcı AI olarak simüle edilmez; engine onun adına konuşma veya duygu üretmez.
> Onun özel sohbetten öğrenilen bilgisi, açık izin verilmedikçe başka karakterlere aktarılmaz (`AK-001`).

### Temel ilkeler

- **Değiştirilemez sürümleme** — gönderilen her revizyon ve derlenen tanım kalıcıdır; eski sürüm yeniden yazılmaz.
- **Kaynaktan türetilen tanım** — system prompt sabittir, katkı metni ayrı bir JSON veri alanında tutulur.
- **Kanıt olmayan şey kanıt değildir** — fixture, sentetik verdict veya dosya doğrulaması gerçek moderasyon/aktivasyon kanıtı yerine geçmez.
- **En az yetki** — API, engine ve dört worker rolü ayrıdır; her özellik kendi grant/RLS kuralını migration içinde getirir.

---

## 📍 Durum

Küratörlük hattı uçtan uca çalışıyor: katkıcı karakter önerir, World Owner gerekçeli
inceler ve karar değiştirilemez. İki kapı bilinçli olarak kapalı — kabul edilmiş bir
moderasyon modeli yok ve henüz gerçek içerik aktive edilemiyor.

Aşamalar numaraya göre değil **bugün gerçekten ne yaptıklarına** göre gruplanıyor,
çünkü bu ayrım sıralamadan daha önemli.

### ✅ Tamamlandı

| Aşama | Size kazandırdığı |
| :-- | :-- |
| **M1** — Foundation | Lokal web/API/veritabanı, health kontrolleri, üç job'lı CI |
| **M2** — Kimlik ve katkı | Giriş, taslak → başvuru → geri çekme, Owner incelemesi, private avatar |
| **M3.1** — Definition derleyici | Değiştirilemez, hash ile doğrulanan karakter tanımları |
| **M4.1** — Kalıcı iş protokolü | Karakter başına tek rezervasyon, fence'li lease, model-bağımsız etki kimliği, outbox |
| **M4.2** — Kuyruk ve worker | pgmq adapter, commit sonrası onay, bounded retry, quarantine, recovery taraması |
| **M4.3** — Model sınırı | Provider protokolü, deterministik fake, zorlanan token/süre/deneme bütçesi, doğrulanan çıktı |

### 🧪 Yalnız test fixture'ı

Uygulanmış ve test edilmiş, ancak **her komut yolu gerçek içeriği reddediyor.**
`is_fixture` sınırı yalnız uygulamada değil, veritabanında da zorlanıyor.

| Aşama | Size kazandırdığı |
| :-- | :-- |
| **M3.2** — Moderasyon kuyruğu | Kalıcı kuyruk, deneme/lease protokolü, worker döngüsü, Owner bekleme/retry görünümü |
| **M3.3** — Aktivasyon | Atomik kimlik ve başlangıç kaydı, kapasite sınırları, Owner görünümü |
| **M3.4** — Lifecycle | Askı, arşiv, aynı kimlikle restore, yeniden aktivasyon, denetimli |
| **M3.5** — Definition değişikliği | Denetimli benimseme, kilitli çekirdek alanlar, korunan geçmiş |
| **M3.6** — Yönetim görünümü | Owner karakterleri aynı hatta yazıyor; audit gerçek aktörü gösteriyor |

### ⏳ Açık

| Aşama | Kapsam |
| :-- | :-- |
| **M3.2 (son)** | Kalibre edilmiş yerel tarayıcı ve model kabulü |
| **M4.4** | Kaynak kimliğine bağlı işleyici handler'ları, atomik tur uygulaması, flag'li ilişki hataları |
| **M4.5** | İdempotent tur kabulü, outbox ile teslim, yayıncı düzlemi |
| **M4.6** | Teslim edilmiş turun SSE akışı — Realtime kanalı ve yanıt token'ı açık |
| **M4.7** | Operasyon UI'ı |
| **M5–M6** | Dünya saati, presence, scene'ler, bilişsel state |
| **M7–M8** | Public yayın, World Viewer, staging kabulü |

> [!WARNING]
> **Bu dilim canlı karakter oluşturmaz ve gerçek otomatik moderasyon yapılandırmamıştır.**
> `PASS` / `REVIEW` / `BLOCK` sağlayıcı fixture'ları yalnız test uygulamasına enjekte edilir
> ve UI'da etiketlenir. `BLOCK` ve `ERROR` override edilemez; `REVIEW` için açık olumlu karar gerekir.
> Aktivasyon, lifecycle ve definition benisleme komutları da aynı nedenle yalnız izole test
> politikasında çalışır; gerçek içerik için komut yolu yoktur. Kesin model seçimi, runtime ve
> lisans kararı kabul aşamasına ertelenmiştir; haricî moderasyon API'si veya cloud fallback
> **kullanılmayacaktır**. Contributor'ların public açılışı için hazır değildir.

Detaylı ve güncel iş kaydı → [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

---

## 🏗️ Mimari

```text
┌──────────────┐   SSR + fetch     ┌──────────────┐   psycopg (cce_api)   ┌──────────────┐
│  Next.js 16  │ ────────────────► │ FastAPI      │ ───────────────────►  │  PostgreSQL  │
│  apps/web    │ ◄──────────────── │  :8000       │ ◄─────────────────── │  (Supabase)  │
└──────────────┘   JSON + şema.sahip└──────────────┘   ayrı roller/RLS    └──────────────┘
       ▲                                                                       ▲
       │ Supabase Auth (SSR cookie, PKCE)                    cce_engine · cce_worker_cpu
       └───────────────────────────────┐                        └────────────────┐
                                        │                                          │
                              ┌─────────▼─────────┐                    ┌───────────▼────────────┐
                              │ World Owner       │                    │ cce-moderation-worker  │
                              │ /admin/reviews    │                    │ (ayrı CLI, yalnız CPU   │
                              │ onay / ret / retry│                    │  worker DB + Auth)     │
                              └───────────────────┘                    └───────────┬────────────┘
                                                                                      │
                                                                            private Storage
                                                                             (avatar okuma, RLS)
```

- **Web ↔ API sözleşmesi** OpenAPI'den üretilir; CI yeniden üretip farkı kontrol eder
  (`apps/web/src/lib/api/generated/schema.d.ts` elle düzenlenmez).
- **İstek kimliği** web ve API JSON loglarında aynıdır. URL/query, token, cookie, body ve
  ham exception içerikleri loglara alınmaz.
- **Yerel sağlık** — liveness DB kapalıyken de 200 verir; readiness bağlantı, kısıtlı API
  kimliği ve migration marker'ını doğrular, aksi hâlde 503 döner ve web bunu başarılı gibi göstermez.
- **Cloud control plane + yerel AI plane** — AI işleri hedef makinede (RTX 3070 / 32 GB) çalışır.

### Depo haritası

```text
apps/web/                    Next.js 16 App Router; (auth), /contributor, /admin, /media
services/backend/            FastAPI; src/cce/{core,modules,infrastructure}
  modules/identity/          JWT doğrulama, owner yetkisi, oturum kontrolü
  modules/contributions/     Taslak/başvuru, avatar, moderasyon işi + worker CLI
  modules/characters/        Definition derleme
supabase/migrations/         Tek şema tarihçesi (foundation → avatar okuyucu)
supabase/tests/              pgTAP testleri
scripts/                     setup_local_db · bootstrap_owner · check_health · export_openapi
infrastructure/              Docker ve izole test yığını yapılandırması
graft/                       Repo bağlam grafiği (graft build ile yenilenir)
```

---

## 🚀 Hızlı başlangıç

### Gereksinimler

| Gereksinim | Not |
| :-- | :-- |
| Docker çalışan daemon | Supabase CLI buna bağlanır. Docker yalnız WSL'de ise aşağıdaki WSL bölümüne bakın. |
| Python **3.13.3** | `.python-version` |
| Node.js **22.15.0** + pnpm **10.13.1** | `.node-version`, `packageManager` |
| uv **0.10.3** | CI ve backend image ile aynı |
| Supabase CLI **2.117.0** | repo devDependency; Linux CLI ayrıca indirilir |

<details>
<summary><b>🔧 Sabitlenen araç sürümleri</b></summary>

| Araç | Sürüm | Nerede sabitlendi |
| :-- | :-- | :-- |
| Python | 3.13.3 | `.python-version`, `requires-python = ">=3.13,<3.14"` |
| Node.js | 22.15.0 | `.node-version`, `engines` |
| uv | 0.10.3 | `services/backend/pyproject.toml` → `required-version` |
| pnpm | 10.13.1 | `packageManager`, `engines.pnpm` |
| Supabase CLI | 2.117.0 | `package.json` devDependencies |
| PostgreSQL | 17 | Supabase CLI image'ı |

Kesin paket sürümleri `services/backend/uv.lock` ve `pnpm-lock.yaml` içindedir.
Komutlar aksi belirtilmedikçe **repo kökünden** çalıştırılır.

</details>

### 1 — Kurulum

```powershell
pnpm install --frozen-lockfile
uv sync --project services/backend --locked
Copy-Item .env.example .env
Copy-Item apps/web/.env.example apps/web/.env.local
```

`.env` dosyalarınız zaten varsa kopyalama adımlarını atlayın. Örnek bağlantı bilgileri
yalnız **lokal test fixture'larıdır**; gerçek credential'ları migration'a veya
`NEXT_PUBLIC_*` değişkenlerine koymayın.

### 2 — Yerel Supabase + migration + fixture

```powershell
pnpm exec supabase start --exclude studio,imgproxy,edge-runtime,logflare,vector
pnpm db:migrate
$env:CCE_ENVIRONMENT = "local"
uv run --project services/backend python scripts/setup_local_db.py
```

`supabase start` boş veritabanına migration'ları uygular; `pnpm db:migrate` sonraki
pending migration'ları uygular. Studio dahil **tam** lokal stack için `pnpm db:start`.
Bu repo bir cloud Supabase projesine bağlı değildir.

<details>
<summary><b>🐧 Docker yalnız WSL'deyse</b></summary>

Windows Supabase executable'ı Linux Docker socket'ine bağlanamaz. Önce ayrı bir
terminalde `wsl -d Ubuntu-24.04` açıp **açık bırakın**; dağıtım kapanınca Docker da durur
(yalnız systemd servisleri ayakta tutmuyor). Dağıtım yeniden açılırken geçici DB bağlantı
hatası görülebilir.

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'mkdir -p .artifacts/cli-linux && curl -fsSL https://github.com/supabase/cli/releases/download/v2.117.0/supabase_linux_amd64.tar.gz -o .artifacts/cli-linux/supabase.tar.gz && tar -xzf .artifacts/cli-linux/supabase.tar.gz -C .artifacts/cli-linux'
wsl -d Ubuntu-24.04 -- .artifacts/cli-linux/supabase --version
wsl -d Ubuntu-24.04 -- .artifacts/cli-linux/supabase start --exclude studio,imgproxy,edge-runtime,logflare,vector
wsl -d Ubuntu-24.04 -- .artifacts/cli-linux/supabase migration up --local
$env:CCE_ENVIRONMENT = "local"
uv run --project services/backend python scripts/setup_local_db.py
```

Diğer `pnpm exec supabase …` komutlarında aynı Linux önekini kullanın. API ve web
Windows'ta çalışabilir; DB'ye `127.0.0.1:54322` üzerinden erişirler. Bu düzen Linux
`node_modules` veya Python ortamını Windows ortamıyla paylaşmaz.

</details>

### 3 — Çalıştırma

İki ayrı terminalde:

```powershell
pnpm dev:api      # FastAPI  → http://127.0.0.1:8000
pnpm dev:web      # Next.js  → http://127.0.0.1:3100
```

| Uç | Adres |
| :-- | :-- |
| Web | <http://127.0.0.1:3100> |
| Liveness | <http://127.0.0.1:8000/health/live> |
| Readiness | <http://127.0.0.1:8000/health/ready> |
| OpenAPI | <http://127.0.0.1:8000/openapi.json> |

<details>
<summary><b>📦 Container akışı</b></summary>

Yerel Supabase ve fixture kurulumu tamamlandıktan sonra:

```powershell
docker compose up --build -d
docker compose ps
docker compose down
```

WSL-only Docker'da önek `wsl -d Ubuntu-24.04 -- docker compose …` olur. Compose yalnız
web/API'yi yönetir; DB'yi Supabase CLI yönetir. Aynı portlarda yerel dev sunucuları
çalışıyorsa önce onları durdurun. Image'lar non-root kullanıcıyla çalışır;
`host.docker.internal` lokal PostgreSQL erişimi içindir.

</details>

---

## 🔐 Kimlik ve ilk Owner ataması

> [!TIP]
> Supabase Auth yapılandırması eksikse health ekranı çalışır; giriş ekranı eksikliği
> açıkça gösterir. Lokal `supabase status -o json` çıktısındaki **yalnız `PUBLISHABLE_KEY`**
> değerini `apps/web/.env.local` içindeki `CCE_SUPABASE_PUBLISHABLE_KEY` alanına koyun.
> Compose için aynı değeri kökteki `.env` içine de koyun. **Service/secret anahtarı kullanılmaz.**

1. `/signup` üzerinden kendi hesabınızı oluşturun. Bütün yeni hesaplar katkıcıdır;
   metadata'daki rol alanı dikkate alınmaz. Portal hesap UUID'sini gösterir.
2. Owner ataması yalnız operatör terminalinden yapılır:

```powershell
$env:CCE_ADMIN_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
uv run --project services/backend python scripts/bootstrap_owner.py --user-id <hesap-uuid> --display-name "<dünya içi ad>" --operator "<işlemi yapan operatör>" --reason "İlk World Owner kurulumu"
Remove-Item Env:CCE_ADMIN_DATABASE_URL
```

Aynı hesaba tekrar atama aynı kişi kimliğini döndürür; başka hesaba devretme reddedilir.
Başarılı ilk atama insan kimliği ve operatör audit'i tek transaction'dır. Yönetim DSN'ini
API/web container'ına veya kalıcı runtime `.env` dosyasına koymayın.

### Yetki sözleşmesi

- API **asimetrik ES256/RS256** JWT imzasını, issuer/audience/süreyi doğrular; metadata'ya güvenmez.
  Eski HS256 proje anahtarı fallback'i yoktur. `CCE_AUTH_ISSUER` token'daki dış issuer ile
  aynı olmalı; `CCE_AUTH_JWKS_URL` API'nin eriştiği güvenilir JWKS adresidir.
- Her yetki kontrolünde **güncel Auth hesabı, session kaydı ve Owner ataması** ayrıca doğrulanır.
  Logout sonrası eski access token kabul edilmez. Saat farkına yalnız 5 saniye tolerans tanınır;
  imza, süre ve güncel session kontrolleri atlanmaz.
- Owner komutları için **ayrı `CCE_ENGINE_DATABASE_URL`** gerekir; aynı DB'deki sınırlı
  `cce_engine` rolünü kullanır, `cce_api` bu role geçemez. Mevcut kurulumda güncel
  migration'dan sonra `scripts/setup_local_db.py`'yi yeniden çalıştırın.
- Supabase Auth şema grant'lerini özel rollere devretmeye izin vermediğinden yalnız
  `current_identity` ve `bootstrap_world_owner` Auth köprüleri migration runner `postgres`
  sahipliğindedir: private, sabit `search_path`'li, dar kapsamlı `SECURITY DEFINER` fonksiyonlar.
  Uygulama tabloları `cce_migrator` sahipliğinde ve **FORCE RLS**'lidir.
- Lokal config'te e-posta onayı kapalıdır. Cloud/beta için e-posta sağlayıcısı ve gerçek
  teslim/recovery testleri **M8** kapısındadır. PKCE dönüş yolu `/auth/callback`'tir; cloud
  ortamında `CCE_WEB_ORIGIN`, Auth Site URL ve redirect allowlist birlikte ayarlanmalıdır.
  **Üretimde yerel onaysız kayıt ayarını kopyalamayın.**

---

## 🛡️ Moderasyon worker

İnceleme başlatıldığında kalıcı bir moderasyon işi oluşur; Owner `PENDING`, `RUNNING` ve hata
durumunu görür. `cce-moderation-worker` ayrı bir CLI başlatıcısıdır ve **yalnız
`cce_worker_cpu`** veritabanı kimliğini kabul eder.

```powershell
$env:CCE_ENVIRONMENT                          = "local"
$env:CCE_WORKER_DATABASE_URL                  = "postgresql+psycopg://cce_worker_cpu:<parola>@127.0.0.1:54322/postgres"
$env:CCE_STORAGE_URL                          = "http://127.0.0.1:54321"
$env:CCE_SUPABASE_PUBLISHABLE_KEY             = "<publishable key>"
$env:CCE_MODERATION_AUTH_USER_ID              = "<worker hesabı UUID>"
$env:CCE_MODERATION_AUTH_EMAIL                = "<worker@…>"
$env:CCE_MODERATION_AUTH_PASSWORD             = "<güçlü parola>"
$env:CCE_MODERATION_SCANNER_FACTORY           = "paket.modul:fabrika"
$env:CCE_MODERATION_STARTUP_SECONDS           = "120"
$env:CCE_MODERATION_TIMEOUT_SECONDS           = "120"
uv run --project services/backend cce-moderation-worker
```

`CCE_MODERATION_SCANNER_FACTORY`, private avatar okuyucusunu alan bir **scanner fabrikasıdır**.
Repo henüz gerçek scanner fabrikası sunmaz. Compose'taki `moderation-worker` profili
isteğe bağlıdır; normal `docker compose up` worker'ı başlatmaz. Yalnız worker'a ait
[ortam şablonu](.env.moderation.example) ve [servis işletim adımları](docs/MODERATION_WORKER_RUNBOOK.md)
hazırdır; gerçek adapter imajı/model kabulü olmadan profili etkinleştirmeyin.
Yapılandırılmamış scanner iş kuyruğunu tüketmez — **test fixture'larını gerçek içerik
için scanner olarak yapılandırmayın.**

Scanner ayrı, sıcak tutulan bir `spawn` process'inde çalışır. Hazır olmadan iş alınmaz;
tarama timeout'u child'ı sonlandırır ve denemeyi `MODEL_TIMEOUT` yapar. Tarama sınırı
en fazla 240 saniyedir (lease 300 saniye). Yeni process sonraki claim'den önce hazırlanır;
hatalı işin retry'ı yine Owner kararıdır. [İşletim ve açık runtime sınırları](docs/MODERATION_WORKER_RUNBOOK.md).

### Worker Auth hesabı

Yalnız güvenilir Supabase yönetim aracıyla oluşturulmuş, e-postası onaylı **ayrı** bir
kullanıcı olmalıdır; yöneticisi `app_metadata.cce_role` değerini `moderation_worker` olarak
atamalıdır. Bu metadata kullanıcı tarafından değiştirilemez. Şifre/JWT ve servis anahtarı
repoya veya web ortamına konmaz. Worker hesabı CCE uygulama kimliği **değildir**.

### Storage sınırı

Storage politikası yalnız kendisine atanmış `RUNNING` işin, geçerli lease'li, güncel inceleme
revizyonundaki avatarına authenticated GET izni verir; listeleme/yazma izni vermez. Worker DB
bağlantısı kapandıktan sonra bu hesabın kısa ömürlü JWT'siyle dosyayı indirir, 512 KiB
sınırını ve kayıtlı SHA-256'yı doğrular. İzin/okuma/doğrulama hatası onayı açmaz. CLI
başlarken yapılandırılmış Auth hesabına giriş yapıp kullanıcı kimliğini doğrular; bu
doğrulama başarısızsa scanner yüklenmez ve kuyruktan iş alınmaz.

> [!IMPORTANT]
> Bu Storage sınırı için izole veritabanı ve gerçek Auth/Storage entegrasyon testi GitHub
> CI'da ve izole yerel yığında geçti. Process timeout sınırı uygulandı; gerçek metin/görsel
> model, dış runtime cancellation, servis kurulumu ve hedef makine kabulü açıktır;
> bunlar bitmeden moderasyon sonucu **gerçek onay veya aktivasyon kanıtı değildir**.

---

## 🧪 Doğrulama

### Günlük kontroller

```powershell
uv run --project services/backend ruff check services/backend scripts
uv run --project services/backend ruff format --check services/backend scripts
uv run --project services/backend mypy --config-file services/backend/pyproject.toml services/backend/src
uv run --project services/backend pytest services/backend/tests -m 'not integration'
pnpm contract:generate
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

API ve production web sunucusu (`pnpm --filter @cce/web start`) çalışırken uçtan uca kontrol:

```powershell
uv run --project services/backend python scripts/check_health.py
```

### Gerçek yerel DB testleri

```powershell
$env:CCE_ENVIRONMENT = "test"
uv run --project services/backend python scripts/setup_local_db.py
$localStatus = pnpm exec supabase status -o json | ConvertFrom-Json
$env:CCE_TEST_SUPABASE_PUBLISHABLE_KEY = $localStatus.PUBLISHABLE_KEY
$env:CCE_TEST_STORAGE_ADMIN_KEY = $localStatus.SERVICE_ROLE_KEY
pnpm exec supabase test db --local
pnpm exec supabase db lint --local --level error --fail-on error
uv run --project services/backend pytest services/backend/tests -m integration
```

WSL Docker için yukarıdaki Supabase komutlarını Linux CLI ile çalıştırın. Fixture script'i
yalnız sabit loopback DB'ye ve açık `local`/`test` ortamında bağlanır. pgTAP testleri
transaction sonunda geri alınır. Python integration testleri API ve CPU-worker kimlikleriyle
gerçek bağlantı kurarak rol sınırlarını doğrular.

> [!CAUTION]
> Kimlik testleri geçici Auth hesapları oluşturur ve yalnız kendi hesaplarını temizler.
> **Owner bootstrap testi gerçek Owner atanmış bir DB'de çalıştırılmamalıdır**; bu durumda
> test güvenli biçimde başarısız olur. Ayrı bir test DB kullanın.

<details>
<summary><b>🧬 Gerçek Owner hesabını koruyan ayrı test yığını</b></summary>

Günlük kullanılan `cce-local` veritabanında Owner testlerini çalıştırmayın veya reset
yapmayın. İkinci yığın `cce-integration`, Auth `55321` ve DB `55322` portlarını kullanır:

```powershell
New-Item -ItemType Directory -Force .artifacts/integration/supabase | Out-Null
Copy-Item infrastructure/testing/supabase/config.toml .artifacts/integration/supabase/config.toml
Copy-Item supabase/migrations .artifacts/integration/supabase -Recurse -Force
Copy-Item supabase/tests .artifacts/integration/supabase -Recurse -Force
pnpm exec supabase start --workdir .artifacts/integration --exclude studio,imgproxy,edge-runtime,logflare,vector
pnpm exec supabase migration up --workdir .artifacts/integration --local
$env:CCE_ENVIRONMENT = "test"
$env:CCE_ISOLATED_TEST_STACK = "1"
uv run --project services/backend python scripts/setup_local_db.py --isolated-test-stack
$localStatus = pnpm exec supabase status --workdir .artifacts/integration -o json | ConvertFrom-Json
$env:CCE_TEST_SUPABASE_PUBLISHABLE_KEY = $localStatus.PUBLISHABLE_KEY
$env:CCE_TEST_STORAGE_ADMIN_KEY = $localStatus.SERVICE_ROLE_KEY
uv run --project services/backend pytest services/backend/tests
pnpm exec supabase test db --workdir .artifacts/integration --local
```

WSL-only Docker'da CLI için Linux önekini kullanın. Migration/test değişince kopyaları
yenileyin; kaynak daima kökteki `supabase/migrations` ve `supabase/tests` olur. Bu testler
yalnız kendi rastgele hesaplarını temizler; **Owner hesabını devretmez.**

`CCE_TEST_STORAGE_ADMIN_KEY` yalnız disposable yerel testlerin oluşturduğu dosyaları
temizlemek içindir; uygulama runtime'ına, web'e veya herhangi bir `NEXT_PUBLIC_` değişkenine
verilmez. Fixture yalnız kendi rastgele kullanıcılarının kayıtlı object path'lerini Storage
API üzerinden siler; bucket veya veritabanını sıfırlamaz.

</details>

<details>
<summary><b>🌐 İnceleme tarayıcı testi (izole yığın)</b></summary>

API/web'i aynı test yığınına bağlayın.

- **API:** port `8001`, `CCE_ENVIRONMENT=test`, API/engine DSN'leri `55322`,
  Auth issuer/JWKS `55321`, `CCE_STORAGE_URL=http://127.0.0.1:55321`, test publishable key.
- **Web:** port `3101`, `CCE_API_BASE_URL=http://127.0.0.1:8001`,
  `CCE_SUPABASE_URL=http://127.0.0.1:55321`, test publishable key,
  `CCE_WEB_ORIGIN=http://127.0.0.1:3101`.

```powershell
$env:CCE_E2E_REVIEW = "1"
$env:CCE_E2E_BASE_URL = "http://127.0.0.1:3101"
uv run --project services/backend pytest services/backend/tests/test_review_integration.py -k browser
```

Python fixture'ı iki geçici hesabı/Owner'ı oluşturur, browser'a yalnız proses ortamıyla
iletir ve test sonunda temizler. CI aynı akışı boş `54321`/`54322` yığınında otomatik
çalıştırır. Ayrı normal tarayıcı testinde bu fixture testi atlanır.

</details>

<details>
<summary><b>🖼️ Private avatar yüklemeleri ve e2e</b></summary>

Kaydedilmiş taslağa PNG/JPEG/WebP yüklenebilir: girdi ve normalize çıktı en fazla 512 KiB,
boyutlar 32–2048 piksel, tek kare. Backend dosyayı decode eder, metadata'yı atar ve yeni PNG
üretir. SVG/HTML, MIME uyumsuzluğu ve animasyon reddedilir. **Bu teknik doğrulama içerik
moderasyonu değildir**; sağlayıcı hem metni hem referanslanan immutable avatarı taramalı ve
sonucu aynı revizyona bağlamalıdır.

`cce-avatars` bucket'ı public değildir. Backend Storage'a kullanıcının doğrulanmış JWT'si
ve publishable key ile erişir; runtime service key kullanmaz. Kullanıcı yalnız kendi
ayrılmış path'ine ekleyebilir; overwrite/delete izni yoktur. Görseller same-origin
`/media/{id}` üzerinden auth kontrollü, `no-store` ve `nosniff` sunulur.

Yükleme `PENDING → READY` rezervasyonu, sabit upload key ve SHA-256 doğrulamasıyla tekrar
denenebilir. Storage çağrısında DB kilidi tutulmaz. Kullanıcı başına 24 saatte 20 ve toplam
100 rezervasyon sınırı vardır; yarım kalan yüklemeler de kotaya dahildir. **Otomatik orphan
temizliği henüz yoktur.**

```powershell
pnpm --filter @cce/web exec playwright install chromium
pnpm --filter @cce/web test:e2e
```

Windows'ta kurulu Edge kullanılacaksa indirme yerine `$env:CCE_BROWSER_CHANNEL = "msedge"`
ayarlayın. E2E rastgele `cce-e2e-…@example.com` test hesabıyla kayıt, taslak/gönderim/geri
çekme, SSR cookie, refresh/reload, admin reddi, giriş ve çıkışı doğrular; yerelde bu deneme
hesabı kalır, gerçek kullanıcıya ait değildir.

</details>

<details>
<summary><b>♻️ Temiz migration tekrarı (yalnız disposable lokal DB)</b></summary>

```powershell
docker stop supabase_realtime_cce-local supabase_auth_cce-local supabase_storage_cce-local supabase_pg_meta_cce-local supabase_rest_cce-local
pnpm exec supabase db reset --local --yes
docker start supabase_realtime_cce-local supabase_auth_cce-local supabase_storage_cce-local supabase_pg_meta_cce-local supabase_rest_cce-local
$env:CCE_ENVIRONMENT = "local"
uv run --project services/backend python scripts/setup_local_db.py
```

CLI 2.117.0 ile çalışan servisler reset sırasında platform migration'larıyla yarışıp
`schema_migrations_pkey` çakışması oluşturabilir; bu nedenle reset öncesi yalnız bu projeye
ait DB tüketicileri durdurulur. WSL-only Docker'da `docker` komutlarına da
`wsl -d Ubuntu-24.04 --` öneki eklenir.

> **Bu komut lokal `cce-local` verisini siler.** Gerçek/veri korunacak ortamlarda reset yerine
> migration hattını kullanın. Servisleri veriyi koruyarak durdurmak için `pnpm db:stop`.

</details>

---

## 🗄️ Veri modeli ve güvenlik

- `public` **tek exposed uygulama şemasıdır**; `world_private` ve `ops_private` Data API'ye açılmaz.
- `cce_migrator` uygulama nesnelerinin NOLOGIN sahibidir; migration runner `postgres` bu role geçebilir.
  **API `cce_api` ile çalışır ve migration credential'ını kabul etmez.**
- Engine ve dört worker rolü (`cce_engine`, `cce_worker_cpu`, …) ayrıdır; yeni özellikler kendi
  grant/RLS kurallarını migration içinde ekler.
- `world_private.character_definitions` Data API'ye kapalıdır. `cce_engine` yalnız güncel Owner
  bağlamıyla okuyup ekleyebilir; UPDATE/DELETE ve worker erişimi yoktur.
- Revizyon, Owner onayı, reviewer, moderasyon politika/sağlayıcı bilgisi ve avatar kimliği/hash'i
  birlikte sabitlenir. Canonical JSON SHA-256'sı okuma sırasında doğrulanır; DB trigger'ı
  artifact'ın kaynağını gerçek onay/revizyonla eşleştirir.
- `definition_version` kaynak revizyon sırasıdır; **henüz canlı karakter sürüm pointer'ı değildir**.
  Şema `1`, derleyici `definition-v1`, prompt `character-v1`, türetme `bootstrap-v1` ile sürümlüdür.
  Aynı revizyonun eşzamanlı/retry derlemesi aynı ID/hash'i döndürür.
- **Yeni migration:** `pnpm exec supabase migration new <name>`. Tek şema tarihçesi
  `supabase/migrations` altındadır. Yeni public tablolarda açık grant ve RLS zorunludur.
  Local fixture credential'ları migration'a dahil değildir.

### Başvuru ve aktivasyon kuralları

- Güncellemeler **beklenen sürümle** yapılır; eski sürüm `409` döndürür. Oluşturma kimliği aynı
  içerikle yinelendiğinde aynı taslağı döndürür.
- Katkıcı başına aktif veya son 24 saatte oluşturulmuş kayıtların birleşimi en fazla **10**'dur.
- Gönderim ve audit atomiktir; **geri çekilen başvuru yeniden açılmaz.** Değişiklik talebinden
  sonra katkıcı yeni bir taslak açıp yeni immutable revizyon gönderebilir; eski gönderim ve
  feedback korunur.
- Başlangıç affect adayı baseline'a eşittir (`bootstrap-v1` geçici teknik tarifi:
  `V=(warmth−50)/125`, `A=(sociability−50)/125`, `D=(assertiveness−50)/125`, aralık ±0.4).
  Bunlar psikolojik ölçüm veya tamamlanmış kalibrasyon **değildir**; politika değişimi açık sürüm
  değişikliği gerektirir ve mevcut tanımların baseline'ı otomatik değişmez.
- Backstory ve geçmiş olayları **background adaylarıdır**, commit edilmiş yaşanmış deneyim değildir.

---

## ✅ CI

**Foundation CI** (`main` ve PR, `ubuntu-24.04`) şunları çalıştırır:

- Backend lint / format / typecheck (mypy strict) / birim testler
- Frontend lint / typecheck / test / production build
- OpenAPI drift kontrolü ve iki container build'i
- Boş lokal Supabase üzerinde migration, pgTAP ve **gerçek rol** testleri
- Gerçek veritabanı + Auth entegrasyon testleri, Playwright smoke ve web → API → DB testi
- İzole moderasyon Auth/Storage entegrasyonu

Başarısız adımların ayrıntısı GitHub **check annotation** olarak yayınlanır; ham log
sayfası oturum ister, annotation'lar istemez. Migration ve entegrasyon hataları bu
yüzden giriş yapmadan okunabilir.

Workflow **production deploy yapmaz**. Tamamlanma ve kalan işler
[implementation plan](IMPLEMENTATION_PLAN.md) ilerleme kaydında tutulur.

---

## 📚 Dokümanlar

| Belge | İçerik |
| :-- | :-- |
| [WORLD_ARCHITECTURE_DECISIONS.md](WORLD_ARCHITECTURE_DECISIONS.md) | Ürün davranışının source of truth'u; WADR-001…014 |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Aşamalar, kabul kanıtları, açık işler |
| [M1 raporu](docs/M1_FOUNDATION_REPORT.md) | Foundation: zemin, roller, kanıt ve ne demek değil |
| [M2 raporu](docs/M2_IDENTITY_AND_CONTRIBUTIONS_REPORT.md) | Kimlik, katkı ve inceleme hattı |
| [Adversarial inceleme](docs/ADVERSARIAL_REVIEW_2026-10-01.md) | Karşıdan güvenlik taraması; çürütülen iddialar işaretli |
| [M3.5–M3.6 sürüm notu](docs/RELEASE_NOTES_2026-10-02_M3_5.md) | Definition benisleme, Owner görünümü, uzlaştırma kararı |
| [Hata desenleri](docs/DEFECT_PATTERNS.md) | M4 boyunca tekrar eden hata sınıfları ve her biri için eklenen önlem |
| [AGENTS.md](AGENTS.md) | Ajan çalışma kuralları ve repo bağlamı (`graft`) |

### Teknik dayanaklar

- [Next.js kurulum ve Node gereksinimleri](https://nextjs.org/docs/app/getting-started/installation)
- [Next.js standalone image çıktısı](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
- [Supabase CLI yerel kurulum](https://supabase.com/docs/guides/local-development/cli/getting-started)
- [Supabase config](https://supabase.com/docs/guides/local-development/cli/config)
- [Supabase Postgres rolleri](https://supabase.com/docs/guides/database/postgres/roles)
- [uv kilitli kurulum](https://docs.astral.sh/uv/concepts/projects/sync/)
- [SQLAlchemy psycopg adapter](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)

---

<div align="center">

<sub>
Bu repo erken aşamadadır. Fixture'lar, sentetik verdict'ler ve geçen testler
gerçek moderasyon ya da aktivasyon kanıtı <strong>değildir</strong>.
</sub>

</div>
