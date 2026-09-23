# Cognitive Character Engine

Kalıcı AI karakterlerin ortak dünyası. Ürün davranışı için
[mimari kararlar](WORLD_ARCHITECTURE_DECISIONS.md), çalışma sırası için
[implementation plan](IMPLEMENTATION_PLAN.md) esas alınır.

M1, Next.js → FastAPI → yerel Supabase health akışını kurar. Karakter, sohbet ve
model entegrasyonları sonraki milestone'larda eklenecek.

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
pnpm exec supabase test db --local
pnpm exec supabase db lint --local --level error --fail-on error
uv run --project services/backend pytest services/backend/tests -m integration
```

WSL Docker için yukarıdaki Supabase komutlarını Linux CLI ile çalıştır. Fixture
script'i sadece sabit loopback DB'ye ve açık `local`/`test` ortamında bağlanır.
pgTAP testleri transaction sonunda geri alınır. Python integration testleri API ve
CPU-worker kimlikleriyle gerçek bağlantı kurarak rol sınırlarını doğrular.

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
