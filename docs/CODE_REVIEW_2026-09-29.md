# CCE Kod İncelemesi — 2026-09-29

**Kapsam:** 30 Python modülü, 25 web kaynak dosyası, 8 SQL migration, 7 pgTAP +
18 backend + 4 e2e test, CI workflow, Docker/compose yapılandırması.

**Yöntem:** Mimari inceleme, statik kod okuması ve kaynak satırı doğrulaması. Hiçbir
dosya değiştirilmedi, test çalıştırılmadı. Her bulgu `dosya:satır` ile kanıtlanmıştır.

**Durum (2026-09-30):** Aşağıdaki uygulama notu, Sürüm 2 bulgularının güncel durumudur.
Migration'lar henüz gerçek veritabanında koşturulmadığı için DB maddeleri entegrasyon
testi geçene kadar **doğrulanmış tamamlandı** sayılmamalıdır.

### 2026-09-30 uygulama notu

| Bulgu | Durum | Yapılan işlem / kalan sınır |
| :-- | :-- | :-- |
| 1 | Kabul edilmedi | Atomik transaction nedeniyle bildirilen yarış yok; eski revizyonun `CANCELLED` kalması kasıtlı. |
| 2 | Kısmi | `READY → PENDING` artık DB trigger'ıyla reddediliyor; `READY` yazan güvenilir API rolünün Storage doğrulamasına güvenilmeye devam ediliyor. |
| 3 | Yanlış pozitif | Yeni revizyon kendi metin–avatar çiftini yeniden tarıyor; avatar silinmedi. |
| 4 | Açık | `identity_context` ve iş transaction'ı ardışık; eşzamanlı iki bağlantı yok. Profil oluşturmayı taşımak yeni hesapların FK davranışını, Owner API/engine rol ayrımını ve avatarın iki fazlı yüklemesini etkiliyor. DB entegrasyon ve eşzamanlı yük testi olmadan havuzu kör büyütmemek için bu ayrı kapasite işi olarak bırakıldı. |
| 5 | Belgeli | GUC/verified-API güven sınırı `actor_transaction` docstring'inde açıklandı; HMAC eklenmedi. |
| 6 | Uygulandı, DB testi bekliyor | DB fixture kapısı varsayılan kapalı. Yalnız loopback test provisioner'ı test stack'inde açıyor; onay ve tanım trigger'ları kapalıyken fixture'ı reddediyor. Entegrasyon testi eklendi. |
| 7 | Koruma eklendi | pgTAP, hiçbir runtime rolünün `cce_migrator` üyesi olmamasını kontrol ediyor. Gelecekte elle yapılacak yanlış grant'i migration tek başına önleyemez. |
| 8 | Uygulandı, DB testi bekliyor | Deferred constraint trigger karar transaction'ında feedback ve event satırlarını zorunlu tutuyor; negatif entegrasyon testi eklendi. |
| 9 | Uygulandı, DB testi bekliyor | Defter deneme değil **istek** günlüğü: PENDING/RUNNING sırasında mevcut işi döndüren idempotent çağrılar da actor ve önceki state ile kaydedilir. Gerçek yürütmeleri `moderation_attempts` tutar. Diğer audit tabloları gibi retention henüz tanımlı değil. |
| 10 | Doğrulandı | Anonim medya isteği 307 yerine gövdesiz 401 dönüyor; web testi eklendi. |
| 11 | Doğrulandı | Pydantic sınırlarıyla karşılaştırılan form contract'ı, CI kontrolü ve form alanı testleri eklendi; gönderim payload'ındaki geniş `as Proposal` cast'i kaldırıldı. |
| 12 | Doğrulandı | API lifespan readiness/rol kontrolü başarısızsa başlatmıyor; unit test eklendi. |
| 13 | Yerel web testleri geçti | Contribution/review status'ları UI hata mesajlarına bağlandı; detay sayfasında 404 `notFound()` yoluna gider. `requireIdentity()` network/5xx yanıtında artık `null` dönüp yanıltıcı 200 Owner ekranı render etmez, hata fırlatır ve error boundary gösterir. Next.js Server Component hata yolunun HTTP yanıtı bire bir upstream 503 değildir. |
| 14 | Kısmi | Yeni SQL davranışları için Python DB entegrasyon testleri eklendi; pgTAP davranış kapsamı ayrıca genişletilmedi. |
| 15 | Uygulandı, DB testi bekliyor | Aktif attempt'ın aynı işe ait olması deferred FK ile, iş başına tek RUNNING attempt kısmi unique index ile korunuyor. |
| 16 | Açık | PENDING/Storage yetimlerini temizleyen ayrı bakım işi henüz yok; idempotent upload retry korunuyor. |
| 17 | Kod değişmedi | PyJWT bilinmeyen `kid` için JWKS yenilemesini zaten dener; gerçek rotasyon penceresi ayrı entegrasyon testiyle ölçülmeli. Her bilinmeyen `kid` 503'e çevrilmemeli. |

Şema sürümü, review sınırı migration'larından sonra `2` yapıldı. API ve loopback
provisioner artık `2` bekler; yalnız foundation migration'ı uygulanmış eski DB
sessizce hazır sayılmaz. `cce_migrator` için eklenen iki audit SELECT politikası
yalnız private deferred trigger'ın FORCE RLS altında kayıtları görebilmesi içindir;
runtime role üyelikleri pgTAP canary'siyle kontrol edilir.

### 2026-10-01 takip bulguları

- 500 yanıtları önce de `http_request`/status/request ID olarak loglanıyordu;
  eksik olan hata türüydü. Backend artık ayrı, allowlist'li `http_exception`
  kaydı üretir; hata metni ve traceback loglanmaz. Web error boundary yalnız
  Next.js `digest` değerini istemci konsoluna yazar; kullanıcıya özel hata
  gösterilmez. İki kayıt arasında otomatik ortak ID yoktur, bu sınırlama sürer.
- Şema v2 marker'ı ayrıcalıklı `postgres` migration runner tarafından güncellenir.
  `cce_migrator` için marker SELECT/UPDATE politikası açılmadı; FORCE RLS altında
  marker'ı değiştirememesi için entegrasyon testi eklendi. Gerçek DB'de henüz
  koşturulmadı. Bu madde güvenlik bulgusu değil, bilinçli yetki sınırıdır.
- v1/v2 API–DB sürüm kapısının yayın ve rollback sırası
  [bekleyen sürüm notunda](RELEASE_NOTES_2026-10-01.md) açıklandı. Bu normal
  operasyonel koşuldur, bulgu değildir; not deploy yapıldığı anlamına gelmez.
- `notFound()` için Türkçe `app/not-found.tsx` eklendi; 404'ün gerçek HTTP
  statüsü streaming moduna bağlı olabilir.

Önceki düşük öncelikli “backend checkbox'ları zorlamıyor” ifadesi yanlıştı:
`repository.py` SUBMIT sırasında iki onayı da zorunlu tutuyor. Taslak kaydında
onayların boş bırakılabilmesi ayrı bir ürün kararıdır.

> **Sürüm 2 (2026-09-29, ikinci geçiş).** İlk sürüm 17 bulguyu 5 "yüksek" ile
> sunmuştu. Kod karşılaştırması sonrası **iki bulgu yanlış çıkarıldı, üçünün önceliği
> düşürüldü, birinin yükseltildi.** Düzeltmeler ve gerekçeleri aşağıda açıkça
> belgelenmiştir — sessizce düzeltilmemiştir. Sürüm 1'deki iddialar bu notla
> geçersizdir.

---

## Sürüm 2 değişiklik özeti

| Bulgu | Sürüm 1 | Sürüm 2 | Neden değişti |
| :-- | :-- | :-- | :-- |
| 1 — `CANCELLED` kalıcı kilit | 🔴 Yüksek | 🟡 Düşük | Transaction atomikliği yarışı ortadan kaldırıyor |
| 2 — Avatar `READY` kapısı | 🔴 Yüksek | 🟠 Orta | `cce_api` son kullanıcı rolü değil |
| 3 — Avatar bayatlaması | 🔴 Yüksek | ❌ **Kaldırıldı** | **Yanlış okuma** — yeni revizyon kendi moderasyonunu alıyor |
| 4 — Havuz darboğazı | 🔴 Yüksek | 🟠 Orta | Kapasite riski, kesin hata değil |
| 5 — Kimlik beyanı | 🔴 Yüksek | 🟠 Orta | Gerçek ama belgelenmemiş güven sınırı |
| **6 — `is_fixture` DB boşluğu** | 🟠 Orta | **🔴 En yüksek** | **Tek gerçek güvenlik sınırı boşluğu** |
| 7 — `cce_migrator` üyeliği | 🟠 Orta | 🟠 Orta | Gerekçe düzeltildi (`NOINHERIT` yetmez) |
| 10 — `/media` 307 | 🟠 Orta | 🔴 Yüksek | Somut HTTP davranış hatası |
| 12 — `lifespan` doğrulaması | 🟠 Orta | 🔴 Yüksek | Somut ve küçük düzeltme |
| 14 — pgTAP kapsamı | 🟠 Orta | 🟠 Orta | İfade düzeltildi ("tamamen" yanlıştı) |
| 17 — JWKS sınıflandırma | 🟠 Orta | 🟠 Orta | Öneri düzeltildi (503 sahte token'ları bozardı) |
| S3 protokolü | 🟡 Düşük | ❌ Kaldırıldı | Yanlış genelleme — kimlik bilgisine bağlı, protokolden bağımsız |

### Kaldırılan bulgu 3 — neden yanlıştı

Rapor `change_draft` içinde `avatar_id`'nin güncellenmediğini ve bunun "moderasyonu
geçmiş eski avatarın yeni metinle eşleşmesi" ürettiğini iddia etti. Bu yanlış.

`change_draft` metin değiştiğinde **yeni bir `revision_id` üretir**
(`repository.py:138-146`) ve `ops_private.submission_moderation` revizyon başına tek
satır tutar (`contribution_review.sql:38`, PK `revision_id`). Yeni revizyon
`enqueue_moderation` ile **kendi moderasyon işine** girer; yeni metin–avatar çifti
tam olarak moderasyondan geçer. Eski revizyonun verdict'i miras alınmaz.

Önerilen "her metin değişikliğinde avatarı sil" düzeltmesi de bu nedenle yanlış olurdu:
avatar taşıyıcı bir görseldir, metinle birlikte değişmesi gerekmez ve katkıcının
seçimini gereksiz yere iptal ederdi.

### Düşürülen bulgu 1 — neden kritik değil

Rapor, `enqueue` (`SUBMITTED` kabul, `:77`) ile `claim` (`UNDER_REVIEW` arar, `:140`)
arasındaki durum farkını "yarış koşulu" olarak sundu. `start_review` bu iki işlemi
**aynı transaction'da** yapar: `review.py:75` `read_one(lock=True)` ile satır kilidi
alır, `enqueue_moderation` ve `UNDER_REVIEW` geçişi `actor_transaction`
(`engine.begin()`) içinde commit edilir. Ara durum gözlenemez.

`CANCELLED` bir revizyona ulaşmak için zaten bir worker'ın claim etmiş olması
gerekir; bu yol ancak eski/kaynak değişmiş bir revizyonda tetiklenir ve o revizyon
zaten onaylanamaz durumdadır. Yeniden denenemez olması gerçek ama **kritik değil,
savunma derinliği** meselesi.

---

## Özet

Kod tabanı, ticari bir projeden çok daha titiz bir güvenlik ve doğruluk disiplini
sergiliyor: RLS politikaları, sabit `search_path`, kapsam daraltılmış `SECURITY DEFINER`
fonksiyonlar, fencing token deseni, üç katmanlı optimistic locking ve dürüst fixture
etiketlemesi.

**Sürüm 2 sonucu: 2 somut davranış hatası, 1 gerçek güvenlik sınırı boşluğu, 1
belgelenmemiş güven sınırı, ~10 bakım/sağlamlaştırma maddesi.** Sürüm 1'in "5 kritik
güvenlik açığı" çerçevesi gerçeği yansıtmıyordu; çoğu savunma derinliği veya kapasite
konusuydu.

| Alan | Sonuç |
| :-- | :-- |
| SQL injection | Yok — ~35 `text()` çağrısının tamamı bound parameter |
| XSS | Yok — `dangerouslySetInnerHTML`/`innerHTML`/`eval` bulunamadı |
| Actor identity sızıntısı | Yok — `SET LOCAL` + fail-closed varsayılan |
| Prompt injection ayrımı | Doğru — katkı metni system prompt'a girmiyor |
| Yetki kararı sunucuda | Doğru — web yalnız gizliyor, karar backend'de |
| **Fixture sınırı** | **Python'da kapalı, DB'de açık** (bulgu 6) |

---

## 🔴 Yüksek

### 6. `is_fixture` sınırı veritabanında kurulmamış

**En önemli gerçek boşluk.** Moderasyon kanıtı kontrolünün tamamı DB trigger'larına
gömülü seçilmiş bir sistemde, tek istisna Python katmanında kalmış.

**Mevcut durum:**

| Katman | `is_fixture` kontrolü | Konum |
| :-- | :-- | :-- |
| Python — review | ✅ var | `review.py:158` |
| Python — derleme | ✅ var | `review.py:88`, `characters/repository.py:74` |
| **DB — onay koruması** | ❌ **yok** | `contribution_review.sql:112-115` |
| **DB — tanım koruması** | ❌ **yok** | `character_definitions.sql:42-45` |

`contribution_review.sql:112-115` yalnız `m.result='PASS' or (m.result='REVIEW' and
new.review_accepted)` kontrol ediyor. `character_definitions.sql:42-45` aynı biçimde.
`finish_moderation` ise `is_fixture=false` yazıyor (`moderation_jobs.sql:210`), yani
gerçek worker yolu zaten doğru değer üretiyor — açık olan yol **test injection'ı**.

**Sonuç:** Bugün exploit değil, çünkü hiçbir SQL yolu `is_fixture=true` yazamıyor
(grant'lar yalnız `cce_engine` ve fixture satırları Python'dan geliyor). Ama sözleşme
veritabanında yaşamıyor; ileride eklenen bir owner yazma yolu (script, yeni panel,
migration) fixture moderasyonuyla production onayı verebilir ve hiçbir test yakalamaz.

**Tasarım uyarısı — kör düzeltme testleri kırar.** Sürüm 1'in önerisi
(`and not m.is_fixture` ekle) **hemen uygulanmamalı**: izole fixture testleri onayı bu
satırdan geçiyor, eklenen koşul onları kırar. Çözüm test stratejisiyle birlikte
tasarlanmalı. İki seçenek:

- **Ortam bayrağı:** Trigger, DB tarafında ayrıca bir "test ortamı" işaretine baksın
  (`set_config` ile yalnız `test`/`local` yığınında ayarlanan bir GUC). Yalnız o zaman
  fixture kabul edilsin.
- **Kimlik ayrımı:** Fixture satırları tanınan bir provider/policy sürümüyle işaretlensin;
  trigger yalnız o sürümü kabul etsin.

Hangisinin seçileceği, test fixture akışının nasıl kurulduğuna bağlı. **Kör trigger
satırı eklemekten kaçınılmalı.**

### 10. `/media/[id]` anonim erişimde 307 + login HTML'i döndürüyor

Somut HTTP davranış hatası.

- `apps/web/src/app/media/[id]/route.ts:5` → `mediaRequest`
- `apps/web/src/lib/media.ts:8,11,13` → `redirect('/login')`

Route handler içinde `redirect()` bir **307 + `text/html`** yanıtı üretir ve exception
route handler'ın dışına çıkar; `route.ts:7`'deki `if (!response.ok)` koruması bu yola
giremez. Anonim `<img src="/media/x">` isteği login sayfasının HTML'ini 307 ile alır,
`<img>` boş kalır. Görsel endpoint'i `401`/`403` dönmeli.

İlgili: Next.js `redirect` yalnız Server Component/Action bağlamında anlamlıdır; Route
Handler'da HTTP dönüşümüne dönüşür. `lib/media.ts`'nin auth başarısızlığını bir
`authRequired` bayrağıyla bildirmesi ve `route.ts:5-7`'nin bunu `401` olarak ele alması
gerekir.

### 12. Rol yetki kontrolü yalnız `/health/ready`'de çalışıyor

`infrastructure/database.py:22-39` `database_ready()` — `cce_api` rolünün
süperuser/`bypassrls`/`createrole`/`createdb` olmadığını doğruluyor. Bu güvenlik
açısından kritik bir kontrol, ancak **yalnız** `api_entrypoint.py:69-73`'te çalışıyor;
`lifespan` (`:36-41`) yalnız `yield` ve `dispose` içeriyor.

**Sonuç:** Yanlış yapılandırılmış veya fazla yetkili `cce_api` ile deploy edilen servis
başarıyla ayağa kalkar ve tüm istekleri karşılar. `bypassrls` yetkili bir rol RLS'i
`FORCE` edilse bile atlatır. Kontrol bir **dağıtım yapılandırmasına bağımlı güvenlik
sınırı** olarak kalmış; uygulama ömrü boyunca zorlanmıyor.

**Öneri:** `lifespan`'ın `yield`'inden önce `database_ready()` çağır, başarısızsa uygulamayı
başlatma. Küçük ve düşük riskli bir değişiklik.

---

## 🟠 Orta

### 5. Rol yetki kontrolü `cce_api`'nin kendi beyanına dayanıyor

- `identity_foundation.sql:54-66`, `moderation_avatar_reader.sql:6-19` —
  `current_identity()` yalnız `cce.actor_id` / `cce.session_id` GUC'larına güveniyor.
- Özel GUC'lar için Postgres rol kısıtlaması yok; `set_config` herhangi bir rol
  tarafından çağrılabilir.

`cce_api` bağlamındaki kod `set_config('cce.actor_id', …, true)` + geçerli bir
`session_id` ile `world_owner` kimliğine yükseltebilir. Backend tarafı doğru
(`identity/repository.py:13-19`, `authentication.py:23-37`), ama bu bir **güven sınırı**
(WADR-011 Alt Karar 6) ve hiçbir migration yorumunda veya ADR'de yazılı değil.

**Öneri:** En azından `current_identity()` başına bu sınırı belgeleyen yorum. Daha güçlü
seçenek: HMAC imzalı context (API imzalar, DB doğrular).

### 7. `cce_migrator` üyeliği RLS'i tamamen atlatır

- `identity_foundation.sql:45-49` — `provision_*` politikaları `using (true) with check (true)`.
- `foundation.sql:23` — `cce_migrator` yalnız `postgres`'e verilmiş.
- Roller `nologin` olarak oluşturulmuş (`foundation.sql:13`).

Bugün böyle bir grant yok. **Sürüm 1'in önerisi hatalıydı:** `NOINHERIT` eklemek tek
başına yeterli değil — PostgreSQL'de üyelik iki ayrı izin verir (`INHERIT` ve üyelik
sırasındaki `SET`), ve `SET ROLE` yetkisi üyelikten gelir. Rol `NOINHERIT` olsa bile
`SET ROLE cce_migrator` çağrılabilir.

**Doğru çözüm:** Runtime rollerine açık revoke —
`revoke cce_migrator from cce_api, cce_engine, cce_worker_cpu, cce_worker_gpu,
cce_worker_publisher, cce_worker_maintenance`. Bu, ileride yanlışlıkla yapılacak bir
grant'i etkisiz hale getirir. Sürüm 1'in "sağlamlaştırma" önerisi bu şekilde düzeltildi.

### 2. Avatar `READY` kapısı doğrulamasız bir role açık

- `contribution_avatars.sql:23` — `grant update (status) on public.avatar_assets to cce_api`
- `:14` — tek kısıt `PENDING`/`READY` CHECK'i. Monotoniklik/doğrulama trigger'ı yok.

**Düzeltilmiş gerekçe:** Sürüm 1 bu bulguyu "onay kovasını atlatma" diye sunmuştu —
bu abartı. `cce_api` **son kullanıcı rolü değil**, backend'in kendi DB kimliğidir ve
`READY` tek başına "moderasyondan geçti" anlamına gelmez; moderasyon kanıtı
`submission_moderation` satırıdır. Gerçek konu, `cce_api`'nin bu kolonu doğrulamasız
değiştirebilmesi ve `READY → PENDING` geri çevirmenin engellenmemiş olması.

**Öneri:** Durum geçişini tek yönlü yapan bir trigger ekle; veya kolon UPDATE'unu
moderasyon ledger'ına bağlı bir `SECURITY DEFINER` yol ile değiştir
(`ops_private.mark_avatar_ready(...)`).

### 4. Her istek iki bağlantı tüketiyor

- `identity/repository.py:29-32` — her istekte `insert into public.profiles ... on
  conflict do nothing`.
- `contributions/router.py:40`, `avatar_router.py:47,56` bu çağrıyı **sonucu
  tamamen discard ederek** yalnız exception fırlatma yan etkisi için kullanıyor.
- `core/config.py:20` (`db_pool_size=3`), `database.py:13-15` (`max_overflow=0`,
  `pool_timeout=2`).

**Düzeltilmiş gerekçe:** Sürüm 1 "dördüncü eşzamanlı istek kesin 503" diyordu — bu
çıkarım kesin değil. `pool_timeout` 2 saniye, istekler milisaniye mertebesinde;
`pool_pre_ping` ve iki transaction da hızlı. Bu bir **kapasite riski ve gereksiz iş**,
garanti edilen bir hata değil. Salt-okunur GET'in yazma transaction'ı açması yine de
gereksiz WAL gürültüsü üretiyor.

**Öneri:** `actor_transaction` içinde `current_identity()` çağırarak `identity_context`'i
tek transaction'a indir; profil upsert'ini `/identity/me` veya `create_draft`'a taşı.
Havuz boyutunu (`:20`, `le=10`) threadpool ile uyumlu yap.

### 8. Denetim kaydı DB'de zorunlu değil

`guard_submission_transition` cce_engine kolunda CHANGES_REQUESTED / REJECTED /
APPROVED geçişlerini `submission_feedback` veya `contribution_events` satırı olmadan
geçiriyor (`contribution_review.sql:105-117`). `owner_feedback` politikası (`:66-70`)
feedback'in geçişten **sonra** yazılmasını şart koşuyor → hiç yazılmaması da meşru
görünüyor. Denetim izi kopabilir.

**Öneri:** `CONSTRAINT TRIGGER … DEFERRABLE INITIALLY DEFERRED` ile commit anında varlık
doğrulaması.

### 9. Moderasyon retry'i denetim kaydı üretmiyor

`review.py:114-135` — `retry_moderation` `actor` parametresi almıyor, `record_event`
çağırmıyor; versiyon artmadığı için `contribution_events`'teki
`unique(submission_id, resulting_version)` kısıtı yüzünden yazılamaz da.
`moderation_jobs.requested_by` atfı koruyor ama `contribution_events` akışında iz yok —
Owner sınırsız retry tetikleyebilir.

**Öneri:** Deneme kimliği yazan ayrı bir tablo (`moderation_retries`), veya
`contribution_events`'te attempt kimliği.

### 11. Web'de zod şeması Pydantic'in elle kopyası, CI doğrulamıyor

`apps/web/src/features/character-submissions/proposal-form.tsx:34-44` — zod şeması
`schemas.py:7-45`'in elle kopyası. CI yalnız `schema.d.ts`'i yeniden üretip diff'liyor
(`ci.yml:38-39`); zod kopyasının sözleşmeyle eşleştiğini hiçbir şey doğrulamıyor.
Backend'de `max_length` değişirse web sessizce 422 üretmeye başlar.

Aynı dosya `:78` — `} as Proposal;` cast'i, `Object.fromEntries` yüzünden alan adı
yazım hatasının derleme zamanında yakalanmasını engelliyor.

### 13. HTTP durum kodu yüzeyi kayboluyor

- `apps/web/src/lib/contributions.ts:40` — 404/409/422/429/503 tek bir `error` string'ine
  indirgiyor.
- `apps/web/src/lib/identity.ts:20,23` — network hatası ve non-OK yanıt `return null` →
  `admin/reviews/page.tsx:8` **200 OK** ile "Owner yetkisi doğrulanamadı." render ediyor.

`media/[id]/route.ts:7` doğru davranıyor (upstream status korunuyor) — tek istisna bulgu 10.

### 14. pgTAP paketi ağırlıklı olarak katalog/grant denetimi

**Düzeltilmiş ifade:** Sürüm 1 "pgTAP tamamen katalog testi" demişti — bu yanlıştı.
`foundation.test.sql:27-30` gerçekten canlı sorgu ve `throws_ok` çalıştırıyor (rol
taklidiyle RLS üzerinden okuma + yazma reddi).

Doğru ifade: paket **ağırlıklı olarak** grant/RLS kataloğunu doğruluyor.
`guard_submission_transition`, `guard_submission_avatar`, `guard_character_definition`
ve `enqueue/claim/finish` için **davranışsal assertion yok** — bu tetikleyicilerin
gevşetilmesi pgTAP adımını geçer, davranış kapsamı Python entegrasyon testlerine
düşüyor (`test_contributions_integration.py`, `test_review_integration.py`,
`test_definition_integration.py`, `test_moderation_jobs_integration.py`).

**İlgili CI riski:** `foundation.test.sql:2` `create extension … with schema extensions`
yapıyor ama dosya `:41`'de `rollback` ile bitiyor → eklenti transaction ile geri
alınıyor. Yalnız bu dosya `search_path`'i ayarlıyor (`:25`); diğer 6 dosya ayarlamıyor.
Temiz veritabanında ilk `supabase test db` koşusunun başarısı belirsiz.

### 15. `active_attempt_id` referans bütünlüğü yok

`moderation_jobs.sql:18` — `active_attempt_id uuid` üzerinde FK yok. Constraint yalnız
`state='RUNNING'` iken non-null olmasını şart koşuyor (`:24-25`); attempt'ın bu işe ait
ve `RUNNING` olduğu DB'de doğrulanmıyor. `moderation_attempts` tarafında da iş başına
tek `RUNNING` deneme garantisi yok (`:44` yalnız `(job_id, attempt_number)` UNIQUE).

`auth_worker_user_id` için kısmi index ile yapılan güvenliğin (`reader:46-48`) kendi iş
kuyruğunda karşılığı yok.

### 16. Başarısız avatar yüklemesi kalıcı yetim bırakıyor

`avatar_router.py:50-58` iki fazlı: `reserve_avatar` (PENDING) → `storage.store` (ağ) →
`attach_avatar` (READY). İkinci transaction başarısız olursa (ör. sürüm çakışması → 409)
asset DB'de `PENDING` kalıyor, Storage nesnesi de kalıyor ve hiç temizlenmiyor. Kota
(`avatars.py:65-73`, 100 toplam / 20 günlük) bu yetimlerle dolabilir. `cce_worker_maintenance`
rolü foundation'da tanımlı ama kullanılmıyor.

### 17. JWKS hata sınıflandırması

`authentication.py:13` — `PyJWKClient(url, lifespan=60, timeout=3)`. Supabase yeni anahtar
döndürdüğünde cache 60 saniye eski JWKS'i sunuyor; bu sürede yeni imzalı token alan
kullanıcılar `PyJWKClientError` alıyor → `:40` `PyJWTError` kolunda yakalıyor → **401**.
Altyapı sorunu kullanıcıya "kimliğiniz geçersiz" diye yansıyor.

**Düzeltilmiş öneri:** Sürüm 1 "bilinmeyen anahtarı 503 yap" diyordu — bu yanlış olurdu,
çünkü **sahte/geçersiz imzalı token'lar da bilinmeyen `kid` taşır** ve 503'e düşerdi.
Doğru yaklaşım: `kid` bilinmiyorsa JWKS cache'ini zorla yenileyip tekrar denemek; yeniden
denemeden sonra da eşleşme yoksa 401 dönmek. PyJWT'nin `refresh=True` davranışı
değerlendirilmeli. Yalnız `PyJWKClientConnectionError` 503'e gitmeli (mevcut doğru davranış).

---

## 🟡 Düşük (seçilmiş)

| Bulgu | Konum | Not |
| :-- | :-- | :-- |
| `scope="function"` → commit, response serileştirilmeden önce | `contributions/router.py:52,63,70,79,92,105,116,127` | Tasarım tuzağı; pratikte `read_one` doğrulama katmanı zaten transaction içinde çalıştığı için şu an zararsız |
| 500 hatalarının hiç loglanmıyor; `raise … from None` bağlamı düşürüyor | `infrastructure/telemetry.py:54,71` | |
| `assert` üretim kodunda (`python -O` altında kaybolur) | `characters/repository.py:115` | |
| `v.version = 1` sabiti — migration `version`'ı yükselttiğinde deploy sırası bağımlılığı | `infrastructure/database.py:31` | |
| `Settings` ve `WorkerSettings` aynı `env_prefix` + göreli `env_file` kullanıyor | `core/config.py:12`, `moderation_service.py:32` | Farklı CWD'den çalıştırmada sessizce farklı config |
| 422 yanıtları `input_value` ile reddedilen değeri yankılıyor | `contributions/schemas.py:86` | Çağıranın kendi verisi; çapraz-kullanıcı sızıntısı değil |
| Doğrulama hatası sarmalaması tutarsız (500 yerine 503 beklenir) | `contributions/repository.py:35`, `identity/repository.py:56` | |
| `moderation_jobs` FK index'leri eksik (parent DELETE/UPDATE seq scan) | `moderation_jobs.sql:10`, `reader:44` | |
| `contribution_events` / `identity_audit` için hiçbir rol SELECT grant'i yok | `contribution_drafts.sql:57`, `identity_foundation.sql:22-32` | Acil müdahale yolu dar |
| `cce_worker_gpu/publisher/maintenance` şema USAGE'ye sahip, nesne grant'i yok | `foundation.sql:33-36` | Kullanılmayan iskelet |
| Migration'lar idempotent değil, rollback/down planı yok | tüm `supabase/migrations/*` | |
| `loading.tsx` / `error.tsx` / `not-found.tsx` yok; sayfa koruması üç farklı desen | `apps/web/src/app/**` | |
| Onay checkbox'ları zorunlu değil (`z.boolean()`), backend de zorlamıyor | `proposal-form.tsx:42`, `schemas.py:44-45` | Ürün kararı; gönderim kapısı olarak test edilmemiş |
| `aria-describedby` eksik, sayısal alanlarda hata mesajı hiç gösterilmiyor | `proposal-form.tsx:122-124` | |
| Repo sağlığı dosyaları yok: LICENSE, CONTRIBUTING, SECURITY.md, dependabot, CODEOWNERS | `.github/` | |
| CI'da `playwright` `retries: 0` → kararsız test flake riski | `playwright.config.ts:4` | |

> **Sürüm 1'den kaldırılan düşük bulgu:** `config.toml`'daki
> `[storage.s3_protocol] enabled = true` için "Storage RLS'ini atlar" ifadesi
> **yanlıştı**. S3 protokolü tek başına bir yetki modeli değildir; istek hangi kimlik
> bilgisiyle geliyorsa onun politikası uygulanır. `service_role` ile gelen istek zaten
> normal yollarda da RLS'i atlar. Sürüm 1'deki genelleme protokolü kimlikten bağımsız
> saymıştı.

---

## ✅ Doğrulanmış iyi desenler

Bunlar düzeltilmemeli, yeni özelliklerde de korunmalı:

1. **Varsayılan "reddet".** `current_identity()` GUC ayarlanmamışsa NULL döner → RLS hiçbir
   satır göstermez. `actor_transaction` bir yerde unutulsa bile sızıntı değil, **veri
   kaybı** olur (fail-closed). `identity/repository.py:11`.
2. **Fencing token.** Worker claim → bağlantıyı bırak → tara → `active_attempt_id` +
   `lease_until` ile kapat. Süresi dolmuş işin geç sonucu sessizce düşüyor.
   `moderation_worker.py:97-149`, `moderation_jobs.sql:176-179`.
3. **Transaction atomikliği.** `start_review` satır kilidini alıp kuyruğa alma ve durum
   geçişini tek transaction'da yapar (`review.py:75-111`) — ara durum gözlenemez.
   *(Bu, sürüm 1'de hatalı olarak "yarış koşulu" raporlanan bulgunun doğru okumasıdır.)*
4. **Kilit sırası tutarlılığı.** `finish` ve `enqueue` submission → job sırasını kullanıyor,
   `claim` submission kilitlemiyor. `moderation_jobs.sql:172-175` yorumlu.
5. **DB, Python'u bağımsız doğruluyor.** `guard_character_definition` artifact'in
   `source` nesnesini SQL'de yeniden kurup karşılaştırıyor; `read_definition` her
   okumada `artifact_hash` yeniden hesaplıyor. `character_definitions.sql:49-65`,
   `characters/repository.py:28`.
6. **Prompt injection ayrımı.** Katkı metni system prompt'a girmiyor;
   `secret_proposals` / `known_people` / `initial_goals` payload'a bile girmiyor.
   `characters/compiler.py:16-24, 95-104`.
7. **Private medya optimizer'a uğramıyor.** `next/image` yerine ham `<img>` +
   same-origin `/media/{id}`, `Content-Type` sabitlenmiş, `nosniff` + `no-store`.
   `private-avatar.tsx:4-6`, `media/[id]/route.ts:6,9`.
8. **Fixture dürüstlüğü.** Test verdict'ları arayüzde açıkça etiketleniyor, aktivasyon
   izni olarak sunulmuyor. `review-panel.tsx:69`, `definition-panel.tsx:29`.
9. **`'use client'` yayılımı yok.** 11 bileşenin 3'ü client; üçü de gerçekten etkileşim
   zorunlu. `auth-form.tsx` progressive enhancement sunuyor (JS'siz de çalışıyor).
10. **Kayıtta rol enjeksiyonu yok.** `signUp` yalnız email/password iletiyor, `options.data`
    çağırdan gelmiyor. `(auth)/actions.ts:28-31`.
11. **Sürüm iyimser kilidi her mutasyonda.** `expected_version` tüm mutasyonlarda geçiyor,
    backend 409 döndürüyor. DB trigger'ı `version+1`'i ayrıca zorunlu kılıyor.
12. **`search_path = ''` her yerde.** Tüm `SECURITY DEFINER` fonksiyonlarda ve `guard_*`
    trigger'larında sabit; trigger'lar invoker (RLS atlatmıyor).
13. **Yazmayan rol reddediliyor.** `guard_submission_transition` üçüncü kolda (`review:121-122`)
    `42501` ile düşüyor — `service_role` dışında tabloya erişebilen hiçbir rol bypass edemez.
14. **Revizyon/denetim korunuyor.** `contribution_events` tek yönlü append-only;
    `submission_moderation` PK'si revizyon başına tek verdict.

---

## Önerilen düzeltme sırası

**Önce (gerçek boşluk ve somut hatalar):**
1. **Bulgu 6** — `is_fixture` sınırını DB'ye taşı. *Test stratejisiyle birlikte
   tasarlanmalı; kör trigger satırı izole fixture testlerini kırar.*
2. **Bulgu 10** — `/media/[id]` route handler'da `401` döndürsün.
3. **Bulgu 12** — `lifespan` başlangıçta `database_ready()` çağırsın.

**Sonra (belge + sağlamlaştırma):**
4. Bulgu 5 — güven sınırını `current_identity()` yorumunda belgele
5. Bulgu 7 — `revoke cce_migrator from <runtime rolleri>` (NOINHERIT değil)
6. Bulgu 13 — HTTP durum kodu ayrımı
7. Bulgu 11 — zod ↔ Pydantic sözleşme testi
8. Bulgu 2 — avatar durum geçişine tek yönlülük

**Bakım:**
9. Bulgu 4 (transaction sayısı), 8, 9, 14 (trigger davranış testleri), 15, 16, 17
10. Düşük öncelikli temizlikler

---

## Test kapsamı özeti

| Katman | Kapsam |
| :-- | :-- |
| pgTAP (7 dosya) | **Ağırlıklı olarak** grant/RLS kataloğu; `foundation.test.sql:27-30` canlı sorgu içeriyor. Trigger davranışı kapsanmıyor. |
| Backend birim (non-integration) | 81 test — kimlik, moderasyon worker, avatar decode, derleyici, health |
| Backend integration | 33 test — gerçek DB/Auth, rol sınırları, eşzamanlılık, pgTAP, tarayıcı |
| Frontend birim (vitest) | 7 test — `apiBaseUrl` SSRF, config, health panel |
| E2E (playwright) | 4 senaryo — signup/SSR, review döngüsü, retry, derleme |

**Boşluklar (yüksek öncelik):** zod ↔ Pydantic sözleşme testi; onay checkbox'ları
zorunluluğu; avatar reddedilme yolları (415/422/413); HTTP durum kodu yüzeyi
(404/409/429); `/media/[id]` yetkilendirme; auth hata yolları.

**Bulgu 6 için not:** Mevcut izole fixture testleri (`test_review_integration.py`,
`test_definition_integration.py`) fixture moderasyonuyla onay verdiği için, DB
kısıtı eklenirken bu testlerin nasıl ayırt edileceği önceden karara bağlanmalı.

---

## Yeniden inceleme notu

Bu rapor 2026-09-29 tarihinde `f687907` commit'i üzerinde alınmıştır. Sürüm 2, kod
karşılaştırması sonrası düzeltilmiş gerekçeleri içerir. Bulgular düzeltildikçe dosya
güncellenmelidir; yeni migration'lar veya endpoint'ler eklendiğinde **6 numaralı madde**
(veritabanı seviyesinde fixture sınırı) yeniden doğrulanmalıdır.
