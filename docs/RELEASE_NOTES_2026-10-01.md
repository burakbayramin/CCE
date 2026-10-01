# Bekleyen sürüm notu — review sınırı ve şema v3

**Durum:** Kod yerelde hazırlanmıştır; yeni SQL migration'ları gerçek DB/CI üzerinde
henüz doğrulanmamış ve bu sürüm deploy edilmemiştir.

Bu değişiklikte `ops_private.schema_version`, review sınırı migration'larında
`1 → 2`, avatar INSERT korumasında `2 → 3` geçer. Yeni API yalnız v3 şemayla
başlar. Önceki API sürümleri v3 DB ile uyumlu değildir; yeni API de v1/v2 DB'de
başlangıçta durur. Bu, bilinçli bir fail-fast kapısıdır; sürümler aynı DB üzerinde bağımsız
rollout/rollback için uyumlu değildir.

| DB | API | Sonuç |
| :-- | :-- | :-- |
| v1 | önceki (v1 bekleyen) | Önceki sürümün normal durumu |
| v1/v2 | yeni (v3 bekleyen) | API başlangıcı reddedilir |
| v3 | önceki (v1 bekleyen) | Readiness `503`; trafik verilmemeli |
| v3 | ara sürüm (v2 bekleyen) | API başlangıcı reddedilir |
| v3 | yeni (v3 bekleyen) | Doğrulama sonrası hedef durum |

Yayın sırası: önce boş/staging DB'de tüm migration ve DB/Auth entegrasyon
testlerini geçir; gerçek ortamda mevcut API trafiğini durdur/drain et, geri
dönüş için tam DB yedeği al, migration'ları uygula, yeni API/web sürümünü aç,
readiness ve temel Auth/Owner/medya akışlarını doğrula, sonra trafiği geri ver.
Bu adımlar tamamlanmadan sıfır kesinti veya başarılı production deploy iddiası yoktur.

Yalnız API binary'sini geri almak yeterli değildir. v3 DB'de eski API hazır
sayılmaz; yalnız marker'ı `1` veya `2` yapmak da yeni şemanın gerçekten geri alındığını
kanıtlamaz. Geri dönüş, uyumlu tam DB yedeği + önceki API'nin birlikte geri
yüklenmesi ya da v3 üzerinde ileriye dönük bir düzeltme gerektirir.
