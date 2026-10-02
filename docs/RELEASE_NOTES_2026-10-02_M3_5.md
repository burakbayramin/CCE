# Sürüm Notu — M3.5 ve M3.6

**Tarih:** 2026-10-02
**Kapsam:** Onaylı definition revizyonu ile gerçek veri düzeltmesinin ayrılması; Owner'ın kendi karakterini oluşturma ve denetim görünümü.

---

## M3.5 — Definition değişikliği

Daha önce onaylı bir definition tek kaynak olduğu için "yeni tanımı etkinleştirmek"
diye bir işlem yoktu. M3.5 bunu iki ayrı işleme ayırıyor.

### Normal revizyon

Katılıcı, onaylanmış bir başvuru üzerinde yeni revizyon açabilir — ama çekirdek
kilitlidir. `guard_submission_transition` önerilen tanımı aktif artifact ile
karşılaştırır ve `introduction`, `speech_style`, `humor` dışındaki alanlarda
kişilik, hedef, geçmiş veya baseline değişikliğini `23514` ile reddeder.

Önemli nokta: aday revizyon henüz onaylanmadığı için **aktif karakteri geçersiz
kılmaz**. Bekleyen tanım ile canlı aktivasyon bilinçli olarak ayrışır ve başlangıç
snapshot'ı değiştirilmez. Doğrulama `test_definition_changes_integration.py`
tarafından karşılaştırılır.

### Denetimli benimseme

Onaylı yeni tanımı etkinleştirmek ayrı bir Owner komutudur:

- Aktif işaretçi taşınır, `lifecycle_version` artar
- `character_definition_events` satırı gerçek aktör, önceki ve yeni definition
  kimliği, sürümler ve 10–1000 karakter gerekçeyle append-only yazılır
- Önceki artifact, onay ve moderasyon kaydı **değişmez**; bağımsız doğrulanabilir kalır
- Aynı `request_id` tekrarı ikinci satır üretmez, ilk kaydı döndürür
- Güncel onay, fixture moderasyonu veya kaynak zinciri tutmuyorsa komut reddeder

Gerçek içerik benislemesi `test_mode` dışında `409` ile kapalıdır; production içeriği
için henüz komut yolu yoktur.

### Uzlaştırma kararı

Onaylı ama benimsenmemiş aday definition, aktivasyonu bozmaz. Başlangıç snapshot'ı
bilinçli olarak korunur ve ilk aktivasyon kaydı değiştirilmez. M4/M6 runtime state
motorları türetilmiş kayıtları sahip oldukları definition sürümüyle ilişkilendirip
yeniden uzlaştıracaktır; **bu aşamada otomatik yeniden hesaplama tanımlı değildir.**

### Yanlışlık düzeltmesi

`prepare_definition`, az önce yazdığı satırı okuyamadığında `assert` ile
beklenmedik bir yere düşüyordu. `python -O` altında bu kontrol tamamen kayboluyor ve
çağıran `None` alıyordu. Aktivasyon yolundaki mevcut davranışla aynı olacak şekilde
açık bir `503`'e çevrildi.

---

## M3.6 — Admin oluşturma ve görünüm

### Owner kendi karakterini oluşturuyor

Owner portalı katkıcı taslak formuna açık bir giriş sunuyor. Garanti edilen üç şey
arayüzde de yazılı:

1. Katılımcıyla **aynı yapılandırılmış form** ve aynı doğrulama hattı kullanılır
2. Kendi onayında moderasyon **yeniden değerlendirilir**, doğrulama atlanmaz
3. `BLOCK` sonucu Owner'ın kendi karakterinde de geçerlidir

Audit satırı gerçek Owner aktörünü yazar. `test_owner_character_integration.py`
bunu ayrı bir test olarak doğruluyor: başvurunun tamamındaki `contribution_events`
satırlarının tek aktörü Owner'dır.

### Görünüm

İnceleme ekranı artık şunları birlikte gösteriyor:

- Definition sürümü ve **aktif tanım işaretçisi** (ayrı ayrı, farklıysa uyarı)
- Bekleyen benisleme varsa uyarı ve komut; izole test politikası dışında komut
  görünmez ama **durum ve geçmiş yine görünür**
- Lifecycle geçmişi ve definition benimseme geçmişi
- Her iki geçmişte de **gerçek aktör kimliği**

Denetim izi yüklenemezse boş bir liste yerine hata gösterilir; "hiç kayıt yok"
ile "okunamadı" birbirine karışmaz.

### Restore negatif gereksinimi

Restore ve reactivate saf durum geçişidir. Test, aktivasyon sonrası sabitlenen
moderasyon iş sayısını her geçişten sonra yeniden ölçer ve revizyonun verdict
sayısının hâlâ 1 olduğunu doğrular. Sessizce yeniden kuyruğa alınan bir tarama
ek iş ya da ikinci verdict olarak görünür.

---

## Doğrulama

| Kontrol | Sonuç |
| --- | --- |
| ruff / ruff format | ✅ |
| mypy (CI yapılandırmasıyla, strict) | ✅ 35 dosya |
| Backend birim testleri | ✅ 140 |
| Web testleri | ✅ 42 |
| tsc / eslint | ✅ 0 hata |
| Production build | ✅ |

**Çalıştırılmadı:** `test_owner_character_integration.py` ve
`test_definition_changes_integration.py` entegrasyon testleridir; izole Supabase
yığını gerektirir ve bu makinede Docker bulunmadığından yalnız CI'da koşacaklar.
Yeni migration uygulanmadı — şema `version = 8` olarak değişmedi.

## Commit'ler

| Commit | Kapsam |
| --- | --- |
| `9ed6104` | M3.5 Python, assert düzeltmesi, yenilenmiş OpenAPI istemcisi |
| `c9de0cb` | M3.6 web: benimseme paneli, gerçek aktör, Owner form girişi, contract testleri |
| `103c3b0` | M3.6 entegrasyon testleri: self-approval audit'i ve restore negatif gereksinimi |

## Kalan açık kapılar

M3'ün tek açık maddesi M3.2'nin **gerçek tarayıcı ve model kabulü** kalıyor. Kesin
metin/görsel modeli, quantization, runtime ve lisans seçimi son entegrasyon kapısında
kullanıcının kararına bağlıdır. Bu kapanmadan gerçek içerik aktivasyonu ve katkıcıların
public açılışı kapalı kalır.