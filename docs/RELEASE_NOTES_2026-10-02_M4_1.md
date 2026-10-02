# Sürüm Notu — M4.1 Ortak İş Protokolü

**Tarih:** 2026-10-02
**Kapsam:** M4'ün yedi alt diliminden ilki. Kalan altı dilim bu protokolün üzerine kuruluyor.

> [!WARNING]
> **Yeni migration henüz çalıştırılmadı.** `supabase start` bu migration'ı uygularken
> başarısız oldu ve kök neden henüz teşhis edilmedi. Bu doküman yalnız **niyeti** kaydeder,
> doğrulanmış davranışı değil. Şema `version = 9` olarak hedefleniyor ama henüz oraya
> ulaşılmadı.

---

## Neden önce protokol

M4'ün altı alt dilimi de aynı üç şeye dayanır: bir karakteri bir etkileşime ayırmak,
bir worker'ın kiralama almadan sonuç yazamaması, ve bir domain etkisinin tam bir kez
uygulanması. Bunlar ayrı ayrı her dilimde yeniden tasarlansaydı M5 ve M6 aynı yarış ve
çift-uygulama hatalarını tekrar ederdi.

---

## İki kural şemayı biçimlendirdi

### 1. Süresi dolmuş lease karakteri müsait yapmaz

İlk taslakta `claim_interaction` süresi dolmuş bir rezervasyonu yeni bir worker'a
devrediyordu. Bu, WADR-011'in açıkça yasakladığı davranıştı: süresi dolmak, worker'ın
durduğunun kanıtı değildir. Böyle bir serbest bırakma, state'i hâlâ uçuşta olabilecek
bir karakter üzerinde ikinci bir etkileşim başlatırdı.

Düzeltilen davranış:

- Süresi dolmuş rezervasyon **reddedilir**
- `stale_interactions()` adayları listeler (taranabilir, otomatik çözülmez)
- `resolve_interaction` operatör kararıyla kapatır; gerekçe 10–1000 karakter zorunlu
- Terk edilmiş denemeler `ABANDONED` olarak **kaydedilir**, silinmez — operatör ne
  olduğunu görebilsin
- Yalnız aynı holder kendi işine devam edip deadline'ı yenileyebilir

### 2. Etki kimliği model adı taşımaz

`domain_effects.effect_identity` bilerek **model adı, sağlayıcı ve processing sürümü
içermez**. `applied_by_processing_version` forensics için ayrı bir sütundur ve
kimliğin parçası değildir.

Bunun sonucu: aynı deneyim farklı bir modelle yeniden koşulduğunda `on conflict do
nothing` ile çarpışır, dünyanın hafızası kopyalanmaz. Model değişikliği bir veri
migration'ı değil, yeniden işlem gerektiren bir olaydır.

---

## Yapılanlar

| Nesne | Rol |
| :-- | :-- |
| `interaction_reservations` | Karakter başına tek `HELD` rezervasyon (kısmi unique index) |
| `ownership_generation` | Her yeniden kiralamada artar; tüm yazma yollarında fence |
| `domain_effects` | Stabil kimlikle bir kez uygulanan etkiler |
| `job_runs` | Append-only deneme defteri; generation'ı kopyalar |
| `interaction_outbox` | Sonuçla **aynı transaction'da** yazılan yayın satırları |

### Fence

`job_runs` kendisine yetki veren lease'in `ownership_generation`'ını kopyalar, yani süresi
dolmuş bir iş sahipsiz bir join olmadan tanınır. Hiçbir runtime rolü `job_runs` veya
`domain_effects` üzerine **doğrudan yazamaz**: deneme açma (`begin_interaction_attempt`)
ve bitirme (`commit_interaction_result`) ikisi de fence'li definer fonksiyonlardan geçer.

### Boş sonuç da sonuçtur

Hiçbir şey değişmeyen bir sahne rezervasyonu yine kapatır. Aksi halde etkisiz etkileşimler
karakteri kalıcı olarak kilitli tutardı.

---

## Doğrulama durumu

| Kontrol | Sonuç |
| :-- | :-- |
| ruff / format / mypy | ✅ |
| Backend birim testleri | ✅ 140 |
| Migration uygulaması | ❌ **başarısız — kök neden teşhis edilmedi** |
| 4 yeni entegrasyon testi | ⏳ CI'da koşacak |

Yazılan entegrasyon testleri M4.1'in dört maddesini sabitliyor: tek rezervasyon ve
fence, süresi dolmuş lease'in karakteri serbest bırakmaması, model değişiminde etki
tekilleştirme, ve boş sonucun rezervasyonu kapatması. **Bunların hiçbiri henüz
koşmadı.**

---

## Commit'ler

| Commit | Kapsam |
| :-- | :-- |
| `618c1f3` | M4.1 migration, Python protokolü, entegrasyon testleri |
| `09c61ed` | CI: veritabanı ve migration hatalarını annotation olarak yayınlama |

## Sıradaki iş

1. Migration hatasının kök nedeni — CI annotation'ları artık migration log'unun kuyruğunu
   da yayınlıyor, bir sonraki koşuda okunabilir olmalı
2. Yeşil CI sonrası M4.1 doğrulanmış sayılır
3. M4.2 — `JobQueue` adapter'ı, worker lease/sahiplik döngüsü, heartbeat, bounded retry,
   quarantine ve recovery taraması

## Commit disiplini notu

GitHub Actions kotası sınırlı. Bu nedenle artık her küçük düzeltmede push yapılmayacak:
değişiklikler yerelde doğrulanıp **mantıksal gruplar hâlinde** tek push'ta toplanacak.
Migration doğrulaması gibi CI'ın tek gerçek kaynağı olduğu durumlarda koşu harcanması
kaçınılmaz; geri kalan her şey yerel kontrollerle kapanacak.