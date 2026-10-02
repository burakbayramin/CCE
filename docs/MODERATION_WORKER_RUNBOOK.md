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

İşletim sistemi servisinin restart/backoff ve secret yönetimi gerçek scanner
seçildikten sonra yapılandırılacak. Birden fazla worker'ın ortak GPU kapasite
koordinasyonu M4'ün protokolüdür; bu tek-worker sınırı dünya çapında semaphore değildir.

## Doğrulama

`test_moderation_process.py` gerçek spawn process'iyle sıcak tekrar kullanım,
hard timeout, process crash, yeni nesil, startup reddi, çıktı sınırı, sanitization
ve stop davranışını sınar. Bunlar DB gerektirmeyen testlerdir.

`test_process_timeout_persists_error_and_owner_retry_keeps_attempt_history`,
yalnız izole Supabase yığınında gerçek job/attempt kaydıyla timeout → ERROR →
Owner retry → yeni deneme sonucunu ve onay kapısının kapalı kalmasını sınar.
İki test grubu da sentetik scanner kullanır; gerçek model kalitesinin kanıtı değildir.

Dayanak: [Python 3.13 multiprocessing](https://docs.python.org/3.13/library/multiprocessing.html)
(spawn, process sonlandırma ve pipe ömrü),
[Supabase Storage erişim kontrolü](https://supabase.com/docs/guides/storage/security/access-control)
(private nesnelerde authenticated/RLS erişimi).
