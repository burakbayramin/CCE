# M2 Raporu — Kimlik, Katkı ve İnceleme

**Aşama:** M2 — Kimlik, katkı ve inceleme
**Durum:** Tamamlandı (2026-09-23 → 2026-09-24)
**İlgili WADR'lar:** WADR-001 (katkı/onay/değişiklik yetkisi), WADR-002 (görünürlük), WADR-003 (tanım ve form sınırları), WADR-010 (moderasyon modeli), WADR-011 (teknoloji yığını), WADR-012 (veritabanı şeması)

**Commit'ler**

| Commit | Dilim |
| --- | --- |
| `d288dfd` | Oturum doğrulama ve denetlenen World Owner ataması |
| `2d32861` | SSR kimlik doğrulama ve korumalı portal ekranları |
| `7f0ba01` | İzole taslaklar ve değiştirilemez gönderimler |
| `4cd7681` | Katkıcı öneri formu ve gönderim akışı |
| `4e27414` | Denetlenen Owner kararları ve değiştirilemez revizyonlar |
| `08a2650` | Owner inceleme ve katkıcı revizyon ekranları |
| `56fe73a` · `073db11` · `d172714` | İnceleme ekranı yarışlarının giderilmesi |
| `78243ed` · `0b68efb` | Private, değiştirilemez avatar yüklemeleri |
| `7f6bc9d` | Yükleme yarışı, kota ve güvenli Storage yapılandırması testleri |
| `04bfa3f` | Doğrulanmış M2 tamamlanma kaydı |

**Doğrulama:** Üç ayrı temiz CI koşusu —
[35864409030](https://github.com/burakbayramin/CCE/actions/runs/35864409030) (kimlik),
[35866586457](https://github.com/burakbayramin/CCE/actions/runs/35866586457) (taslak),
[36028256372](https://github.com/burakbayramin/CCE/actions/runs/36028256372) (M2.2–M2.6).

> Bu rapor yalnız M2'nin o noktadaki durumunu anlatır. Sonraki aşamalarda başvuru
> durum makinesine yeni korumalar, medya kurallarına yeni kısıtlar ve oturum sınırına
> yeni kapılar eklendi.

---

## 1. Hedef

Planın tek cümlelik hedefi: *"Contributor yalnız kendi taslak/başvurusunu görür;
World Owner güvenilir komutlarla inceleme yapar."*

Bu iki cümle aşamanın tamamını belirliyor. Bir karakter sistemi değil, **güvenilir bir
küratörlük hattı** kuruldu: kim önerir, kimin nereye erişimi var, bir öneri nasıl
değişmez hale gelir ve bir insan nasıl gerekçeli bir karar verir.

## 2. Teslim edilen iş

### M2.1 — Kimlik
Supabase Auth giriş/kayıt ve SSR oturum akışı kuruldu. World Owner ataması
operatör terminalinden, **denetlenen bir yönetim yoluyla** yapılıyor:

- Atama `postgres` bağlantısı gerektiriyor; API ve web bu kimliği kabul etmiyor
- Advisory lock ile yarış kapatıldı: aynı hesaba tekrar atama aynı kişiyi döndürür,
  başka hesaba devretme reddedilir
- İlk atama insan kimliği ve operatör audit'i tek transaction'dır
- **Kullanıcı metadata'sı rol yükseltemez.** Yeni hesaplar katkıcıdır; metadata'daki
  rol alanı dikkate alınmaz

### M2.2 — Yetki sözleşmesi
JWT doğrulaması asimetrik imza, issuer, audience ve süre kontrolüyle yapılıyor;
`PyJWTError` ile `PyJWTClientError` ayrımı sonradan eklendi. Actor bağlamı
`set_config(..., is_local=true)` ile **transaction'a bağlı** olarak ayarlanıyor, yani
SQLAlchemy havuzunda istekler arası taşınmıyor.

Kritik tasarım kararı: varsayılan davranış **reddet**. Kimlik bağlamı ayarlanmamışsa
`current_identity()` NULL döner ve hiçbir RLS politikası satır göstermez. Bu yüzden
bir yerde `actor_transaction` unutulsa bile sızıntı değil, veri kaybı olur.

### M2.3 — Başvuru modeli
Başvuru durum makinesi veritabanına gömüldü:

```
DRAFT ⇄ SUBMITTED → UNDER_REVIEW → { CHANGES_REQUESTED → DRAFT
                                  | REJECTED
                                  | APPROVED }
        └──────────────────────────→ WITHDRAWN
```

Durum alanı `text` + CHECK olarak seçildi (enum değil) — evrim kolaylığı için.
Geçişler hem Python'da hem DB trigger'ında doğrulanıyor ve **yazma yetkisi olmayan
her rol `42501` ile reddediliyor.**

Kritik sınır: geri çekilen başvuru yeniden açılamaz. Değişiklik talebinden sonra
katkıcı yeni bir taslak açıp **yeni bir immutable revizyon** gönderir; eski gönderim
ve geri bildirim korunur.

### M2.4 — Katkı arayüzü ve API'si
Yapılandırılmış form, ön izleme, gönderim, revizyon, geri çekme ve durum ekranı.
OpenAPI'den TypeScript istemci üretildi; Zod yalnız form UX doğrulaması için
kullanıldı (WADR-003'ün sınırı).

Katkıcı sınırları: başvuru başına en fazla **10** kayıt, avatar için **20/gün** ve
**100/toplam** rezervasyon.

### M2.5 — İnceleme arayüzü ve API'si
World Owner için sürüm farkı, gerekçeli ret/değişiklik talebi ve moderasyon sonucu
görünümü. **Ayrı bir engine yetkisi** (`cce_engine`) tanımlandı — Owner işlemleri API
rolünden ayrı bir DB kimliğiyle yürür, `cce_api` bu role geçemez.

Onay, **yalnız incelenen revizyona** aittir. Revizyon değişirse onay düşer.

### M2.6 — Medya
Avatar önerileri private Storage alanında, sahiplik kontrollü yükleniyor:

| Kural | Değer |
| --- | --- |
| Bucket | `cce-avatars`, **public değil** |
| Boyut | ≤ 512 KiB (girdi ve normalize çıktı) |
| Boyut aralığı | 32–2048 piksel |
| Format | PNG / JPEG / WebP, tek kare |
| Saklama | Sunucu yeniden kodlar (metadata atılır) |

Runtime **service key kullanmaz**; kullanıcının doğrulanmış JWT'si ve publishable key
ile erişir. Kullanıcı yalnız kendi ayrılmış path'ine ekleyebilir; overwrite/delete
izni yoktur. Görseller aynı origin `/media/{id}` üzerinden auth kontrollü sunulur.

Onay için referanslanan medya sürümü değiştirilemez.

## 3. Ölçek

| | M1 sonrası | M2 sonrası |
| --- | --- | --- |
| Migration | 1 | 5 |
| Web kaynak dosyası | 7 | 24 |
| Test dosyası (backend) | 3 | 10 |
| pgTAP dosyası | 1 | 4 |
| Web test dosyası | 2 | 5 |

Tamamlanma anındaki koşu sayıları: **54 backend testi** (birim + gerçek DB/Auth/
Storage entegrasyonu), **49 pgTAP**, **7 web testi.**

## 4. Doğrulama kanıtı

**Güvenlik sınırları gerçek bağlantılarla sınandı:**

- Owner metadata yükseltmesi reddedildi
- İkinci Owner ataması reddedildi
- Revoke sonrası eski token reddedildi
- Havuzlanmış bağlantıda A → B → kimliksiz erişim sırası doğrulandı
- İki kullanıcı izolasyonu: katkıcı başkasının başvurusunu göremiyor
- Eşzamanlı oluşturma/kaydetme, eski sürüm (409), kota ve revizyon değişmezliği sınandı
- Yükleme/gönderim yarışı sınandı
- Boş veya privileged Storage key reddi doğrulandı

**Tarayıcı:** Gerçek Edge üzerinde kayıt → giriş → çıkış → SSR → admin reddi akışı.
İki oturumlu (Owner + katkıcı) tarayıcı testi CI'a eklendi: avatar → inceleme →
değişiklik talebi → revizyon → ret.

**İzolasyon:** Gerçek yerel Owner ve kullanıcı verisi korunmak için ayrı bir
`cce-integration` yığını kuruldu (Auth 55321, DB 55322). Geliştirme yığınındaki
testler kendi rastgele hesaplarını oluşturup **yalnız kendi hesaplarını** temizliyor;
Owner testi, Owner atanmış bir veritabanında çalıştırılırsa güvenli biçimde
başarısız oluyor.

**Zaman farkı:** Windows/WSL saat farkından kaynaklanan token hatası gerçekte
görüldü ve sınırlı **5 saniyelik** toleransla karşılandı; imza, süre ve oturum
kontrolleri atlanmadı.

## 5. Bu aşama ne demek, ne demek değil

**Demek:** Kuratörlük hattı uçtan uca çalışıyor. Bir insan öneri yazıyor, gönderiyor,
Owner gerekçeli karar veriyor, katkıcı revize ediyor — ve bu süreçte yazılan her şey
denetlenebilir ve değiştirilemez. Medya özel ve değişmez.

**Dememek — ve bu ayrım kritik:**

- Gerçek moderasyon **yapılmadı.** M2'deki moderasyon adapter'ı test fixture'ıdır.
  Gerçek içerik aktivasyonu, plan gereği M3 karar kapısındadır.
- Canlı karakter **yoktur.** Başvuru onaylanır ama dünyaya katılan bir karakter
  üretilmez — bu M3.1'in işidir.
- Sohbet, dünya, bellek, ilişki, sene **yoktur.** Bunlar M4–M6'dadır.
- Katkıcılar için public açılış **yoktur.**

## 6. Sonraki aşamaya açtığı kapı

M2, M3'e üç şey verdi:

1. **Başvuru durum makinesi** — aktivasyon yalnız `APPROVED` durumuna bağlandığı için
   M3.1 bu makineyi girdi olarak kullandı; ayrı bir lifecycle enum'u üretmedi.
2. **Onaylanmış immutable revizyon** — definition derleyicisinin tek güvenilir kaynağı
   bu oldu. Tanım, kendi kaynak revizyonunu DB'de yeniden doğruluyor.
3. **Denetim defteri** — M3'ün her koruması "gerçek actor ile audit edilir" kuralına
   dayandı; altyapı hazırdı.

Ayrıca iki karar M3'ü şekillendirdi: geri çekme tek yönlü olduğu için aktivasyon
akışı "geri alınamaz" ilkesine göre tasarlanmak zorunda kaldı; ve `is_fixture`
sınırının Python'da durması, M3.2'de bunun veritabanına taşınması gerektiğini
gösterdi.

## 7. Sonradan sertleştirilen yüzeyler

M2'nin koyduğu kararlar aşağıdaki eklerle güçlendirildi. Hiçbiri M2'yi geçersiz
kılmıyor; hepsi aynı sözleşmenin daha sıkı uygulanması:

| Yüzey | Sonraki hâli |
| --- | --- |
| `is_fixture` sınırı | Python'dan çıkarılıp veritabanına taşındı; yalnız `postgres` değiştirebilen bir politika tablosu üzerinden |
| Avatar `READY` yazımı | Tek yönlü trigger; `READY`'ın doğrulanmadan yazılması engellendi |
| Denetim kaydı | Karar, geri bildirim ve olay satırı olmadan commit edilemiyor |
| Kimlik doğruluğu | Bağlantı açılışında veritabanı sürümü ve rol yetkisi doğrulanıyor |
| Oturum kontrolü | Avatar decode'dan **önce** canlı oturum denetleniyor |
| Retry denetimi | Yeniden deneme, kilitli iş durumuna bağlı olarak atomik yazılıyor |

Ayrıntı ve kanıt için `docs/ADVERSARIAL_REVIEW_2026-10-01.md` ve
`docs/CODE_REVIEW_2026-09-29.md`.

## 8. Devam eden riskler

M2 bittiğinde açık kalan ve aşama sırasında çözülmüş sayılmayan noktalar:

- Gerçek moderasyon sağlayıcısı/modeli seçimi — bilinçli olarak M3'e ertelendi
- Otomatik temizlik: yarım kalan avatar yüklemeleri ve retry kayıtları için retention
  politikası yok
- Onay checkbox'ları üç katmanda da toplanıyor ama hiçbir katman zorlamıyor —
  bu bir ürün kararı, bilinçli olarak açık bırakıldı
- Zaman aşımı, quota ve retry sayıları ölçülmüş değil; WADR-012'nin ölçülmüş
  optimizasyon disiplini M8'e bırakıldı