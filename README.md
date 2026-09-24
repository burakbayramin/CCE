# Cognitive Character Engine

Kalıcı AI karakterlerin ortak dünyası. Ürün davranışı için
[mimari kararlar](WORLD_ARCHITECTURE_DECISIONS.md), çalışma sırası için
[implementation plan](IMPLEMENTATION_PLAN.md) esas alınır.

M1, Next.js → FastAPI → yerel Supabase health akışını kurar. Karakter, sohbet ve
model entegrasyonları sonraki milestone'larda eklenecek.

M2'nin ilk dilimi `/signup`, `/login`, `/contributor` ve `/admin` yollarını ekler.
`/contributor/drafts` üzerinden yapılandırılmış taslak, kaydedilmiş ön izleme,
değiştirilemez başvuru gönderimi ve geri çekme çalışır. `/admin/reviews` üzerinden
Owner incelemesi, gerekçeli değişiklik talebi/ret, revizyon farkları ve onay kapısı
vardır. Katkıcı değişiklik talebinden sonra yeni taslak açıp yeni immutable revizyon
gönderebilir; eski gönderim ve feedback korunur. Medya yükleme henüz uygulanmadı.
Bu dilim canlı karakter oluşturmaz ve gerçek otomatik moderasyon henüz yapılandırılmadı;
public contributor açılışı için hazır değildir.

Yapılandırılmamış tarama `ERROR` gösterir ve onayı engeller; Owner değişiklik
isteyebilir veya gerekçeli ret verebilir. `PASS`/`REVIEW`/`BLOCK` sağlayıcı fixture'ları
yalnız test uygulamasına enjekte edilir ve UI'da etiketlenir. `BLOCK`/`ERROR`
override edilemez; `REVIEW` için açık olumlu karar gerekir. Onaylanan test revizyonu
gerçek moderasyon kanıtı değildir; M3 aktivasyon kapısı gerçek taramayı zorunlu tutacaktır.

Güncellemeler beklenen sürümle yapılır; eski sürüm 409 döndürür. Oluşturma kimliği
aynı içerikle yinelendiğinde aynı taslağı döndürür. Katkıcı başına aktif veya son
24 saatte oluşturulmuş kayıtların birleşimi en fazla 10'dur. Gönderim ve audit
atomiktir; geri çekilen başvuru yeniden açılmaz.

## Araçlar

| Araç | Sabitlenen sürüm |
| --- | --- |
| Python | 3.13.3 (`.python-version`) |
| Node.js | 22.15.0 (`.node-version`) |
| uv | 0.10.3 (CI ve backend image) |
| pnpm | 10.13.1 (`packageManager`) |
| Supabase CLI | 2.117.0 (repo bağımlılığı) |
| PostgreSQL | 17 (Supabase CLI image'ı) |

Docker uyumlu çalışan bir daemon gerekir. Bu oturumda Windows araçları ile WSL2
Ubuntu 24.04 içindeki Docker kullanıldı; geliştirme makinesinin GTX 1050 GPU'su,
WADR'deki hedef RTX 3070 AI makinesinden farklıdır. M1 GPU gerektirmez.
Python/JS paketlerinin kesin sürümleri `services/backend/uv.lock` ve
`pnpm-lock.yaml` içindedir. Komutlar aksi belirtilmedikçe repo kökünden çalıştırılır.

## İlk kurulum

```powershell
pnpm install --frozen-lockfile
uv sync --project services/backend --locked
Copy-Item .env.example .env
Copy-Item apps/web/.env.example apps/web/.env.local
```

Mevcut `.env` dosyaların varsa kopyalama adımlarını atla. Örnek bağlantı bilgileri
yalnız yerel test fixture'larıdır. Gerçek credential'ları migration'a veya
`NEXT_PUBLIC_*` değişkenlerine koyma.

Docker aynı shell'den erişilebiliyorsa:

```powershell
pnpm exec supabase start --exclude studio,imgproxy,edge-runtime,logflare,vector
pnpm db:migrate
$env:CCE_ENVIRONMENT = "local"
uv run --project services/backend python scripts/setup_local_db.py
```

`start` boş veritabanına migration'ları uygular. `db:migrate` sonraki pending
migration'ları uygular. Studio dahil tam yerel stack için `pnpm db:start` kullan.
Bu repo cloud Supabase projesine bağlı değildir.

### Docker yalnız WSL'deyse

Windows Supabase executable'ı Linux Docker socket'ine doğrudan bağlanamaz. Linux
CLI'yi repo altındaki ignored `.artifacts` klasörüne bir kez indir:

Önce ayrı bir terminalde `wsl -d Ubuntu-24.04` açıp açık bırak. Bu makinede son WSL
oturumu kapandığında dağıtım ve Docker da duruyor; yalnız systemd servisleri WSL'yi
ayakta tutmuyor. Dağıtım yeniden açılırken geçici DB bağlantı hatası görülebilir.

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'mkdir -p .artifacts/cli-linux && curl -fsSL https://github.com/supabase/cli/releases/download/v2.117.0/supabase_linux_amd64.tar.gz -o .artifacts/cli-linux/supabase.tar.gz && tar -xzf .artifacts/cli-linux/supabase.tar.gz -C .artifacts/cli-linux'
wsl -d Ubuntu-24.04 -- .artifacts/cli-linux/supabase --version
wsl -d Ubuntu-24.04 -- .artifacts/cli-linux/supabase start --exclude studio,imgproxy,edge-runtime,logflare,vector
wsl -d Ubuntu-24.04 -- .artifacts/cli-linux/supabase migration up --local
$env:CCE_ENVIRONMENT = "local"
uv run --project services/backend python scripts/setup_local_db.py
```

Diğer `pnpm exec supabase …` komutlarının yerine aynı Linux CLI önekini kullan.
API ve web Windows'ta çalışabilir; DB'ye `127.0.0.1:54322` üzerinden erişirler.
Bu düzen Linux node_modules veya Python ortamını Windows ortamıyla paylaşmaz.

## Çalıştırma

İki ayrı terminalde:

```powershell
pnpm dev:api
```

```powershell
pnpm dev:web
```

- Web: <http://127.0.0.1:3100>
- Liveness: <http://127.0.0.1:8000/health/live>
- Readiness: <http://127.0.0.1:8000/health/ready>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

Liveness DB kapalıyken de 200 verir. Readiness bağlantı, kısıtlı API kimliği ve
migration marker'ını doğrular; başarısızsa 503 verir. Web bu durumu başarılı gibi
göstermez. İstek kimliği web ve API JSON loglarında aynıdır; URL/query, token,
cookie, body ve ham exception içerikleri bu loglara alınmaz.

`WorldClock` yalnız test edilebilir bir domain arayüzüdür. Kalıcı dünya saati M5'te
uygulanır; operasyon süreleri `perf_counter` ve bağlantı timeout'larını kullanır.

### Container akışı

Önce yerel Supabase ve fixture kurulumu tamamlanır, sonra:

```powershell
docker compose up --build -d
docker compose ps
docker compose down
```

WSL-only Docker'da önek `wsl -d Ubuntu-24.04 -- docker compose …` olur.
Compose yalnız web/API'yi yönetir; DB'yi Supabase CLI yönetir. Aynı portlarda yerel
dev sunucuları çalışıyorsa önce onları durdur. Image'lar non-root kullanıcıyla
çalışır. `host.docker.internal` yerel PostgreSQL erişimi içindir.

## Doğrulama

### M2 kimlik kurulumu

Yerel Supabase başlatıldıktan sonra `supabase status -o json` çıktısındaki yalnız
`PUBLISHABLE_KEY` değerini `apps/web/.env.local` içindeki
`CCE_SUPABASE_PUBLISHABLE_KEY` alanına koy; `CCE_SUPABASE_URL=http://127.0.0.1:54321`
olmalı. Compose için aynı publishable değişkenini kökteki ignored `.env` içine koy.
Secret/service-role anahtarı kullanılmaz. Auth yapılandırması eksikse health ekranı
çalışır, giriş ekranı açıkça yapılandırma eksikliğini gösterir.

Önce `/signup` üzerinden kendi hesabını oluştur. Bütün yeni hesaplar katkıcıdır;
metadata'daki rol alanı dikkate alınmaz. Portal hesap UUID'sini gösterir. Owner
ataması yalnız operatör terminalinden, gerçek hesabın UUID'siyle yapılır:

```powershell
$env:CCE_ADMIN_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
uv run --project services/backend python scripts/bootstrap_owner.py --user-id <hesap-uuid> --display-name "<dünya içi ad>" --operator "<işlemi yapan operatör>" --reason "İlk World Owner kurulumu"
Remove-Item Env:CCE_ADMIN_DATABASE_URL
```

Bu örnekteki credential yalnız yerel Supabase içindir. Yönetim DSN'ini API/web
container'ına veya kalıcı runtime `.env` dosyasına koyma. Aynı hesaba tekrar atama
aynı kişi kimliğini döndürür; başka hesaba devretme reddedilir. Başarılı ilk atama,
insan kimliği ve operatör audit'i tek transaction'dır. Bu oturumda gerçek Owner
hesabı seçilmedi; test atamaları yalnız geçici test hesaplarında denendi.

API asimetrik ES256/RS256 JWT imzasını, issuer/audience/süreyi doğrular; metadata'ya
güvenmez. `CCE_AUTH_ISSUER` token'daki dış issuer ile aynı olmalı;
`CCE_AUTH_JWKS_URL` API'nin eriştiği güvenilir JWKS adresidir. Eski HS256 proje
anahtarı fallback'i yoktur. Her yetki kontrolünde güncel Auth hesabı, session kaydı
ve Owner ataması ayrıca doğrulanır. Logout sonrası eski access token kabul edilmez.
Auth/API saat farkına yalnız 5 saniyelik tolerans tanınır; imza, süre ve güncel
session kontrolleri atlanmaz. Owner komutları için ayrı `CCE_ENGINE_DATABASE_URL`
gerekir; aynı DB'deki sınırlı `cce_engine` rolünü kullanır, `cce_api` bu role geçemez.
Mevcut yerel kurulumda güncel migration'dan sonra `scripts/setup_local_db.py`'yi
yeniden çalıştır; yeni engine fixture credential'ını yalnız backend ortamına ekle.
Supabase rehberindeki ayrı grant/RLS sınırları uygulanır ve Owner işleminde gerçek
actor, gerekçe, incelenen revizyon ve sonuç sürümü atomik audit'e yazılır.

Supabase Auth şema grant'lerini özel rollere devretmeye izin vermediğinden yalnız
`current_identity` ve `bootstrap_world_owner` Auth köprüleri migration runner
`postgres` sahipliğindedir. Bunlar private, sabit search_path'li, dar kapsamlı
SECURITY DEFINER fonksiyonlardır. API yalnız ilkini çağırabilir; bootstrap yalnız
operatöre açıktır. Uygulama tabloları `cce_migrator` sahipliğinde ve FORCE RLS'lidir.

Yerel config'te e-posta onayı kapalıdır; cloud/beta e-posta sağlayıcısı ve gerçek
teslim/recovery testleri M8 kapısında kalır. PKCE dönüş yolu `/auth/callback`'tir;
cloud ortamında `CCE_WEB_ORIGIN`, Auth Site URL ve redirect allowlist birlikte
ayarlanmalıdır. Config değişiklikleri için yerel Supabase'i veriyi koruyarak
yeniden başlat. Üretimde yerel onaysız kayıt ayarını kopyalama.

### Otomatik kontroller

```powershell
uv run --project services/backend ruff check services/backend scripts
uv run --project services/backend ruff format --check services/backend scripts
uv run --project services/backend mypy services/backend/src
uv run --project services/backend pytest services/backend/tests -m 'not integration'
pnpm contract:generate
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

API ve production web sunucusu (`pnpm --filter @cce/web start`) çalışırken uçtan
uca kontrol: `uv run --project services/backend python scripts/check_health.py`.

OpenAPI'den üretilen `schema.d.ts` elle düzenlenmez; CI yeniden üretip farkı kontrol
eder. Şema tüketimi ve HTTP hata durumları frontend testlerinde sınanır.

Gerçek yerel DB testleri:

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

WSL Docker için yukarıdaki Supabase komutlarını Linux CLI ile çalıştır. Fixture
script'i sadece sabit loopback DB'ye ve açık `local`/`test` ortamında bağlanır.
pgTAP testleri transaction sonunda geri alınır. Python integration testleri API ve
CPU-worker kimlikleriyle gerçek bağlantı kurarak rol sınırlarını doğrular.

Kimlik testleri geçici Auth hesapları oluşturur ve yalnız kendi hesaplarını
temizler. Owner bootstrap testi gerçek Owner atanmış bir DB'de çalıştırılmamalıdır;
bu durumda test güvenli biçimde başarısız olur. Ayrı test DB kullan.

### Gerçek Owner hesabını koruyan ayrı test stack'i

Günlük kullanılan `cce-local` veritabanında Owner testlerini çalıştırma veya reset yapma.
İkinci stack `cce-integration`, Auth 55321 ve DB 55322 portlarını kullanır:

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

WSL-only Docker'da CLI için yukarıdaki Linux önekini kullan. Migration/test değişince
kopyaları yenile; kaynak daima kökteki `supabase/migrations` ve `supabase/tests` olur.
Bu testler yalnız kendi rastgele hesaplarını temizler; Owner hesabını devretmez.
`CCE_TEST_STORAGE_ADMIN_KEY` yalnız disposable yerel testlerin oluşturduğu dosyaları
temizlemek içindir; uygulama runtime'ına, web'e veya herhangi bir `NEXT_PUBLIC_`
değişkenine verilmez. Fixture yalnız kendi rastgele kullanıcılarının kayıtlı object
path'lerini Storage API üzerinden siler; bucket veya veritabanını sıfırlamaz.

İnceleme tarayıcı testi için API/web'i aynı test stack'ine bağla. API örneği: port
8001, `CCE_ENVIRONMENT=test`, API/engine DSN'leri 55322, Auth issuer/JWKS 55321,
`CCE_STORAGE_URL=http://127.0.0.1:55321` ve test publishable key;
web örneği: port 3101, `CCE_API_BASE_URL=http://127.0.0.1:8001`,
`CCE_SUPABASE_URL=http://127.0.0.1:55321`, test publishable key ve
`CCE_WEB_ORIGIN=http://127.0.0.1:3101`. Ardından `CCE_E2E_REVIEW=1` ve
`CCE_E2E_BASE_URL=http://127.0.0.1:3101` ile
`pytest services/backend/tests/test_review_integration.py -k browser` çalıştır.
Python fixture'ı iki geçici hesabı/Owner'ı oluşturur, browser'a yalnız proses
ortamıyla iletir ve test sonunda temizler. CI aynı akışı boş 54321/54322 stack'inde
otomatik çalıştırır. Ayrı normal tarayıcı testinde bu fixture testi atlanır.

### Private avatar önerileri

Kaydedilmiş taslağa PNG/JPEG/WebP yüklenebilir: girdi ve normalize çıktı en fazla
512 KiB, boyutlar 32–2048 piksel, tek kare. Backend dosyayı decode eder, metadata'yı
atar ve yeni PNG üretir. SVG/HTML, MIME uyumsuzluğu ve animasyon reddedilir. Bu
teknik doğrulama **içerik moderasyonu değildir**; M3 sağlayıcısı hem metni hem
referanslanan immutable avatarı taramalı ve sonucu aynı revizyona bağlamalıdır.

`cce-avatars` public değildir. Backend Storage'a kullanıcının doğrulanmış JWT'si ve
publishable key ile erişir; runtime service key kullanmaz. Kullanıcı yalnız kendi
ayrılmış path'ine ekleyebilir; overwrite/delete izni yoktur. Owner yetkisi ve
oturumun hâlâ geçerli oluşu Storage RLS içinde yeniden kontrol edilir. Görseller
same-origin `/media/{id}` üzerinden auth kontrollü, `no-store` ve `nosniff` sunulur.

Yükleme `PENDING → READY` rezervasyonu, sabit upload key ve SHA-256 doğrulamasıyla
tekrar denenebilir. Storage çağrısında DB kilidi tutulmaz; taslak sürümü değişirse
dosya bağlanmaz. Gönderim avatar kimliğini immutable revizyona kopyalar. Yeni
revizyon yeni bir dosya seçebilir; önceki dosyanın byte'ları/referansı değişmez.
Kullanıcı başına 24 saatte 20 ve toplam 100 rezervasyon sınırı vardır; yarım kalan
yüklemeler de kotaya dahildir. Otomatik orphan temizliği henüz yoktur.

API için `CCE_STORAGE_URL` ve `CCE_SUPABASE_PUBLISHABLE_KEY` ayarla. Compose mevcut
root publishable key'i API/web'e geçirir. Sağlayıcı eksikse onay `ERROR` nedeniyle
kapalı kalır; sadece dosya doğrulamasından geçmek karakter onayı/aktivasyonu değildir.

Web/API çalışırken tarayıcı testi:

```powershell
pnpm --filter @cce/web exec playwright install chromium
pnpm --filter @cce/web test:e2e
```

Windows'ta kurulu Edge kullanılacaksa indirme yerine
`$env:CCE_BROWSER_CHANNEL = "msedge"` ayarla. E2E, rastgele `cce-e2e-…@example.com`
test hesabıyla kayıt, taslak/gönderim/geri çekme, SSR cookie, refresh/reload, admin reddi, giriş ve çıkışı
doğrular; yerelde bu deneme hesabı kalır, gerçek kullanıcıya ait değildir.

Temiz migration tekrarı yalnız bu projeye ayrılmış disposable yerel DB üzerinde:

```powershell
docker stop supabase_realtime_cce-local supabase_auth_cce-local supabase_storage_cce-local supabase_pg_meta_cce-local supabase_rest_cce-local
pnpm exec supabase db reset --local --yes
docker start supabase_realtime_cce-local supabase_auth_cce-local supabase_storage_cce-local supabase_pg_meta_cce-local supabase_rest_cce-local
$env:CCE_ENVIRONMENT = "local"
uv run --project services/backend python scripts/setup_local_db.py
```

CLI 2.117.0 ile çalışan servisler reset sırasında platform migration'larıyla
yarışıp `schema_migrations_pkey` çakışması oluşturabildi. Bu nedenle reset öncesi
yalnız bu projeye ait DB tüketicileri durdurulur, sonrasında yeniden başlatılır.
WSL-only Docker'da `docker` komutlarına da `wsl -d Ubuntu-24.04 --` öneki eklenir.

Bu komut yerel `cce-local` verisini siler. Gerçek/veri korunacak ortamlarda reset
yerine migration hattını kullan. Servisleri veriyi koruyarak durdurmak için
`pnpm db:stop` kullan.

## Veritabanı sınırları

`public` tek exposed uygulama şemasıdır; `world_private` ve `ops_private` Data API'ye
açılmaz. `cce_migrator` uygulama nesnelerinin NOLOGIN sahibidir; migration runner
`postgres` bu role geçebilir. API `cce_api` ile çalışır, migration credential'ını
kabul etmez. Engine ve dört worker rolü ayrıdır; yeni özellikler kendi grant/RLS
kurallarını migration içinde ekler. M1'de API sadece RLS korumalı schema marker'ını
okuyabilir; worker'lara henüz domain tablo yetkisi verilmez.

Yeni migration: `pnpm exec supabase migration new <name>`. Tek şema tarihçesi
`supabase/migrations` altındadır. Yeni public tablolarda açık grant ve RLS zorunludur.
Local fixture credential'ları migration'a dahil değildir; production provisioning
ve kimlik/yetki politikaları kendi milestone'larında kurulacaktır.

## CI

`Foundation CI`: backend lint/typecheck/unit test, frontend lint/typecheck/test/build,
OpenAPI drift, boş yerel Supabase migration/pgTAP/gerçek rol testleri ve iki container
build'i çalıştırır. Workflow production deploy yapmaz. Tamamlanma ve kalan işler
[implementation plan](IMPLEMENTATION_PLAN.md) ilerleme kaydında tutulur.

## Teknik dayanaklar

- [Next.js kurulum ve Node gereksinimleri](https://nextjs.org/docs/app/getting-started/installation)
- [Next.js standalone image çıktısı](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
- [Supabase CLI yerel kurulum](https://supabase.com/docs/guides/local-development/cli/getting-started)
- [Supabase config](https://supabase.com/docs/guides/local-development/cli/config)
- [Supabase Postgres rolleri](https://supabase.com/docs/guides/database/postgres/roles)
- [uv kilitli kurulum](https://docs.astral.sh/uv/concepts/projects/sync/)
- [SQLAlchemy psycopg adapter](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)
