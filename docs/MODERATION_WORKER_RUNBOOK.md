# Yerel moderasyon worker — işletim sınırları

Bu belge 2026-10-02 tarihli process supervisor dilimini kapsar. Gerçek metin/görsel
model seçimi, hedef GPU kabulü ve işletim sistemi servis kurulumu tamamlanmış değildir.
Fixture scanner'lar yalnız izole test içindir; production onayı veya aktivasyon açmaz.

## Başlatmadan önce

- Uygulama migration'ları ve API şeması aynı sürümde olmalı; bu dilim v5'i değiştirmez.
- DB kimliği yalnız `cce_worker_cpu`, Auth kimliği yalnız ayrı moderasyon hesabı olmalı.
  Avatar erişimi geçerli iş/deneme, atanmış hesap, kaynak revizyon ve hash ile sınırlıdır.
- README'deki worker ortamını hazırlayın. Parola/DSN/JWT'yi commit'e veya komut satırı
  argümanlarına koymayın; production secret'ları yerel fixture değerleri olamaz.
- `CCE_MODERATION_SCANNER_FACTORY`, avatar okuyucusunu alan, gözden geçirilmiş ve
  import edilebilir bir `paket.modul:fabrika` olmalı. Repo gerçek scanner sağlamaz.
- Scanner, çalışma sırasında hata/ham çıktı/token yazdırmamalı. Child stdout/stderr
  ayrıca atılır; sonuçlar yalnız doğrulanmış yapı ve sanitize edilmiş kodlarla saklanır.

## Süre sınırları

| Ortam değişkeni | Varsayılan | İzin verilen aralık | Kapsam |
| :-- | :-- | :-- | :-- |
| `CCE_MODERATION_STARTUP_SECONDS` | 120 sn | `0 < değer <= 600` | Spawn child'ının Auth kontrolü ve scanner fabrikası/model yüklemesi; henüz iş claim edilmez |
| `CCE_MODERATION_TIMEOUT_SECONDS` | 120 sn | `0 < değer <= 240` | Tek işin IPC, avatar okuma ve tarama süresi |
| `CCE_MODERATION_IDLE_SECONDS` | 2 sn | `0 < değer <= 60` | Kuyruk boşken bekleme |

NaN/sonsuz tarama ve başlangıç süresi reddedilir. Tarama üst sınırı 300 saniyelik
lease içinde process sonlandırma ve fenced sonuç commit'i için pay bırakır. Bu
bir model performans ölçümü değildir; hedef makinede bütçe ayrıca doğrulanmalıdır.

Worker CLI'ını `uv run --project services/backend cce-moderation-worker` ile
başlatın. Parent Auth kontrolünden sonra scanner ayrı `spawn` process'inde yüklenir.
Child kendi DB engine/avatar okuyucusunu oluşturur; parent pool'u devralmaz.
Scanner hazır olmadan claim yapılmaz. Sağlıklı child işler arasında sıcak tutulur;
aynı worker içinde iki tarama paralel çalıştırılmaz. Child model yüklemesi veya
inference sırasında parent claim transaction'ı açık kalmaz.

## Hata ve durdurma davranışı

| Durum | Sonuç / operatör adımı |
| :-- | :-- |
| Yanlış Auth hesabı / fabrikası, başlangıç hatası veya timeout | İş claim edilmez; süreç hata verir. Yapılandırmayı düzeltip CLI'ı yeniden başlatın. |
| Takılan tarama | Child terminate/kill ile sonlandırılır, eski pipe atılır; deneme `ERROR / MODEL_TIMEOUT` olur, onay kapalı kalır. |
| Child crash / erişim / çıktı hatası | Yalnız sanitize edilmiş `SCAN_FAILED`, `AVATAR_UNAVAILABLE` veya `INVALID_OUTPUT`; başarı varsayılmaz. |
| Timeout sonrası yeni işler | Yeni child yalnız bir sonraki claim'den önce hazırlanır. Başlangıç başarısızsa kuyruk tüketilmez. Hatalı iş otomatik retry edilmez. |
| Owner retry | Aynı kalıcı işte yeni deneme açılır; önceki ERROR/timeout geçmişi korunur. |
| `SIGINT` / `SIGTERM` | Idle bekleme veya aktif IPC kesilir, child sonlandırılır. Aktif tarama mevcut hata protokolüyle `SCAN_FAILED` olarak sonuçlandırılmaya çalışılır; yeni claim yapılmaz. |
| DB / commit hatası | Supervisor'a hata döner; sonuç uydurulmaz. Commit edilmemiş denemenin lease'i kalıcıdır; sonraki claim mevcut expiry/recovery protokolünü izler. |
| Child / taşıma thread'i sonlandırılamıyor | Supervisor zehirlenir; yeni child/claim açamaz. Process'i dış supervisor ile yeniden başlatın; GPU/backend işinin durduğunu ayrıca kontrol edin. |

Sonuçların kaynağı Owner ekranındaki job/attempt geçmişidir. Kuyruk boş, worker
çevrimdışı veya `PENDING` olması taramanın başarılı olduğu anlamına gelmez. Yanlış
verdict'i temizlemek için audit/attempt silmeyin; mevcut Owner retry yolunu kullanın.

## Adapter ve servis kabulünün açık sınırları

Process izolasyonu **güvenlik sandbox'ı değildir**; scanner fabrikası güvenilir
operator kodudur. Child daemon'dur; multiprocessing alt process oluşturamaz.
Adapter bağımsız inference process'lerini geride bırakmamalıdır. Dış bir Ollama/
model servisine istek yapıyorsa client timeout'u tek başına sunucu inference'ını
iptal ettiğini kanıtlamaz: cancellation ve kaynak serbest bırakma hedef runtime'da
ayrıca doğrulanmadan gerçek scanner kabul edilemez. Bu dilimde model indirilmedi,
dış model sunucusu başlatılmadı ve OS servisi kurulmadı.

Opt-in Compose profilinin restart ve minimum yetki sınırları aşağıda hazırlanmıştır;
gerçek scanner, production secret yönetimi ve işletim sistemi servis kurulumu hâlâ
kabul aşamasındadır. Birden fazla worker'ın ortak GPU kapasite
koordinasyonu M4'ün protokolüdür; bu tek-worker sınırı dünya çapında semaphore değildir.

## Opt-in container profili

`compose.yaml` içindeki `moderation-worker` servisi yalnız aynı adlı profilde yer alır.
Varsayılan `docker compose up` yalnız API/web'i çalıştırır. Worker'ı adıyla hedeflemek
profili otomatik etkinleştirebilir; bu nedenle yanlışlıkla `up moderation-worker`
kullanmayın. [Docker Compose profil davranışı](https://docs.docker.com/compose/how-tos/profiles/).

Servis root olmayan mevcut backend imajını kullanır; port yayınlamaz, API/web'e
`depends_on` bağı yoktur. `init`, salt-okunur kök filesystem, 64 MiB `/tmp` tmpfs,
`cap_drop: ALL`, `no-new-privileges`, 256 PID sınırı, `on-failure:3`, 30 saniyelik
stop grace ve boyutu sınırlı log politikası hazırdır. GPU, model dosyası, model cache
ve dış runtime henüz verilmez; bunlar seçilmiş adapter'ın kabul kapısıdır.

1. `.env.moderation.example` dosyasından git-ignored `.env.moderation` oluşturun.
   Yalnız ayrı worker DB/Auth kimliğini ve publishable key'i doldurun. `CHANGE_ME`
   değerleri gerçek yapılandırma değildir. Local host DB/Storage adresi container
   içinden `host.docker.internal` olmalı; staging/production Storage HTTPS ister.
2. Docker'ın çalıştığı host'ta (bu geliştirme bilgisayarında WSL) repo kökünden
   `docker compose --env-file .env.moderation --profile moderation-worker config --quiet`
   çalıştırın. Normal `config` ve `docker inspect` çıktısı secret içerebilir; paylaşmayın.
   Interpolation dosyasındaki tüm değişkenler container'a aktarılmaz: worker environment
   yalnız açık allowlist'tir, API/engine DSN veya servis anahtarı eklenmez.
3. Gerçek scanner seçilene kadar burada durun. Base backend imajı gerçek fabrika
   içermez. Sonrasında gözden geçirilmiş scanner'ı içeren, aynı worker CLI'ına sahip
   adapter imajını ayrı local override'da belirtin; model/driver/GPU/cache ve dış
   runtime cancellation kabulünü ayrıca tamamlayın. İmajı kabul olmadan fixture ile
   “çalışır” göstermeyin.

Kabul sonrası örnek local override (`.artifacts/moderation-image.compose.yaml`):

```yaml
services:
  moderation-worker:
    image: YOUR_REVIEWED_SCANNER_IMAGE:PINNED_VERSION
```

Yalnız bu adımlar tamamlandıktan sonra hedef servisi başlatın:

```sh
docker compose -f compose.yaml -f .artifacts/moderation-image.compose.yaml --env-file .env.moderation --profile moderation-worker up -d --no-deps --no-build moderation-worker
```

Worker'ı durdurmak için aynı dosya/ortam önekleriyle `stop moderation-worker` kullanın.
Genel `down` API/web'i de etkileyebilir. Container'ın `Up` olması moderasyon readiness
veya GPU/model kabul kanıtı değildir; geçerli job/attempt ve gerçek scanner sonucu izlenir.
CLI hatası exit `1` + `moderation_worker_failed` / exception sınıfı üretir; traceback,
DSN/token veya ham model içeriği yayınlanmaz. Clean stop hata logu üretmez.

## Doğrulama

`test_moderation_process.py` gerçek spawn process'iyle sıcak tekrar kullanım,
hard timeout, process crash, yeni nesil, startup reddi, çıktı sınırı, sanitization
ve stop davranışını sınar. Bunlar DB gerektirmeyen testlerdir.

`test_process_timeout_persists_error_and_owner_retry_keeps_attempt_history`,
yalnız izole Supabase yığınında gerçek job/attempt kaydıyla timeout → ERROR →
Owner retry → yeni deneme sonucunu ve onay kapısının kapalı kalmasını sınar.
İki test grubu da sentetik scanner kullanır; gerçek model kalitesinin kanıtı değildir.

`scripts/check_moderation_container.py --image cce-api:test`, Docker host'unda
yalnız standard-library Python ile çalışır. Varsayılan profilin worker'ı dışarıda
tuttuğunu, resolved environment allowlist'ini ve servis hardening ayarlarını kontrol
eder. Production backend imajında ağsız/salt-okunur geçici container'la yanlış
yapılandırmanın sanitize edilmiş hata çıkışını ve Linux spawn/reuse/timeout/yeni nesli
sınar. Gerçek Auth/DB/model kullanmaz. Foundation CI `containers` job'ına eklenmiştir;
yerel başarı yeni GitHub CI koşusu yerine geçmez.

Dayanak: [Python 3.13 multiprocessing](https://docs.python.org/3.13/library/multiprocessing.html)
(spawn, process sonlandırma ve pipe ömrü),
[Supabase Storage erişim kontrolü](https://supabase.com/docs/guides/storage/security/access-control)
(private nesnelerde authenticated/RLS erişimi).
