# Hata Desenleri — Bu Projede Tekrar Tekrar Düşülen Yerler

**Tarih:** 2026-10-04
**Kapsam:** M4.1–M4.7 sırasında yapılanlar. Her madde somut bir hataya, kanıtına ve
kalıcı düzeltmesine işaret eder.

Bu liste bir günlük değil, bir katalog. Aynı sınıftan hatalar tekrar ettiği için
sayılarıyla birlikte yazıldı: bir kez görüldüğünde şüphelenilecek, ikinci kezinde
aranacak.

---

## 1. RLS politikası var, grant yok — **5 kez**

**Neden oluyor:** satır düzeyi güvenlik politikası, yetkisi **zaten** olan bir rolün
satırlarını filtreler; yetkiyi kendisi vermez. İkisi birlikte yazılmalıdır.

**Kırktaş.** Belirgin hata şudur: politika yazdığım için "sıfır satır döner" bekliyorum,
karşılığında **`permission denied for table ...`** geliyor. Boş sonuç meşru bir cevaptır,
izin hatası ise hatadır — aradaki farkı kaybolduğunda teşhis yanlış yere gidiyor.

| # | Tablo | Nerede |
| :-- | :-- | :-- |
| 1 | `interaction_reservations`, `domain_effects`, `job_runs`, `interaction_outbox` | M4.1 |
| 2 | `job_workers`, `job_quarantine` | M4.2 |
| 3 | `interaction_turns` + dört karakter state tablosu | M4.4 |
| 4 | `interaction_deliveries` | M4.5 |
| 5 | `interaction_messages`, `interaction_response_tokens` | M4.6 |

**Kalıcı önlem:** grant ve politika aynı migration'da, birbirine yakın yazılır ve
yanına yorum gider. Bu dosyada sayı geçiyorsa yeni bir migration eklerken kontrol
listesine "grant var mı" maddesi eklenmeli.

**İlgili pgTAP boşluğu:** grant/politika eşleşmesi hiçbir katalog testiyle
doğrulanmıyor. `foundation.test.sql` yalnız `anon`/`authenticated` erişimini
denetliyor; runtime rollerinin yeni tablolara erişimi test edilmeseydi bu beş hata
görünmezdi.

---

## 2. plpgsql belirsizliği — parametre / kolon / çıktı sütunu — **4 kez**

**Neden oluyor:** plpgsql bir değişken ile aynı adlı kolonu kararsız bulur. Varsayılan
`variable_conflict = error` olduğu için ya belirsizlik hatası verir ya da üstüne
yazar. `SET search_path = ''` olan fonksiyonlarda isim çözümlemesi yine tam değil.

| # | Çakışan | Fonksiyon |
| :-- | :-- | :-- |
| 1 | `turn_index` parametre ↔ kolon | `claim_interaction` |
| 2 | `target_turn`, `recipient`, `request_key` parametreleri ↔ kolonlar | `accept_turn_delivery` |
| 3 | `turn_index` parametre ↔ kolon | `apply_interaction_turn` |
| 4 | **`sequence` çıktı sütunu** ↔ tablo kolonu | `commit_message` |

Dördüncüsü en incesi: `RETURN TABLE (recorded boolean, sequence integer)` yazdığım için
çıktı sütunu da bir değişken olur ve `max(sequence)` ifadesindeki tablo kolonuyla
çakışır. Fonksiyon adıyla nitelemek (`accept_turn_delivery.target_turn`) ya da
çıktı sütununu yeniden adlandırmak (`accepted_sequence`) çözüm oldu.

**Kalıcı önlem:** yeni `ops_private` fonksiyonunda parametre adları tablo kolon
adlarıyla **örtüşmemeli**; `RETURN TABLE` sütun adları da aynı dikkate tabidir.

---

## 3. Hata eşleme kendi SQL'ini okuyordu — **1 kez, 3 CI koşusunu yedi**

**En pahalı hata.** `protocol._map` veritabanı mesajını kelime kelime tarıyordu:

```python
if "Lease" in message or "lease" in message:
    return ContributionError(409, "Kiralama artık geçerli değil")
```

Çağrı `select * from ops_private.claim_interaction(:id,:purpose,:holder,:lease,:command)`
şeklindeydi. SQLAlchemy hata metnine **bağ parametrelerinin adını** yansıttığı için
`:lease` kelime taramasını tetikliyordu. Gerçek hata ise `claim_interaction`'ın
`character_id` kolonunu hiç yazmamasından gelen bir NOT NULL ihlaliydi.

Sonuç: gerçek mesaj kayboldu, üç tur yanlış yere bakıldım ("Docker Hub rate limit",
"grant eksik", "kiralama süresi") ve hiçbiri doğru değildi.

**Kalıcı önlem:** eşleme kelime taramasıyla değil, veritabanının **kullandığı tam
ifadelerle** yapılır; `_FAILURES` tablosu buna göre kuruldu. Ayrıca her eşleme
öncesi ham mesaj `logger.warning` ile yazılıyor — bu log olmasa teşhis yine kör
yürüyecekti. **Bu tek başına öğrenilen en değerli şey: yutulan hatayı loglama.**

---

## 4. Migration dosya adı ile işaretlediği sürüm ters sırada — **1 kez**

`20261003103000_delivery_table_grants` → sürüm 16, `20261003110000_processing_table_grants`
→ sürüm 15. Son dosya işareti geri 15'e yazıyordu ve uygulama görünürde başarılıydı.

**Neden oluyor:** Supabase migration'ları **adın zaman damgasına göre** sıralar;
`ops_private.schema_version` ise dosyanın içinde yazan değerdir. İkisi ayrı kaynaktır.

**Kalıcı önlem:** `db reset` "başarılı" olsa bile `select version from
ops_private.schema_version` ile beklenen değer ayrıca okunmalı. Push'tan önce yerelde
bu okuma yapılmalı.

---

## 5. Test kendi kurduğu ortamı varsayıyordu — **9 kez**

| # | Hata | Sonuç |
| :-- | :-- | :-- |
| 1 | Ham `psycopg` bağlantısı, kod SQLAlchemy bekliyor | `TextClause has no len` |
| 2 | `SecretDsn` (yok) yerine `SecretStr` | Import hatası |
| 3 | Engine DSN'i `database_url` alanına kondu | Doğrulama reddetti; `cce_api` rolü şart |
| 4 | `identity_context` owner engine'de çağrıldı | `cce_engine` `public.profiles`'ı okuyamıyor → 503 |
| 5 | **Sabit port 55322** yazıldı | CI 54322'de koşuyor, bağlantı reddi |
| 6 | Commit edilmiş tur bitmiş, `HELD` rezervasyon beklenmiş | `fetchone()` → None |
| 7 | Geçersiz türe Python API'siyle ulaşılamadı | Test hiçbir şey doğrulamıyordu |
| 8 | Ham alt dizi sayıldı | Metin meşru olarak iki kareye yayıldığı için hata |
| 9 | Fixture, kendisi tükettikten sonra çağrıldı | Fixtures are not supposed to be called directly |

**Kalıcı önlem:** entegrasyon testleri `local_environment`'ten türetilen yardımcıları
kullanır; hiçbir port veya DSN sabit yazılmaz. Beklenen durum testin içinde
kurulur (`a_stuck_reservation`), hazır bir duruma güvenilmez.

---

## 6. Ölü kod bırakıldı — **4 kez**

Her seferinde "yazdım, temizledim, sildim" dedim ama çalıştırmadığım için fark
etmedim: kullanılmayan pydantic model, `raise ContributionError(500)` yapan sahte
oturum yardımcısı, hiç çağrılmayan `_one`, kullanılmayan `expiry_from_now`,
`del text` satırı.

**Kalıcı önlem:** yeni modül yazıldıktan sonra başka bir dosyadan **gerçekten
kullanıldığı** görülmeden commit'lenmemeli. `ruff` kullanılmayan *import'u* bulur,
kullanılmayan *sınıf ve fonksiyonu* bulmaz.

---

## 7. Yanlış engine'de yetki kontrolü — **1 kez, 3 dal kırıldı**

Oturum/rol kontrolünü owner engine üzerinde yapmak. Kimlik `public.profiles`'ı okur,
onu **yalnız `cce_api`** okur. Doğru bölme: **okuma API düzleminde, komut owner
düzleminde** — `current_identity` deseninin kendisi.

Aynı hatanın iki biçimi vardı ve ikisi de aynı yere çöküyor:
`interaction_context` yetkisi olmayan tabloda açılıyor, `SET LOCAL` beklenen
transaction'da kurulmuyor.

---

## 8. Ortam tuzakları

**WSL kendiliğinden sönüyor.** Boşta kalınca distro kapanıyor, Docker daemonu
duruyor, konteynerler "restarting" görünüyor ve `psql` "database system is starting up"
diyor. Belirti: **testler ara ara kendiliğinden geçiyor**, sonra düşüyor — kod
değişmediği halde. Çözüm: test koşarken `docker logs -f` ile distro ayakta tutulur
(`wsl -d ... -- docker logs -f`). Docker kurulduktan sonra bu tamamen kesildi.

**`toomanyrequests: Rate exceeded` gürültüsü.** Docker Hub limiti loga `ERROR`
seviyesinde düşüyor ve gerçek SQL hatasını gölgeliyor. **Bir kez teşhisi yanlış
yönlendirdi.** Logda `ERROR`/`FATAL` satırı görüldüğünde, ondan önce/sonra
giden bağlam satırları okunmalı; filtreli `grep` yanıltıcı olabilir.

**Arka plan süreçlerinde `workdir` uygulanmıyor.** Komut içinde konum değiştirmek
gerekiyor.

---

## 9. Doğrulama disiplini — işe yarayan kısım

**Push'tan önce yerelde koştur.** Docker ortaya çıktıktan sonra M4.4, M4.5 ve M4.6
toplamda **yedi gerçek hata** push'tan önce yakalandı: `turn_index` belirsizliği,
`ON CONFLICT` hedefinin kolon olması gerektiği, sürüm işarekinin geri alınması,
migration dosya adı çakışması, iki sütun çakışması, grant eksikleri ve yanlış
engine.

Push öncesi koşmayan iki dönemde ise **dört hata** CI'dan çıktı ve üçü ayrı kök
nedendi. Karşılaştırma tek başına yeterli bir gerekçe: **maliyet, aynı iş için
geçen süre ve turlar; kalan süre burada belirleyici olduğu için önce yerelde
doğrula.**

---

## Bu listeden çıkarılacak tek ders

Beşinci kez aynı sınıfa düştüğümde fark ettim: **bir kalıbın ikinci tekrarı,
tesadüf değildir.** O an önlem yazılmalı. Bu dosya o anların kaydı; yeni bir
kategori eklendiğinde buraya da girmeli.

İlgili: [M1 raporu](M1_FOUNDATION_REPORT.md) ·
[M2 raporu](M2_IDENTITY_AND_CONTRIBUTIONS_REPORT.md) ·
[Adversarial inceleme](ADVERSARIAL_REVIEW_2026-10-01.md) ·
[M3.5 sürüm notu](RELEASE_NOTES_2026-10-02_M3_5.md) ·
[M4.1 sürüm notu](RELEASE_NOTES_2026-10-02_M4_1.md)
