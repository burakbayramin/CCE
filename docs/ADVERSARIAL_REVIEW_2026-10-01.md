# CCE Karşıdan Güvenlik İncelemesi — 2026-10-01

**Kapsam:** `f687907`'den sonraki tüm değişiklikler — 4 yeni migration
(`20260930110443`, `20260930110756`, `20260930111403`, `20260930130956`) ve commit'li
uygulama katmanı. İki paralel inceleme (veritabanı / uygulama) + her bulgunun kaynakta
doğrulanması.

**Yöntem:** Salt okunur inceleme. Hiçbir bulgu için düzeltme yapılmadı; bu dosya
yalnızca kayıttır. İnceleme sırasında **hiçbir yeni migration çalıştırılmadı** — bu
makinede Docker yok, dolayısıyla `supabase db reset`, pgTAP ve integration testleri
koşmadı. Aşağıdaki hiçbir SQL iddiası çalıştırılarak doğrulanmadı.

**İlk durum:** Raporlayıcı önerisi. İlk incelemede hiçbir düzeltme yapılmadı.

**Uygulama takibi (2026-10-01):** B-1 için yeni migration, avatar INSERT'inde
`PENDING` şartını ve mevcut UPDATE değişmezliğini aynı trigger'da zorlar; şema
hazırlık işareti bu güvenlik sınırı için `2 → 3` yükseltilir. API rolüyle sahte
`READY` INSERT'ünün reddini sınayan entegrasyon testi ve INSERT/UPDATE trigger
kapsamı için pgTAP kontrolü eklendi. Bu testler gerçek DB'de henüz çalıştırılmadı;
B-1 bu yüzden **kodda giderildi, DB doğrulaması bekliyor** durumundadır.

B-3'ün "gerçek SQL hiç test edilmiyor" iddiası eksikti: mevcut
`test_local_api_role_and_readiness`, `TestClient(create_app(config))` ile gerçek
DB'de pozitif başlangıç ve `/health/ready` yolunu zaten çalıştırıyordu. Buna
ek olarak, marker'ı veya paylaşılan test DB'sini değiştirmeden gerekli sürümü
bilinçli olarak yanlış ayarlayıp `database_ready=False` ve startup reddini
doğrulayan negatif entegrasyon testi eklendi. Testin gerçek DB/CI sonucu bekleniyor.

B-4'teki yinelenen, erişilemeyen Owner engine koruması kaldırıldı. Katkıcı ve
Owner avatar okuma dalları ile `READY`/`PENDING` yanıtları DB gerektirmeyen
testlerde ayrı ayrı doğrulandı. Yetki rolü ayrımı değiştirilmedi; B-4 kod
düzeyinde kapalıdır.

**Önceki kayıt:** `docs/CODE_REVIEW_2026-09-29.md` (sürüm 2 + 2026-09-30 uygulama
notu) — o 17 bulgunun durumunu kapsar. Bu dosya yalnız 2026-10-01 tarihli
karşıdan incelemenin bulgularını içerir ve **o dosyanın yerine geçmez**.

---

## Özet

İnceleme 2 yüksek, 8 orta, 8 düşük bulgu ve 23 yanlış alarm raporladı. Raporlayıcının
kendi doğrulamasında **iki yüksek bulgunun biri düşürüldü** (gerekçesi aşağıda) ve
üç bulgunun önceliği yeniden ölçeklendirildi.

Net sonuç: **bir gerçek ve ucuz güvenlik düzeltmesi**, bir **test kapsamı boşluğu
(production'ı düşürebilir)**, bir **güvenlik yolunda okunabilirlik/ölü kod**, ve
kalanı **dayanıklılık ve sözleşme sertleştirme** maddeleri.

| Alan | Sonuç |
| :-- | :-- |
| SQL injection | Yok — tüm `text()` çağrıları bound parameter |
| RLS atlatma (yeni nesnelerde) | Yok — `anon`/`authenticated`/`service_role` şema USAGE'ı bile yok |
| Avatar `READY` garantisi | **Kısmi** — UPDATE korumalı, INSERT korumasız (B-1) |
| Denetim izi bütünlüğü | **Kırılgan** — kontroller sürüm aritmetiğine bağlı (B-2) |
| Başlangıç kapısı (`database_ready`) | Gerçek veritabanında **hiç test edilmemiş** (B-3) |
| Yanlış alarm | 23 — aşağıda özetlendi |

---

## 🔴 Yüksek

### B-1 · Avatar `READY` garantisi INSERT yolunda yok

**Konum:** `supabase/migrations/20260930110756_avatar_and_moderation_integrity.sql:15-16`
(trigger tanımı) · `20260924161331_contribution_avatars.sql:14,22,25-29` (kaynak koşullar)

**Doğrulandı.** `guard_avatar_status` yalnızca `before update` olarak tanımlı. Ancak:

- `contribution_avatars.sql:22` — `grant select,insert on public.avatar_assets to cce_api`
- `:14` — `status` için tek kısıt `check (status in ('PENDING','READY'))`
- `:25-29` — `own_avatar` politikasının `with check`'i yalnız `user_id = cce.actor_id` ve
  `exists(current_identity())` kontrol ediyor; **`status` kolonuna hiç bakmıyor**

Sonuç: `cce_api` bağlamındaki bir INSERT `status='READY'` yazabilir — Storage'da hiç
byte doğrulanmadan, keyfi `sha256`/`byte_size` ile. `guard_submission_avatar`
(`contribution_avatars.sql:52-55`) yalnız `status='READY'` aradığı için bunu kabul eder.
`moderation_jobs.avatar_sha256` sahte hash'e göre dolar
(`20260926095425_moderation_jobs.sql:75`), dolayısıyla `moderation_avatar_path`
(`20260929102208_moderation_avatar_reader.sql:93-94`) ve `finish_moderation`
(`20260926095425:198`) gerçekte var olmayan ya da eşleşmeyen bir Storage nesnesini
işaret eder.

**Etki:** Bugün exploit **değil** — uygulama bu yolu kullanmıyor. `avatars.py:76-79`
INSERT'te `status` yazmıyor (default `PENDING`), `:102` UPDATE ile `READY` yapıyor.
Ama yeni migration'ın kendi yorumu (`:4-5`) "READY = API byte'ları doğruladı" diyor ve
**bu değişmezlik veritabanında zorlanmıyor.** Yani tam olarak kapatmayı amaçladığı sınır
yarım kalmış.

**Önerilen düzeltme (tek satır):** trigger'ı `before insert or update` yapıp INSERT
dalında `new.status='PENDING'` zorunlu kıl. Ya da `own_avatar` politikasının
`with check`'ine `and status='PENDING'` ekle.

> **Raporlayıcı notu:** Bu konu `docs/CODE_REVIEW_2026-09-29.md` sürüm 2'de "Bulgu 2 —
> kısmi, düşük" diye değerlendirilmişti. Karşıdan inceleme daha keskin bir yön buldu:
> sorun `READY`'nin geri çevrilemezliği değil, **hiç doğrulanmamış olarak yazılabilmesi**.
> Öncelik yeniden yükseltildi.

---

## 🟠 Orta

### B-2 · `contribution_events` kirliliği — kontrol atlatma değil, denetim izi bozulması

**Konum:** `20260923130347_contribution_drafts.sql:68-71` (politika),
`:41` (unique), `:55` (version UPDATE grant'ı) · `20260924053912_contribution_review.sql:16-19` (action CHECK)

**İnceleme şunu iddia etti ve raporlayıcı bunu doğrulayamadı:** katkıcı `APPROVED`
sahte olayı yazarak `require_review_audit`'i kandırır ve Owner'ın karar vermesini
kalıcı engeller.

**Neden geçerli değil — izlenen kanal:** `own_contribution_event` politikası
(`:68-71`) `resulting_version = s.version` şartı koyuyor; yani V sürümlü bir olay
yazmak için başvuru o **an** V sürümünde olmalı. Ama:

- `guard_submission_transition` (`20260923130347:83`) sürümü her UPDATE'te tam +1
  artırıyor
- `20260924053912:94-104` — `cce_api` yalnız `DRAFT→DRAFT`, `DRAFT→SUBMITTED`,
  `CHANGES_REQUESTED→DRAFT` ve `→WITHDRAWN` yapabiliyor

Yani katkıcı sürümü yalnız **DRAFT iken**, en fazla M'e kadar ilerletebiliyor. Sonrasında
SUBIT → M+1, START_REVIEW → M+2, karar → **M+3**: üçü de ışgal aralığının dışında.
Owner'ın kararının düşeceği sürüm asla ışgal edilemez, sahte olay
`require_review_audit`'i **sağlayamaz**. DoS yalnızca katkıcının kendi gönderimini
bloke eder — kendi kendine zarar.

**Gerçek olan kısım:** `contribution_review.sql:16-19` CHECK'i `APPROVED`,
`START_REVIEW`, `REJECTED` gibi karar aksiyonlarına izin veriyor ve
`own_contribution_event` politikası `action` kolonuna **hiç bakmıyor**. Katkıcı DRAFT
sırasında kendi adına sahte `APPROVED` satırları yazabilir. Bu **denetim izi
kirliliği** — kontrol atlatma değil. Üstelik `contribution_events` tablosuna hiçbir
rolün SELECT grant'i olmadığı (`20260923130347:57` yalnız INSERT) bugün kimse SQL ile
okuyamıyor.

**Yine de düzeltmeye değer**, çünkü `require_review_audit` trigger'ının bütünlüğü şu
an sürüm aritmetiğine bağlı, olay tablosunun güvenilirliğine değil. Sürüm protokolü
değişirse (ör. toplu geçiş) bu bağımlılık sessizce kırılır.

**Önerilen düzeltme (tek satır):** politikaya
`and action in ('CREATED','SAVE','SUBMIT','WITHDRAW','REVISE')` ekle. Karar
aksiyonları yalnız Owner'a bağlı kalsın.

---

### B-3 · Başlangıç kapısı gerçek veritabanında hiç test edilmemiş

**Konum:** `services/backend/src/cce/infrastructure/database.py:29-38` (sorgu),
`services/backend/src/cce/api_entrypoint.py:39` (lifespan),
`services/backend/tests/test_health.py:24,26,38,56,81` (tümü monkeypatch)

`database_ready` artık **hard boot gate**. `git` araması yapıldı: fonksiyonun yalnız
iki giriş noktası var — lifespan (`api_entrypoint.py:39`) ve readiness (`:74`). **Hiçbir
test gerçek SQL'i gerçek Postgres'e çalıştırmıyor.** Tüm testler
`api_entrypoint.database_ready`'i monkeypatch'lıyor.

**Etki:** Sorguda bir yazım hatası — `rolcreatedb` kolon adı, `:version` bağlama
parametresi, `ops_private.schema_version` üzerindeki `CROSS JOIN` (`cce_api` bu tabloyu
yalnız `api_read_schema_version` politikasıyla okuyabilir,
`20260922131025_foundation.sql:32-33`) — `checks` job'ının tamamını geçer ve her üretim
açılışında crash-loop üretir.

**Önerilen düzeltme:** İki integration testi:
`database_ready(create_database(config))` → `True`; ardından
`update ops_private.schema_version set version=3` sonrası → `False`.

> **Uyarı:** Bu test integration işaretli ve çalıştırılmadan yazılamaz. Makinede Docker
> olmadığı için raporlayıcı bu testi yazmadı — doğrulanmamış test yazmak, doğrulanmamış
> düzeltme yazmaktan farksızdır. CI'da çalıştırılmalı.

---

### B-4 · Ölü kod bir yetkilendirme yolunda

**Konum:** `services/backend/src/cce/modules/contributions/avatar_router.py:106-115`

```python
with actor_transaction(api_engine, actor) as connection:
    identity = identity_context(connection, actor)
    if identity["role"] == "world_owner":
        if owner_engine is None:                  # :107-108
            raise ContributionError(503, ...)
    else:
        asset = read_asset(connection, asset_id)  # :110
if identity["role"] == "world_owner":
    if owner_engine is None:                      # :112-113  ← ölü
        raise ContributionError(503, ...)
```

`:112-113` **erişilemez**: `:111`'e `role == 'world_owner'` ile ulaşan her yol için
`:107-108` zaten geçmiş olmalı. Raporlayıcı bu satırları doğrudan okuyarak doğruladı.

**Yetkilendirme değişikliği değil.** Katkıcı için `read_asset` hâlâ `api_engine`
altında `own_avatar` politikasıyla (`20260924161331:38-41`), owner için `owner_engine`
altında `owner_avatar` ile (`:42-43`) çalışıyor. Kapsama bozulmamış.

**Maliyet:** iki havuz çıkışı, `role` string'inin kontrol akışı bayrağı olarak
kullanılması, ve — asıl önemlisi — bir gözden geçiren kişi artık owner/katkıcı
ayrımını tek bakışta **göremiyor**. Bu, görünürlüğü en kritik olması gereken yol.

**Önerilen düzeltme:** Tek `owner_engine is None` korumasıyla
`if role != 'world_owner': <api_engine oku> else: <owner_engine oku>` biçimine indir ve
`asset.status != 'READY'` kontrolünü transaction'ın içine geri al.

---

### B-5 · Avatar decode, kimlik kontrolünden önce çalışıyor

**Konum:** `avatar_router.py:47-48` (`AvatarStorage` + `verify_image`) vs `:50`
(`identity_context`)

Eski sıra: `identity_context` → `AvatarStorage` → `verify_image`. Yeni sıra tersi.
JWT yine de `verified_actor` (`:74`) ile önce doğrulanıyor, dolayısıyla **yetki atlama
değil**. Ancak DB'de iptal edilmiş / yasaklanmış / oturumu sonlanmış bir aktör, reddedilmeden
önce tam bir Pillow decode'u tetikliyor.

`verify_image` sınırları (`images.py:22-23`: 512 KiB, 2048 piksel, tek kare,
`:45` DecompressionBomb yakalıyor) nedeniyle bu **mütevazı bir CPU amplifikasyonu**,
DoS değil.

**Önerilen düzeltme:** `identity_context`'i `verify_image`'dan önce geri al —
artık `Connection` aldığı için kısa bir transaction açmak kolay.

---

### B-6 · `check_proposal_contract.py` bir limit kayması dedektörü, şema eşitliği değil

**Konum:** `scripts/check_proposal_contract.py:15-37`

Çıkarılanlar: string `maxLength` (`:16-19`), dizi `maxItems`/`maxLength` (`:20-24`),
eksen ve yaş `minimum`/`maximum` (`:29-33`), boolean alan adları (`:34-36`),
`schema_version` default'u (`:26`).

**Çıkarılmayanlar:** `min_length`, `required`, `strip_whitespace`, `extra="forbid"`,
ve JSON tipi string/array/integer/boolean olmayan hiçbir alan.

Somut boşluklar:
- `ShortText` `min_length=1` (`schemas.py:7`) — 2'ye çıkarılırsa kontrol görmez
- `CharacterProposal.model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)`
  (`schemas.py:21`) — değişimi görünmez
- İç içe bir nesne veya `Literal` alan eklenirse her iki taraftan da sessizce çıkarılır;
  kontrol geçer, form alanı hiç render edilmez

**Etkiyi sınırlayan iki doğru karar:** `proposal-fields.test.ts:6-9` alan
*kapsamının* eşit olduğunu doğruluyor ve `proposal-form.tsx:21-27` limitleri sabit
literal'lerden değil `contract.*`'ten okuyor. Yani kapsam ve limit yayılımı korumalı;
yalnız **Pydantic → contract** kenarı eksik.

**Önerilen düzeltme:** `min_length`, sıralanmış `required` ve alan-anahtar kümesi
eşitliğini de karşılaştır.

---

### B-7 · `claim_moderation` tek bozuk işte tüm kuyruğu durdurabilir

**Konum:** `20260930110756:27-28` (`moderation_attempts_one_running_per_job`),
`20260926095425_moderation_jobs.sql:134-157` (claim döngüsü)

Yeni partial unique index doğrudur ve mevcut kod yolları ihlal üretmez. Ama ihlal bir
kez oluşursa (elle düzeltilmiş bir veri satırı, ya da `:129-130`'daki `state='RUNNING'`
eşleşmezken `:131`'in job'ı yine ERROR'a çevirmesi gibi bir durum) `create unique index`
ihlali `claim_moderation`'ın **tamamını** 23505 ile geri alır. Döngüde istisna yakalama,
`SAVEPOINT` veya "bu işi atla" yolu yok.

**Etki:** `cce_worker_cpu` tek bir bozuk job yüzünden hiç iş claim edemez; Owner'ın
retry'ı da aynı job'a yönlendiği için kurtarma yolu kalmaz.

**Önerilen düzeltme:** Claim döngüsünü `EXCEPTION WHEN unique_violation` bloğuyla sarıp
işi atlayacak yol ekle. (Bu bir **ölü kilit değil**, 23505 ile tüm claim'in geri
alınması — daha sessiz bir arıza modu.)

### B-8 · Fixture bayrağı veritabanı genelinde, kilitsiz

**Konum:** `20260930110443:6-14` (bayrak), tüketiciler
`tests/test_review_integration.py:88-117` ve `scripts/setup_local_db.py:35-38`

Bayrağın değiştirilmesi tek satırlık bir UPDATE ve hiç kilidi yok — repo'nun kendi
kilit geleneği bunun tersi (`bootstrap_world_owner` `20260923105328:87`,
`claim_moderation_for_worker` `20260929102208:57` advisory lock kullanıyor).

Bayrak ayrıca **veritabanı genelinde tek bir boolean**; `guard_fixture_approval:27-33`
yalnız `is_fixture`'a bakar. Yani `enabled=true` iken herhangi bir testin işaretlediği
herhangi bir fixture revision'ı onaylanabilir; `enabled=false` iken meşru bir test
onayı reddedilir. `test_review_integration.py:88-117` bayrağı `finally` bloğunda geri
açıyor — **paralel koşuda (`pytest-xdist`) veya iki yığın aynı DB'yi paylaşıyorsa bir
testin `finally`'si diğerinin kararının ortasında ateşlenebilir.**

CI şu an sıralı çalıştığı için ılı. Kilit sırasına uymak için
`pg_advisory_xact_lock` mantığı veya bayrağı `(submission_id, revision_id)` ile
eşleştirmek daha sağlam olur.

### B-9 · `moderation_retry_events` "denetim kaydı" ama değerleri uygulama iddiası

**Konum:** `20260930111403:33-52` (politika),
`services/backend/src/cce/modules/contributions/review.py:137-149` (yazar)

Politika yalnız `actor_user_id = cce.actor_id`, çağıranın `world_owner` olması ve
`job_id`'nin var olmasını doğruluyor. `previous_state` ve `previous_attempt_number`
için **hiçbir** veritabanı kısıtı yok — `moderation_jobs.state` ile karşılaştırılmıyor.
Ayrıca bu tabloya hiçbir rolün SELECT grant'i yok, yani **yazan rol (`cce_engine`) yazdığı
kaydı okuyamıyor.**

`retry_moderation` ayrıca `previous_state`'i `enqueue_moderation`'dan **önce** okuduğu
`review.moderation_job`'tan alıyor, yani iki okuma arasında durum değişmiş olabilir:
kayıt gerçekte ne değiştiğini değil, ne **göründüğünü** belgeliyor. Aynı migration'ın
`:4-5`'teki "API'nin yazmayı unutmasına güvenmeyelim" ilkesiyle çelişiyor —
`enqueue_moderation` durumu değiştiriyor ama hiçbir yerde kayıt yazmıyor.

**Önerilen düzeltme:** Kaydı `enqueue_moderation` içine taşı, `previous_state` /
`previous_attempt_number`'ı UPDATE'in `old` imajından oku.

---

## 🟡 Düşük

| Bulgu | Konum | Not |
| :-- | :-- | :-- |
| `/media` API kesintisinde sanitize edilmemiş 500 veriyor | `apps/web/src/app/media/[id]/route.ts:5`, `lib/media.ts:13` | `media.ts:13`'teki `fetch` guard'sız; route handler `app/error.tsx` kullanmıyor. Kullanılabilirlik + tutarsız hata yüzeyi, sızıntı yok |
| `proxy.ts` matcher'ı `/media`'yi kapsamıyor | `apps/web/src/proxy.ts:27` | `media.ts:8` `writable=false` kullandığı için token yenilemesi zaten kalıcı olamaz. Etkisi `private-avatar.tsx:6`'nın `/contributor/drafts/[id]` içinde render edilmesi sayesinde pratikte yok |
| `error.tsx` `IdentityUnavailable.status` ayrımını atıyor | `apps/web/src/app/error.tsx:9-12` | Güvenlik sorunu değil — maskeleme doğru ve kasıtlı. Yalnız operatör "503 mü, 502 mi, ağ mı" ayırt edemiyor |
| Sürüm geçidi ara migration'ların varlığını doğrulamıyor | `20260930130956:6-13` | Yalnız `version=1` kontrol ediyor. `supabase` isim sırasıyla uyguluyor ve zaman damgaları sıralı, bu yüzden pratikte kapalı |
| `fixture_approval_allowed()` `cce_engine`'e açık | `20260930110443:22` | Salt okunur boolean; "fixture kaçışı şu an açık" bilgisi istismar öncesi değerleme için kullanılabilir |
| `migrator_fixture_policy` tüm komutlara açık | `20260930110443:13-14` | Singleton satırı `cce_migrator` tarafından silinebilir. `coalesce(...,false)` sayesinde **fail-closed** — güvenli, ama teşhisi zor |
| `guard_fixture_approval` `AND` kısa devresine bağlı | `20260930110443:27-33` | `cce_api`'nin bu fonksiyonda EXECUTE'u yok. Koşul yeniden yazılırsa katkıcının meşru UPDATE'i 42501 ile kırılır. SQL standartı değerlendirme sırasını tanımlamaz |
| `moderation_retry_events` indeks ve okunabilirlik eksik | `20260930111403:42-46` | `actor_user_id` üzerinde indeks yok; diğer tüm denetim tablolarında var |

---

## ❌ Yanlış alarm (görünüşte sorunlu, aslında güvenli)

İnceleme 23 yanlış alarm raporladı. Doğrulanan ve kayda değer olanlar:

1. **Trigger sıralaması çakışmıyor.** `character_submissions` üzerindeki üç BEFORE UPDATE
   trigger'ı alfabetik sırayla `block_fixture_approval` → `guard_submission_avatar` →
   `guard_submission_transition`. Üçü de yalnız `raise` yapıyor; tek `NEW` değiştiren
   `guard_submission_transition` (`new.updated_at := now()`) ve zaten en son ateşleniyor.
   Hiçbir diğerinin etkisini ezemiyor.

2. **Deferrable FK doğru ve gerekli.** `conftest.py:118-129` attempt'leri job'lardan
   **önce** silmek zorunda; `INITIALLY DEFERRED` olmasa test temizliği kırılırdı.
   Kolon eşleşmesi de doğru: yerel `(id, active_attempt_id)` ↔ uzak `(job_id, id)`.

3. **Eksik `revoke` yok.** `20260922131025_foundation.sql:45-46`
   `alter default privileges for role cce_migrator revoke execute on functions from
   public` bunu önceden kapatıyor ve yeni migration'lardan **önce** çalışıyor.

4. **Sözdizimi hatası yok.** Dört dosya satır satır tarandı; tek bir hata, yanlış
   argüman veya var olmayan nesne referansı bulunamadı.

5. **Sıralama bağımlılığı yok.** 12 migration'ın çapraz referansları tek tek doğrulandı;
   `supabase db reset` isim sırasıyla uyguluyor ve zaman damgaları sıralı.

6. **`notFound()` / `redirect()` `app/error.tsx`'yi tetiklemiyor.** İkisi de kendi
   sınırlayıcılarıyla yakalanır. (Gerçek `error.tsx` ilişkili sorun B-4 değil, akış
   sırasıydı — o da aşağıdaki notta düşürüldü.)

7. **`drafts/page.tsx`'in `requireIdentity` çağırmaması bir açık değil.** Backend
   sahipliği RLS ile zorunlu kılıyor: `read_one` (`repository.py:21-35`) çıplak bir
   `select *` atıyor ama `own_submission` politikası `user_id = current_setting('cce.actor_id')`
   ile filtreliyor ve bu GUC yalnız JWT doğrulamasından sonra ayarlanıyor. Başkasının
   taslağını isteyen katkıcı sıfır satır alıyor → 404 → `notFound()`.
   *(Not: bu sayfaya `requireIdentity()` yine de eklendi — 4 kardeş sayfa artık aynı
   desende, savunma derinliği için.)*

8. **`retry_moderation` yetki sızıntısı yok.** `actor_user_id` (Python) ile
   `current_setting('cce.actor_id')` (Postgres) aynı `Actor`'dan türediği için
   ayrışamaz. Ayrışsalardı RLS `with check` satırı reddeder ve transaction geri alınırdı —
   **fail-open değil, fail-closed.**

9. **`request_id` log enjeksiyonuna kapalı.** `telemetry.py:31-35`
   `str(UUID(raw.decode("ascii")))` uyguluyor ve `ValueError`/`UnicodeDecodeError`'da
   `uuid4()`'e düşüyor. `<script>` geçemiyor.

10. **`cce_migrator` üzerindeki iki yeni SELECT politikası sızıntı değil.** `cce_migrator`
    NOLOGIN ve yalnız `postgres`'a üye; `cce_api`'nin `SET ROLE` yetkisi yok ve bu
    `test_database_integration.py:30-31`'de `InsufficientPrivilege` beklenerek test ediliyor.
    Bu politikalar **zorunlu**: `require_review_audit` SECURITY DEFINER ve sahibi
    `cce_migrator`; FORCE RLS açık olduğu için sahip bile politikasız satır göremez.

11. **`guard_avatar_status` süperuser'ı da durduruyor — bu kasıtlı.**
    `test_avatar_integration.py:53-58` bunu açıkça doğruluyor.

12. **Avatar byte işleme atlatma yok.** `verify_image` (`images.py:20-46`) format
    allowlist'i kullanıyor, `Image.open`'a `formats=[formats[content_type]]` geçiriyor
    (sahte Content-Type + JPEG baytları 422 verir), yeniden PNG'ye kodluyor, boyutu
    yeniden kontrol ediyor. `object_name` `.png` zorlayan GENERATED kolon
    (`20260924161331:9`), bucket `allowed_mime_types` yalnız `image/png` (`:70`).
    İstemci tipi bir güvenlik sınırı değil, bir allowlist'e giriş girdisi.

---

## 🛠️ Düzeltilmiş iki şey (bu inceleme sırasında)

### `loading.tsx` dosyaları kaldırıldı

İnceleme, bu oturumda eklenen iki `loading.tsx` dosyasının `notFound()` yolunu
bozabileceğini bildirdi: Suspense sınırı oluşturduğu için, `await` sonrasında atılan
`notFound()` `not-found.tsx` yerine `error.tsx`'e düşebilir ve 404 bir "servis
kullanılamıyor" mesajına dönüşebilir.

**Bu iddia çalıştırılarak doğrulanmadı** — makinede Docker olmadığı için bu rotalar
koşturulamıyor. Dosyalar untracked'dı, silmek bedava, ve kaybedilen şey yalnızca
kozmetik bir yükleme durumuydu; risk ise yarım saat önce birlikte düzelttiğimiz 404 /
anti-enumeration yoluydu. **İkisi de kaldırıldı** (`next build` ile doğrulandı).

Dosyalar `apps/web/src/app/admin/reviews/[id]/loading.tsx` ve
`apps/web/src/app/contributor/drafts/[id]/loading.tsx` idi; yeniden eklenmek istenirse
5 satır.

### Eklenen web test kapsamı

`server-only` alias'ı (`vitest.config.ts` + `test/server-only-stub.ts`) — Next bu
paketi kendi bundler koşuluyla çözüyor, vitest çözmüyordu; `media.ts` bu yüzden hiç
test edilemiyordu.

- `src/lib/media.test.ts` — 5 yetkisiz şeklin **hepsi** `null` dönüyor ve **sıfır API
  çağrısı** yapılıyor; çağıranın verdiği `Authorization` her zaman sunucu token'ıyla
  eziliyor
- `src/lib/contributions.test.ts` — genişletildi: 500 gövdesi sızdırılmıyor, okunamayan
  gövde status'u koruyor, ağ hatası status'suz, 401 ve eksik oturum redirect
- `src/app/contributor/drafts/actions.test.ts` — 7 bozuk girdi şekli istek atmadan
  reddediliyor, revalidate yalnız teyitli yüklemede

Web testleri 14 → 28 (`tsc` 0, `eslint` 0, `next build` başarılı).

---

## ⚠️ Doğrulanamayan tek teknik kalem

**PostgreSQL referans bütünlüğü kontrollerinin FORCE RLS altında hangi bağlamda
çalıştığı.**

Gözlem: `avatar_assets` (`20260924161331:4`, `cce_migrator`'a ait, `:21` FORCE RLS)
`character_submissions(id, user_id)`'ye FK veriyor (`:17`); `character_submissions`
üzerinde **hiçbir `cce_migrator` politikası yok**
(`20260923130347:58-62`, `20260924053912:59-63` — yalnız `cce_api`/`cce_engine`).
Aynı desen `moderation_retry_events` → `moderation_jobs` için de geçerli
(`20260930111403:33,35`).

**Empirik kanıt lehine:** bu desen bugün CI'da çalışıyor. `moderation_jobs`
üzerindeki üç `SECURITY DEFINER` fonksiyon `20260926095425:57`'de `reset role`
**sonrasında** oluşturuluyor, yani sahipleri `postgres`. Mevcut FK'ların hepsi bu
yüzden sorunsuz olabilir; RI kontrollerinin sahipten bağımsız çalıştığı (ve dolayısıyla
FORCE RLS'u atladığı) bu sonuçtan çıkarılabilir.

Bu, `supabase db reset` sonrası **ilk çalıştırmada** izlenmesi gereken tek şey. Dört yeni
migration ilk kez orada koşacak.

---

## Önerilen sıra

**Doğrulanmamış güvenlik sınırı:**
1. **B-1** — avatar `READY` INSERT koruması (tek satır)

**Yanlışlık halinde üretimi düşürebilir:**
2. **B-3** — `database_ready` için gerçek-DB integration testi (CI'da koşmalı)
3. **B-7** — `claim_moderation` dayanıklılığı

**Güvenlik yolu okunabilirliği:**
4. **B-4** — `avatar_router.py` ölü kod
5. **B-5** — decode sırası

**Sözleşme sertleştirme:**
6. **B-2** — `contribution_events` aksiyon kısıtı (tek satır)
7. **B-6** — `check_proposal_contract.py` kapsamı
8. **B-8** — fixture bayrağı kilidi
9. **B-9** — retry kaydını `enqueue_moderation`'a taşı

**Bilinçli olarak açık bırakıldı (ürün kararı):**
Onay checkbox'ları (`adult_appearance_confirmed`, `original_character_confirmed`) üç
katmanda da toplanıyor, render ediliyor ve sözleşmeyle izleniyor — ama **hiçbir katman
zorlamıyor**. `proposal-form.tsx:29` yalnız `z.boolean()`, `schemas.py:44-45` yalnız
`bool = False`, veritabanı yalnız `jsonb_typeof` kontrol ediyor. Katkıcı her ikisini de
`false` bırakarak gönderebilir. Bu değişiklik alanları daha görünür kıldı, ancak
danışmanlık hâlâ bağlayıcı değil. Kapatılması bir ürün kararıdır; kapatılırsa üç
katmana birden eklenmelidir.

---

## Yeniden inceleme notu

Bu kayıt `8fed08f` commit'i üzerinde alınmıştır. B-1, B-2 ve B-3 düzeltildikçe bu
dosyadaki durum güncellenmelidir. Yeni migration veya endpoint eklendiğinde **B-1**
(avatar `READY` yazma yolu) yeniden doğrulanmalıdır — çünkü `cce_api`'nin INSERT
yapabildiği herhangi bir tablo aynı sınıfı taşır.
