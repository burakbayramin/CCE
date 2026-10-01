# Bekleyen sürüm notu — review sınırı ve şema v5

**Durum:** Kod ve SQL migration'ları yalnız izole yerel `cce-integration` yığınında
doğrulandı: 16 migration'ın boş DB'de tekrarı, 89 pgTAP, 47 DB/Auth/Storage
integration testi ve ayrıca iki wrapper içindeki üç gerçek tarayıcı senaryosu geçti.
109 backend birim testi, 38 web testi, lint/typecheck ve contract kontrolleri geçti.
Bu commit'ler için yeni GitHub CI koşusu yapılmadı; sürüm deploy edilmedi.
Mevcut `cce-local` veritabanı ve Owner verileri değiştirilmedi; geliştirme DB'si
hâlâ v1 olduğundan yeni API'yi orada çalıştırmak ayrıca migration gerektirir.

Bu değişiklikte `ops_private.schema_version`, review sınırı migration'larında
`1 → 2`, avatar INSERT korumasında `2 → 3`, katkıcı audit eylemi ve bozuk moderasyon
işi korumalarında `3 → 4`, kilit altındaki retry audit'inde `4 → 5` geçer.
Yeni API yalnız v5 şemayla başlar. Önceki API sürümleri v5 DB ile uyumlu değildir;
yeni API de v1/v2/v3/v4 DB'de
başlangıçta durur. Bu, bilinçli bir fail-fast kapısıdır; sürümler aynı DB üzerinde bağımsız
rollout/rollback için uyumlu değildir.

| DB | API | Sonuç |
| :-- | :-- | :-- |
| v1 | önceki (v1 bekleyen) | Önceki sürümün normal durumu |
| v1/v2/v3/v4 | yeni (v5 bekleyen) | API başlangıcı reddedilir |
| v5 | önceki (v1 bekleyen) | Readiness `503`; trafik verilmemeli |
| v5 | ara sürüm (v2/v3/v4 bekleyen) | API başlangıcı reddedilir |
| v5 | yeni (v5 bekleyen) | Doğrulama sonrası hedef durum |

Yayın sırası: önce boş/staging DB'de tüm migration ve DB/Auth entegrasyon
testlerini geçir; gerçek ortamda mevcut API trafiğini durdur/drain et, geri
dönüş için tam DB yedeği al, migration'ları uygula, yeni API/web sürümünü aç,
readiness ve temel Auth/Owner/medya akışlarını doğrula, sonra trafiği geri ver.
Bu adımlar tamamlanmadan sıfır kesinti veya başarılı production deploy iddiası yoktur.

Yalnız API binary'sini geri almak yeterli değildir. v5 DB'de eski API hazır
sayılmaz; yalnız marker'ı `1`, `2`, `3` veya `4` yapmak da yeni şemanın gerçekten geri alındığını
kanıtlamaz. Geri dönüş, uyumlu tam DB yedeği + önceki API'nin birlikte geri
yüklenmesi ya da v5 üzerinde ileriye dönük bir düzeltme gerektirir.
