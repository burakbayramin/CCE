# Bekleyen sürüm notu — review sınırı ve şema v2

**Durum:** Kod yerelde hazırlanmıştır; yeni SQL migration'ları gerçek DB/CI üzerinde
henüz doğrulanmamış ve bu sürüm deploy edilmemiştir.

Bu değişiklikte `ops_private.schema_version` son migration ile `1 → 2` geçer.
Yeni API yalnız v2 şemayla başlar. Önceki API ise v1 beklediğinden v2 DB'de
readiness `503` döndürür. Ters yönde, yeni API + v1 DB başlangıçta durur.
Bu, bilinçli bir fail-fast kapısıdır; iki sürüm aynı DB üzerinde bağımsız
rollout/rollback için uyumlu değildir.

| DB | API | Sonuç |
| :-- | :-- | :-- |
| v1 | önceki (v1 bekleyen) | Önceki sürümün normal durumu |
| v1 | yeni (v2 bekleyen) | API başlangıcı reddedilir |
| v2 | önceki (v1 bekleyen) | Readiness `503`; trafik verilmemeli |
| v2 | yeni (v2 bekleyen) | Doğrulama sonrası hedef durum |

Yayın sırası: önce boş/staging DB'de tüm migration ve DB/Auth entegrasyon
testlerini geçir; gerçek ortamda mevcut API trafiğini durdur/drain et, geri
dönüş için tam DB yedeği al, migration'ları uygula, yeni API/web sürümünü aç,
readiness ve temel Auth/Owner/medya akışlarını doğrula, sonra trafiği geri ver.
Bu adımlar tamamlanmadan sıfır kesinti veya başarılı production deploy iddiası yoktur.

Yalnız API binary'sini geri almak yeterli değildir. v2 DB'de eski API hazır
sayılmaz; yalnız marker'ı `1` yapmak da yeni şemanın gerçekten geri alındığını
kanıtlamaz. Geri dönüş, uyumlu tam DB yedeği + önceki API'nin birlikte geri
yüklenmesi ya da v2 üzerinde ileriye dönük bir düzeltme gerektirir.
