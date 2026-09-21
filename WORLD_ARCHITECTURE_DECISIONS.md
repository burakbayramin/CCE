# Cognitive Character Engine — Ortak Dünya Mimari Kararları

Bu belge, en fazla 50 kalıcı AI karakterin yaşadığı ortak dünya için ürün ve mimari kararlarını tek tek değerlendirmek amacıyla tutulur.

## Ürün Tanımı

Cognitive Character Engine, proje yöneticisinin AI karakterlerle konuşabildiği ve karakterlerin birbirleriyle özerk etkileşimler ve ilişkiler geliştirdiği kalıcı bir yapay dünya motorudur. Destekçiler ve katkıcılar UI üzerinden yeni karakter tasarlayabilir; ancak karakterlerle konuşamaz ve canlı dünya state'ini doğrudan değiştiremez.

## Aktörler

### World Owner / Admin

- Karakter oluşturabilir.
- Aktif karakterlerle konuşabilir.
- Katkıcı başvurularını ve değişiklik önerilerini inceleyebilir.
- Karakteri dünyaya kabul edebilir, askıya alabilir veya arşivleyebilir.
- Dünya olaylarını ve engine ayarlarını yönetebilir.
- Yetkili brain/debug ekranlarına erişebilir.

### Contributor

- Hesap oluşturabilir.
- UI üzerinden karakter taslağı hazırlayabilir.
- Taslağı incelemeye gönderebilir.
- Kendi başvurusunun durumunu ve geri bildirimleri görebilir.
- Canlı karakterlerle konuşamaz.
- Canlı karakter state'ini, memory'lerini veya ilişkilerini doğrudan değiştiremez.

### AI Character

- Onaylandıktan sonra ortak dünyada aktif bir varlık olur.
- Diğer aktif AI karakterlerle etkileşebilir.
- Yönlü ilişkiler, memory, mood, goals ve deneyimler geliştirebilir.
- World Owner ile konuşabilir.
- Katkıcı tarafından doğrudan kontrol edilmez.

## Karar Durumları

- `BEKLİYOR`: Henüz tartışılmadı.
- `TARTIŞILIYOR`: Seçenekler değerlendiriliyor.
- `KABUL`: Karar kesinleştirildi.
- `DEĞİŞTİRİLDİ`: İlk önerinin farklı bir biçimi kabul edildi.
- `RED`: Uygulanmayacak.
- `ERTELENDİ`: Sonraki faza bırakıldı.

## Karar Özeti

| No | Konu | Durum | Nihai karar |
| --- | --- | --- | --- |
| WADR-001 | Karakter katkısı, onay ve değişiklik yetkisi | KABUL | Katkıcı önerir; World Owner onaylar ve yayınlar |
| WADR-002 | Dünyanın kimler tarafından görülebileceği | KABUL | Küratörlü public World Viewer ve katmanlı görünürlük |
| WADR-003 | Karakter tanımı ve katkı formunun sınırları | KABUL | Yapılandırılmış form + kontrollü yaratıcı alanlar + World Owner onayı |
| WADR-004 | Ortak dünya, zaman ve mekân modeli | KABUL | Merkezî world clock + ayrık konumlar + scene tabanlı event-driven simülasyon |
| WADR-005 | Karakterler arası etkileşim seçimi ve bütçesi | KABUL | Kurallı adaylar + puanlama + sınırlı director + katmanlı bütçeler |
| WADR-006 | Karakterler arası konuşma ve event modeli | KABUL | Karaktere özel context kullanan sınırlı turn-based scene engine |
| WADR-007 | Social graph ve yönlü ilişkiler | KABUL | Objektif bağlar + yönlü çok boyutlu state + append-only event geçmişi |
| WADR-008 | Memory görünürlüğü ve karakterler arası bilgi aktarımı | KABUL | Kapsamlı, provenance taşıyan epistemik memory |
| WADR-009 | Autonomy, goals ve reflection sistemi | KABUL | Sınırlandırılmış agency + hiyerarşik goals + event-driven reflection |
| WADR-010 | Moderasyon ve güvenlik modeli | KABUL | Katmanlı moderasyon; yetişkin karakterler ve explicit olmayan olgun anlatım |
| WADR-011 | Güncellenmiş teknoloji yığını | KABUL | Cloud control plane + yerel AI plane; model/provider seçimleri benchmark'a ertelendi |
| WADR-012 | Veritabanı ve event şeması | KABUL | İlişkisel çekirdek, üç erişim şeması, domain event standartları ve ölçümlü optimizasyon |
| WADR-013 | Backend, worker ve frontend mimarisi | KABUL | Yapılandırılmış monorepo + modüler monolith + üretilmiş API sözleşmeleri |
| WADR-014 | MVP kapsamı ve fazlama | KABUL | 3–5 karakterle başlayan uçtan uca dikey MVP |

---

## WADR-001 — Karakter Katkısı, Onay ve Değişiklik Yetkisi

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

### Karar

Katkıcı, karakter tasarımcısı ve öneri sahibi olarak hareket eder; canlı karakterin sahibi veya operatörü olmaz. World Owner nihai onay ve yayın yetkisini korur.

### İlk başvuru akışı

```text
DRAFT
  ↓
SUBMITTED
  ↓
UNDER_REVIEW
  ├── CHANGES_REQUESTED ──► DRAFT
  ├── REJECTED
  └── APPROVED
          ↓
        ACTIVE
          ↓
        SUSPENDED / ARCHIVED
```

- Katkıcı yalnızca kendi taslaklarını oluşturabilir ve başvuru öncesinde düzenleyebilir.
- Gönderilmiş başvuru inceleme süresince değiştirilemez; gerekirse yeni revizyon açılır.
- World Owner başvuruyu kabul edebilir, reddedebilir veya değişiklik isteyebilir.
- Yalnızca onaylanan karakter canlı dünya state'i, memory, mood ve ilişki kayıtları kazanır.

### Onay sonrası değişiklik

- Katkıcı aktif karakteri doğrudan düzenleyemez.
- Katkıcı yeni bir değişiklik önerisi/revizyonu gönderir.
- Değişiklik mevcut sürüm ile önerilen sürüm arasındaki fark olarak incelenir.
- World Owner onay verirse yeni karakter tanımı sürümlenerek yayınlanır.
- Engine tarafından oluşmuş memory, relationship, mood, goal ve event state'i katkıcı değişikliğinden ayrıdır.
- Kim tarafından ne önerildiği ve kim tarafından ne zaman onaylandığı audit kaydına alınır.

### Güvenlik sonucu

- Contributor rolü canlı engine tablolarına yazamaz.
- Rol yetkilendirmesi kullanıcı tarafından değiştirilebilir metadata'ya dayandırılmaz.
- Onay ve yayın işlemleri yalnızca güvenilir backend komutları üzerinden yürütülür.
- Katkı metinleri canlı prompt'a girmeden önce şema, içerik ve güvenlik doğrulamasından geçer.

---

## WADR-002 — Dünyanın Kimler Tarafından Görülebileceği

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Katkıcıların ve ziyaretçilerin aktif karakterleri, ilişkileri, dünya zaman çizelgesini ve karakterler arası etkileşimleri hangi ayrıntı düzeyinde görebileceği belirlenecektir.

### Karar

Küratörlü public World Viewer ve katmanlı görünürlük modeli kabul edilmiştir.

#### Public erişim

Giriş yapmamış ziyaretçiler aşağıdaki yayınlanabilir projection'ları görebilir:

- Aktif karakterlerin public profilleri
- Public ilişki haritası
- Seçilmiş veya özetlenmiş dünya olayları
- Yayınlanmış karakterler arası etkileşimler
- Public timeline ve temel dünya istatistikleri

#### Contributor erişimi

Katkıcı, public World Viewer'a ek olarak yalnızca kendi karakter taslaklarını, başvurularını, revizyonlarını, inceleme geri bildirimlerini ve başvuru durumlarını görebilir. Aktif karakterlerle konuşamaz ve internal state'e erişemez.

#### World Owner erişimi

World Owner; karakterlerle chat, moderasyon, internal world state, memory/mood/relationship ayrıntıları, LLM ve job gözlemlenebilirliği ile brain/debug araçlarına erişebilir.

#### Yayınlanmayacak içerik

- Ham veya yayınlanmamış konuşma kayıtları
- Internal reasoning ve private/internal memory
- Prompt, model ve güvenlik ayarları
- Ayrıntılı mood/relationship state'i
- Moderasyon notları ve katkıcı kişisel bilgileri
- Debug, LLM ve job kayıtları
- World Owner ile karakter arasındaki özel konuşmalar

#### İçerik görünürlüğü

Karakter etkileşimleri ve world event projection'ları en az aşağıdaki görünürlüklerden birini taşır:

- `internal`: insan erişimi yalnız World Owner'a açıktır; engine erişimi görev yetkisiyle, AI karakter erişimi ise ayrıca bilgi kapsamıyla sınırlandırılır
- `public_summary`: güvenli ve özetlenmiş public anlatım
- `featured`: World Owner tarafından özellikle yayınlanmış içerik

Public sayfalar internal tablolara doğrudan erişmez; yalnızca yayınlanmak üzere hazırlanmış ve RLS/izin politikalarıyla korunan projection'ları okur.

İnsanlara yayın görünürlüğü, karakterlerin ne bildiğinden ayrı bir eksendir. Bir sahnenin `internal` olması katılımcıların gözlemlediklerini öğrenmesini engellemez; bir içeriğin World Viewer'da yayınlanması da bütün karakterlere otomatik bilgi kazandırmaz.

---

## WADR-003 — Karakter Tanımı ve Katkı Formunun Sınırları

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Katkıcının hangi karakter özelliklerini belirleyebileceği, hangi alanların engine veya World Owner tarafından yönetileceği ve serbest metin alanlarının nasıl doğrulanacağı belirlenecektir.

### Karar

Yapılandırılmış form, kontrollü yaratıcı alanlar ve World Owner onayı birlikte kullanılacaktır.

#### Katkıcının belirleyebileceği alanlar

- İsim, zamirler, açıkça yetişkin görünen yaş ve kısa tanıtım
- Görsel/avatar önerisi, kültürel arka plan, meslek veya dünyadaki rol
- Sınırlandırılmış personality eksenleri
- Güçlü yönler, kusurlar, değerler, korkular ve motivasyonlar
- Mizah ve konuşma tarzı, sevilen/sevilmeyen şeyler
- Kontrollü serbest metinle backstory, önemli geçmiş olayları ve başlangıç hedefi önerileri
- Başlangıçta bilinen kişi/kurum ve sır önerileri

#### Katkıcının belirleyemeyeceği alanlar

- Ham system prompt, model/temperature ve güvenlik talimatları
- Tool yetkileri veya erişim politikaları
- Canlı mood, relationship, memory ve runtime goal state'i
- Memory importance/decay algoritmaları
- Başka karakterlere onaysız ilişki veya geçmiş dayatmaları

Başka bir karakteri etkileyen bağlantılar yalnızca öneri olarak sunulur ve World Owner onayı gerektirir.

#### Derleme ve yayınlama

1. Serbest metin alanları içerik ve güvenlik doğrulamasından geçer.
2. Veriler sürümlenmiş, yapılandırılmış karakter tanımına dönüştürülür.
3. Engine; temperament baseline, başlangıç affect değerleri, stil parametreleri, core memory ve goal adaylarını türetir.
4. Katkıcı ön izlemeyi görebilir ancak runtime değerlerini doğrudan değiştiremez.
5. World Owner inceleyip onayladıktan sonra sürümlenmiş prompt şablonu derlenir ve karakter aktive edilir.

#### İçerik sınırları

- Aktif karakterler açıkça yetişkin olacaktır.
- Gerçek kişilerin izinsiz kopyaları ve telifli karakterlerin birebir kopyaları kabul edilmez.
- Prompt/system talimatı enjekte etmeye çalışan veya başka kişilerin özel verilerini içeren katkılar reddedilir.
- Ham katkı metni hiçbir zaman doğrudan system prompt olarak kullanılmaz.

---

## WADR-004 — Ortak Dünya, Zaman ve Mekân Modeli

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Dünyanın gerçek zamanla ilişkisi, karakterlerin konumları, karşılaşma koşulları ve world state'in ayrıntı düzeyi belirlenecektir.

### Karar

Merkezî dünya saati, ayrık/anlamlı konumlar ve scene tabanlı event-driven simülasyon kabul edilmiştir.

#### Dünya saati

- MVP'de dünya zamanı gerçek zamanla 1:1 ilerler ve başlangıç saat dilimi `Europe/Istanbul` olur.
- Domain kodu sistem saatini doğrudan okumaz; merkezî bir `world_clock` arayüzünü kullanır.
- Duraklatma, hızlandırma, ileri sarma ve testlerde sahte zaman desteği mimari olarak mümkün bırakılır; yönetim arayüzü sonraki faza bırakılabilir.
- Worker çevrimdışıyken dünya saati gerçek zamanla 1:1 ilerlemeye devam eder; AI etkileşimleri bekler. Geri dönüşte güncel zamana uyarlanır, gerçekleşmemiş konuşmalar geçmişte yaşanmış gibi üretilmez (`AK-002`: KABUL).
- Queue lease, bağlantı timeout'u ve worker heartbeat gibi operasyonel süreler dünya saatinden bağımsız gerçek zamanla ölçülür. Dünya zamanını duraklatmak operasyonel timeout'ları durdurmaz.

#### Çevrimdışı dönem ve geri dönüş — AK-002: KABUL

- Worker çevrimdışıyken yeni autonomous sahne üretimi durur; eksik diyalog, karşılaşma veya ilişki deneyimi sonradan uydurulmaz. Public/control plane çalışabilir; UI AI worker'ın çevrimdışı ve işlerin bekliyor olduğunu gösterir.
- Geri dönüşte önce kalıcı sonuçlar ve yarım işler uzlaştırılır. Commit edilmiş turn'ler korunur; yalnız gerçekten gerçekleşmiş etkileşimin etkileri idempotent processing ile tamamlanır. Artık zaman/konum koşulları geçerli olmayan yarım sahne eski zamandan konuşma üretmeye devam etmez; geçerli prefix'i üzerinden kesintili olarak sonuçlandırılır.
- Ardından presence, konum ve rutinler mevcut dünya saati ve geçerli dünya kurallarına göre deterministik olarak güncellenir. Kaçırılan her zaman bloğunu tek tek oynatmak yerine güncel duruma uyarlama kaydı tutulur; bu kayıt yaşanmış sosyal deneyim veya episodic memory sayılmaz.
- Henüz başlamamış eski sahne adayları güncel konum, müsaitlik, tetikleyici, cooldown ve bütçeyle yeniden değerlendirilir. Geçersiz aday gerekçesiyle kapatılır; hâlâ anlamlı olan etkileşim güncel zaman için planlanabilir. Geçmiş günlerin kullanılmamış sahne kotası birikmez.
- Birikmiş rutin/zaman bloğu bakım işleri gerekli güncel hesaplamaya birleştirilir. Süresi geçmiş goal tetikleyicileri güncel goal koşullarıyla değerlendirilir; geçen süre, eylemin yapılmış veya hedefin başarılmış olduğu anlamına gelmez.
- Kalıcı chat mesajları ve sonuç uygulama işleri sırf eski oldukları için kaybedilmez. Bekleyen cevap üretimi iptal/lifecycle/context kontrollerinden sonra güncel zamanda yürütülür; gecikme görünürdür, cevap geçmişe tarihlenmez.
- Son geçerlilik, iş türü ve tetikleyicinin geçerli olduğu zaman aralığına bağlanır; bütün job'lara aynı TTL uygulanmaz. Kesin süreler iş sözleşmesinde yapılandırılır. Çevrimdışı geçen dünya zamanı mood'un baseline'a yaklaşma ve gündelik memory'nin hatırlanma önceliği hesaplarına dahildir. Bunlar ayrı hesaplamalardır; önemli deneyimler korunur, güven otomatik düzelmez ve zaman geçmesi memory'nin fiziksel silinmesini gerektirmez.

#### Konum ve presence

- Sürekli koordinatlar yerine hiyerarşik ve anlamlı konum düğümleri kullanılır.
- Konumlar parent, açıklama, kapasite, gizlilik seviyesi, etiketler ve açılış saatleri gibi özellikler taşıyabilir.
- Karakterin konumu, etkinliği, etkileşime uygunluğu ve beklenen kalış süresi `character_presence` benzeri güncel state ile tutulur.

#### Scene

- Önemli karakter etkileşimleri bir scene içinde gerçekleşir.
- Scene; konum/kanal, katılımcılar, zaman, tetikleyici, görünürlük ve durum bilgisi taşır.
- Scene sonunda katılımcılara özgü memory, yönlü relationship event'leri, mood etkileri ve uygun olduğunda public timeline özeti üretilebilir.

#### Program ve etkileşim koşulları

- Dakika dakika simülasyon yerine morning/afternoon/evening/night gibi zaman blokları ve esnek rutinler kullanılır.
- Fiziksel karşılaşma; konum, müsaitlik, bütçe ve anlamlı bir tetikleyici gerektirir.
- Uzaktan iletişim aynı konumu gerektirmez ancak tanışıklık veya geçerli iletişim nedeni ister.

#### Event-driven çalışma

State; zaman bloğu değişimi, planlanmış scene, world event, World Owner konuşması, goal zamanı veya presence değişimi gibi olaylarda ilerletilir. Karakterler sürekli LLM çağrılarıyla simüle edilmez.

---

## WADR-005 — Karakterler Arası Etkileşim Seçimi ve Bütçesi

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

En fazla 50 karakter arasından hangi etkileşimlerin üretileceği, önceliklendirileceği ve LLM/worker bütçesiyle nasıl sınırlandırılacağı belirlenecektir.

### Karar

Deterministik aday üretimi, açıklanabilir puanlama, yalnızca daraltılmış adaylar üzerinde çalışan sınırlı LLM director ve katmanlı bütçeler kabul edilmiştir.

#### Aday üretimi ve puanlama

- Konum/kanal, aktiflik, müsaitlik, cooldown, devam eden scene, tanışıklık ve bütçe kuralları mümkün olmayan eşleşmeleri LLM çağrısından önce eler.
- Kalan adaylar location relevance, relationship tension, shared goal, world event, unfinished business, narrative novelty ve fairness sinyalleriyle puanlanır.
- Yakın zamanda tekrarlanan etkileşimler, aynı çiftin aşırı kullanımı ve tahmini maliyet negatif puan üretir.

#### Sınırlı director

- Director bütün dünya context'ini almaz; yalnızca en yüksek puanlı ve backend tarafından geçerli bulunan az sayıda adayı değerlendirir.
- Director scene katılımcısı, tetikleyicisi, amacı ve kısa dramatic question önerebilir.
- Backend öneriyi yeniden doğrular ve nihai başlatma yetkisini korur.

#### Katmanlı bütçeler

- Dünya seviyesinde günlük autonomous scene, token ve concurrency sınırları
- Karakter seviyesinde günlük scene/turn sınırı ve cooldown
- Scene seviyesinde turn, süre, token ve idle timeout sınırı
- Worker seviyesinde eşzamanlı LLM işi, rate limit, timeout ve retry sınırı

MVP başlangıç hedefi donanım testleriyle kesinleştirilmek üzere 3–5 aktif karakter için günde yaklaşık 2–4 autonomous scene, karakter başına en fazla 2 scene, aynı çift için 12–24 saat cooldown, scene başına 6–10 turn ve aynı anda 1 autonomous scene'dir. Aktif karakter sayısı büyüdüğünde dünya bütçesi önce 10–15 scene/gün aralığına kontrollü biçimde yükseltilebilir.

#### Fairness ve uyarlama

- Uzun süredir scene almayan uygun karakterler fairness bonusu kazanır.
- Kota doldurmak amacıyla anlamsız sahne üretilmez.
- World Owner belirli karakter veya ilişkilere geçici öncelik verebilir.
- Queue/model yükü arttığında yeni scene üretimi otomatik olarak yavaşlatılabilir.
- World Owner konuşmaları autonomous scene kotasından sayılmaz; fakat karakter state'ini ve müsaitliğini etkileyebilir.

#### Toplam AI yükü ve öncelik

- Chat, scene turn'leri, director, memory extraction, reflection, consolidation, summary, model tabanlı moderasyon ve çıktı düzeltme denemeleri ortak kaynak muhasebesine dahildir. Scene sayısı toplam model maliyetinin yerine geçmez.
- İş türü bazında token, süre ve deneme sınırları bulunur; başarısız denemeler de tüketimden sayılır. Yeni iş kabulünde bütçe ayrılır, bitişte gerçek tüketimle uzlaştırılır.
- Kaynak ve karakter uygunluğu sağlanan admin chat işleri, henüz başlamamış autonomous/background GPU işlerinden önce seçilir. Hedef karakter devam eden sahnedeyse AK-003 uyarınca mevcut turn tamamlanır, sahne güvenli biçimde sonlandırılıp etkileri kaydedilir ve ardından chat başlar. GPU önceliği bu state tutarlılığı sınırını atlayamaz.
- Uzun arka plan akışları kısa, yeniden başlanabilir model görevlerine bölünür. Önceliklendirme GPU çağrıları arasındaki güvenli noktalarda uygulanır; sonsuz bekleyen arka plan işleri ve en yaşlı iş süresi izlenir.

---

## WADR-006 — Karakterler Arası Konuşma ve Event Modeli

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Seçilen karakterlerin scene'i nasıl yürüteceği, konuşma sırasının nasıl belirleneceği ve sonuçların kalıcı state'e nasıl uygulanacağı belirlenecektir.

### Karar

Karaktere özel context kullanan, sınırlandırılmış turn-based scene engine ve düşük önemdeki karşılaşmalar için özet event yolu kabul edilmiştir.

#### Scene yaşam döngüsü

```text
SCHEDULED → PLANNING → RUNNING → PROCESSING → COMPLETED
                         └──────► INTERRUPTED / FAILED / CANCELLED
```

- Planning aşaması katılımcıları, konumu, tetikleyiciyi, amacı, görünürlüğü ve bütçeyi kesinleştirir.
- Her karakter yalnız kendi personality/goals/memory state'ini, karşı taraf hakkında bildiklerini, kendi yönlü relationship state'ini ve ortak transcript'i görür.
- Ortak transcript yalnız commit edilmiş konuşmaları ve diğer katılımcıların gözlemleyebildiği, backend tarafından kabul edilmiş eylemleri içerir. Private intent, içsel affect sinyali, reflection ve engine/debug alanları ortak transcript'e eklenmez.
- Karakter başka bir karakterin private memory veya internal state'ini göremez.
- Her LLM çağrısı yalnızca ilgili karakterin tek turn'ünü üretir; başka karakter adına konuşamaz.
- Çıktı utterance, action, intent, affect sinyali ve scene bitirme sinyali gibi yapılandırılmış alanlarla doğrulanır.

#### Kontrol ve bitirme

- Scene Controller konuşma sırasını, turn/token bütçesini, timeout'u ve bitirme koşullarını yönetir.
- Scene doğal sonuç, amaç tamamlanması, karşılıklı bitirme, bütçe, timeout, güvenlik hatası veya World Owner müdahalesiyle sona erebilir.
- LLM sınırsız turn veya scene başlatma yetkisine sahip değildir.

#### Scene sonrası işleme

- Her katılımcı için ayrı memory candidate'ları üretilir.
- Yönlü relationship, emotion/mood ve goal değişimleri ayrı ayrı değerlendirilir.
- Shared experience, internal summary ve uygunsa güvenli public summary oluşturulur.
- Aynı scene farklı karakterlerde farklı yorum ve memory oluşturabilir.

#### Dayanıklılık ve maliyet

- Tamamlanan turn'ler kalıcılaştırılır; scene yarıda kesilirse transcript kaybolmaz.
- Processing işleri idempotent olur; yarım scene etkilerinin nasıl uygulanacağı açık durum kurallarına bağlanır.
- Varsayılan scene bütçesi yaklaşık 6–10 turn ile sınırlıdır.
- Düşük önemdeki arka plan karşılaşmaları tam turn-by-turn diyalog yerine tek çağrılı özet event olarak üretilebilir.

#### Eşzamanlılık ve sonuç uygulama sınırı

- GPU concurrency 1, karakter state'inin tek akış tarafından kullanıldığını garanti etmez. Scene/chat için karakter bazlı etkin etkileşim rezervasyonu ayrıca tutulur; çok katılımcılı rezervasyon tek kısa transaction'da alınır.
- Rezervasyonun aktif sahibini ve süresini doğrulayan deneme kimliği kullanılır. LLM çalışırken veritabanı transaction'ı veya uzun süreli satır kilidi açık tutulmaz.
- Context, kullanılan state sürümleriyle ilişkilendirilir. Sonuç kabulünde ilgili state sürümleri, lifecycle, rezervasyon ve iptal durumu doğrulanır; eski context ile üretilmiş sonuç sessizce yeni state'e uygulanmaz. Yeniden üretim bounded retry kurallarına tabidir.
- Sahne sonrası memory, relationship, affect ve goal adayları önce hazırlanır/doğrulanır. Birlikte görünmesi gereken domain etkileri bütün katılımcılar için kısa, atomik bir sonuç uygulama transaction'ında kaydedilir; geçerli sıfır değişim de sonuçtur.
- Domain etkileri uygulanmadan sahne `COMPLETED` olmaz ve ilgili karakter yeni etkileşime hazır sayılmaz. Embedding, public summary ve bildirimler gibi türetilmiş işler outbox ile sonradan yürütülebilir; bunlar canonical sonucun commit edilmesini engellemez.
- Henüz embedding'i üretilmemiş yeni canonical memory'ler context'ten kaybolmaz; yetkili son etkileşim kayıtları/recent memory yolu vector indeksinden bağımsız okunur.
- Yarım sahnede yalnız commit edilmiş, geçerli turn'ler yaşanmış etkileşim sayılır; üretilmemiş devamı varsayılmaz. Kesinti nedeni, son kabul edilen turn ve processing durumu ayrı kaydedilir. Bu prefix'in domain etkileri aynı sonuç protokolüyle en fazla bir kez uygulanır; doğrulanamayan çıktı quarantine'e alınır.
- `PLANNING` ve `PROCESSING` dahil her aşamanın hata/iptal/yeniden deneme geçişleri uygulama sözleşmesinde tanımlanır. Operasyonel hata, sahnenin kendiliğinden başarıyla tamamlandığı anlamına gelmez.
- Admin'in sahnedeki karaktere mesaj göndermesi hâlinde rezervasyon devri aşağıdaki AK-003 akışını uygular.

#### Admin sohbeti için güvenli sahne sonlandırma — AK-003: KABUL

- World Owner sahne katılımcısına mesaj gönderdiğinde mesaj kalıcılaştırılır ve sahneye idempotent bir durma isteği kaydedilir. UI “mevcut konuşmasını tamamlıyor” durumunu gösterir; mesaj kaybolmaz veya hemen yanıtlanmış sayılmaz.
- O anda üretilen turn, mevcut token/süre sınırları içinde tamamlanıp doğrulanır. Sonraki sahne turn'ü başlatılmaz. Aktif üretim yoksa son commit edilmiş turn güvenli sınırdır; durma isteği ve yeni turn başlatma kontrolü atomik olarak koordine edilir.
- Turn timeout veya validation hatasıyla biterse geçersiz/kısmi üretim yaşanmış konuşma sayılmaz; son geçerli transcript kullanılır. Sahneyi kapatmak için ek bir LLM kapanış diyaloğu zorunlu tutulmaz.
- Scene, admin sohbeti nedeniyle `INTERRUPTED` olarak kaydedilir; transcript ve iki katılımcının geçerli domain etkileri mevcut atomik/idempotent processing protokolüyle tamamlanır. Kesintili sahne tam hedefini başarmış gibi `COMPLETED` sayılmaz; processing'in tamamlanması ayrıca izlenir.
- Hedef karakterin rezervasyonu, gerekli memory/relationship/affect/goal etkileri commit edildikten sonra bekleyen admin chat'e devredilir; araya yeni autonomous etkileşim giremez. Sahne zaten `PROCESSING` aşamasındaysa mevcut processing'in tamamlanması beklenir, aynı etkiler yeniden uygulanmaz.
- Bu devri açmak için gerekli processing işleri ilgisiz arka plan işlerinden önce yürütülür. Processing başarısızsa UI hata/bekleme durumunu gösterir; tutarsız eski state ile sessizce chat başlatılmaz.
- Henüz turn başlamamış planning/scheduled sahne durdurulursa yaşanmamış deneyim veya sahne memory'si oluşturulmaz. Diğer katılımcının rezervasyonu güvenli sonlandırma sonrası serbest bırakılır.
- Chat context'i son sahnenin commit edilmiş etkilerini içerir; embedding tamamlanmamışsa recent-memory yolu kullanılır. Teknik durma nedeni diğer karaktere admin mesajının içeriğini veya özel bilgileri öğrenme hakkı vermez.
- Yarım kalan konu, ileride geçerli tetikleyici ve bütçe/cooldown kurallarıyla yeni bir sahnede ele alınabilir. Eski sahne dondurulduğu noktadan otomatik devam ettirilmez ve gelecekte tamamlanması garanti edilmez.

---

## WADR-007 — Social Graph ve Yönlü İlişkiler

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Karakterler arası objektif bağların, öznel algıların, çok boyutlu ilişki state'inin ve değişim geçmişinin nasıl temsil edileceği belirlenecektir.

### Karar

Objektif bağlantıları, karakterlerin öznel ve yönlü ilişki state'inden ayıran; çok boyutlu snapshot ve append-only event geçmişi kullanan social graph kabul edilmiştir.

#### Objektif bağlantılar

- Akrabalık, iş arkadaşlığı, komşuluk, aynı organizasyon ve birlikte yaşanmış doğrulanmış bağlantılar ortak dünya gerçeği olarak ayrı kaydedilir.
- Bağlantılar kaynak, geçerlilik başlangıcı/bitişi ve onay bilgisi taşır.

#### Yönlü öznel state

- Her `source_character → target_character` yönü ayrı state'tir.
- MVP boyutları familiarity, trust, affection, respect, tension, fear ve rivalry'dir.
- Karakter çiftleri için baştan kayıt üretilmez; tanışma veya tanımlı bağ oluştuğunda sparse graph üzerinde yaratılır.
- `friend`, `rival`, `conflicted` gibi okunabilir etiketler sayısal state'ten türetilir ve birden fazlası aynı anda geçerli olabilir.

#### Değişim geçmişi

- Her scene iki yön için farklı relationship event'leri üretebilir.
- LLM delta ve yorum önerir; backend aralık, personality, mevcut state ve maksimum değişim kurallarını uygular.
- Event ile snapshot aynı transaction içinde güncellenir.
- Boyutlar farklı değişim/decay kurallarına sahip olabilir; örneğin familiarity yavaş, tension daha hızlı değişebilir.

#### Public projection

Public World Viewer ham sayıları veya gizli öznel algıları göstermez. Yalnızca yayınlanması güvenli, türetilmiş ilişki açıklamalarını ve onaylı objektif bağları gösterir.

---

## WADR-008 — Memory Görünürlüğü ve Karakterler Arası Bilgi Aktarımı

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Karaktere özel bilgi, ortak deneyim, sır, söylenti ve public world bilgisinin kapsamı ile bir karakterden diğerine aktarılırken provenance ve güven düzeyinin nasıl korunacağı belirlenecektir.

### Karar

Kapsam, bilgi türü, provenance, confidence ve shareability taşıyan epistemik memory modeli kabul edilmiştir.

#### Bilgi kapsamları

- `private`: ilgili karaktere özel iç bilgi, yorum, sır ve World Owner konuşması
- `shared`: yalnızca belirtilen karakterlerin veya grubun bildiği bilgi
- `world`: dünya içinde öğrenilebilir gerçek; karakterin otomatik olarak bildiği anlamına gelmez
- `public`: World Viewer için ayrıca yayınlanmış güvenli projection

#### Epistemik türler ve provenance

- Memory; `fact`, `belief`, `observation`, `claim`, `rumor`, `interpretation` veya `secret` gibi bir bilgi türü taşır.
- Kaynak türü/kimliği, kaynak karakter, ilgili scene, subjects, confidence, oluşma ve olay zamanı mümkün olduğunca kaydedilir.
- Bir karakterin iddiası diğer karakterde doğrudan gerçek değil, kaynağı belirtilmiş claim olarak oluşur.
- Çelişkili iddialar tek bir kayıtta zorla birleştirilmez; ayrı provenance zincirleriyle korunur.

#### Paylaşılabilirlik

Memory görünürlüğünden ayrı olarak `never`, `owner_only`, `trusted_characters`, `explicit_permission` veya `freely_shareable` gibi paylaşım politikası taşır.

- `never` kapsamındaki bilginin içeriği, izin verilmeyen bir alıcıya konuşma üreten context'in hiçbir bölümüne verilmez; yalnız paylaşım seçeneklerinden çıkarmak yeterli değildir. `owner_only` ve diğer politikalar da gerçek alıcıya göre değerlendirilir.
- Diğer paylaşımlar relationship, personality, goals, verilmiş sözler ve hassasiyet kuralları altında değerlendirilir.

#### World Owner sohbetlerinin paylaşımı — AK-001: KABUL

- Özel sohbet memory'leri varsayılan `private` erişim ve `owner_only` paylaşım politikası taşır. Karakter bunları kendi deneyimi olarak değerlendirir; başka karaktere yönelik konuşma context'ine izin olmadan taşımaz.
- World Owner'ın açık izni, yalnız belirtilen bilgi ve belirtilen alıcılar için paylaşım yetkisi oluşturur. Örneğin “bunu Mira'ya söyleyebilirsin” bütün sohbeti veya bütün karakterleri kapsamaz. Belirsiz izin kapsamı genişletilmez.
- İzin, ilgili kaynak mesaj ve bilgi/alıcı kapsamıyla kaydedilir; paylaşımda kaynak/provenance korunur. İzin verilmesi bilginin bütün karakterlere otomatik aktarılması değil, uygun bir etkileşimde paylaşılabilmesi demektir.
- Trust, affection veya başka ilişki eşikleri açık izin yerine geçmez. Türetilmiş memory, reflection ve özetler de aynı sınırı korur; alıcı karaktere aktarım sonraki alıcılara sınırsız paylaşım hakkı vermez.
- Karakterler arası paylaşım izni public World Viewer'da yayın izni değildir; özel sohbetlerin public yayın yasağı devam eder.

#### Türetilen bilginin sınırları

- Memory'den türetilen özet, reflection, goal, belief ve yeniden birleştirilmiş memory kaynak kimliklerini taşır; kaynakların erişim/paylaşım kısıtlarını kendiliğinden genişletemez.
- Birden fazla kaynaktan türetilen kaydın izinli alıcıları kaynak izinlerinin kesişimiyle sınırlandırılır. Belirsiz veya eksik provenance daha geniş erişim gerekçesi olmaz; kayıt incelemeye ayrılır.
- Context builder yalnız memory retrieval sonucunu değil, definition, goal, reflection, özet ve transcript dahil bütün context bileşenlerini alıcıya göre filtreler. Sadece model talimatıyla gizlilik garantisi verildiği varsayılmaz.
- Public projection ayrı ve açık onaylı bir yayın ürünüdür; kaynak memory'nin karakterler arası paylaşım politikasını değiştirmez. Yayınlanması yasak içerik, sırf özetlendiği için yayınlanabilir hâle gelmez.
- Consolidation veya tekrar sayısı bir claim/rumor'ı doğrulanmış fact'e çeviremez. Aynı kaynağın tekrarları bağımsız kanıt sayılmaz; fact kabulü için yetkili dünya kaydı veya açık doğrulama dayanağı gerekir.
- Mood'un karaktere özgü baseline'a yaklaşması ve aşağıdaki hafıza davranışı AK-004 kapsamında kabul edilmiştir. Mood decay memory'yi silmez veya ilişki güvenini sıfırlamaz; temel kişiliğin gelişim sınırları WADR-009'da ayrıca tanımlanmıştır.

#### Ortak deneyim ve öznel memory

- Scene'in objektif ortak özeti `shared_experience` olarak kaydedilebilir.
- Ortak özet, doğrulanmış eylem/gözlem ile katılımcı iddiasını ayırır; bir konuşmada söylenen şeyin doğruluğunu varsaymaz. Tek çağrılı arka plan özetleri de aynı bilgi kapsamı ve provenance kurallarına tabidir.
- Her katılımcı aynı scene için kendi öznel memory'sini ayrı oluşturur.
- Aynı olay karakterlerde farklı duygu, yorum ve confidence üretebilir.

#### Retrieval sınırı

Context builder yalnızca karakterin kendi memory'lerini, katıldığı paylaşımlı deneyimleri, gerçekten öğrendiği world bilgisini ve hedef karakter hakkında bildiklerini aday havuzuna alır. Başka karakterlerin private memory'si vector search adaylarına dahi dahil edilmez.

#### Hatırlama, unutma ve consolidation — AK-004 alt kararı: KABUL

- Önemli deneyimler, anlamlı sözler ve ilişki dönüm noktaları korunur. Gündelik/düşük önemdeki ayrıntıların hatırlanma önceliği dünya zamanı ilerledikçe azalabilir; bütün memory türlerine aynı decay uygulanmaz.
- Unutma, retrieval erişilebilirliğinin/önceliğinin azalmasıdır; kendiliğinden veritabanı silme veya yaşanmış geçmişi değiştirme işlemi değildir. Fiziksel silme/anonimleştirme ayrı retention süreçlerine tabidir; korunma ilkesi bu süreçleri iptal etmez.
- Context seçimi erişim filtresinden sonra konu ilgisi, önem, güncellik ve gerçek etkileşimlerle pekişme gibi sinyalleri bütçe içinde değerlendirir. Önemli memory'nin korunması her prompt'a tamamının eklenmesi demek değildir.
- Konu yeniden açıldığında ilgili eski memory tekrar retrieval adayı olabilir; düşük öncelik kalıcı erişim yasağı değildir. Hatırlama, kaynağın kapsamını veya paylaşım iznini genişletemez.
- Benzer anılar özetlenebilir; özet kaynak referanslarını, epistemik tür ayrımlarını ve en kısıtlı geçerli erişim/paylaşım sınırını korur. Çelişkili iddialar tek bir kesin gerçeğe dönüştürülmez; kaynak ayrıntıları yalnız özet üretildi diye silinmez.
- Importance ve pekişme backend kurallarıyla doğrulanır; LLM sınırsız önem atayamaz. Aynı kaydın teknik retry veya tekrar retrieval ile okunması yeni deneyim/bağımsız kanıt sayılmaz ve tek başına yapay pekişme yaratmaz.
- Yeterli dayanak bulunamayan ayrıntı uydurulmaz. Karakter belirsizliğini ifade edebilir veya açıklama isteyebilir; modelin tahmini yaşanmış bir anı olarak kalıcılaştırılmaz.
- Decay hızları, önem eşikleri ve retrieval ağırlıkları sürümlü teknik parametrelerdir; önemli söz/dönüm noktası ile gündelik selamlaşma senaryoları üzerinden kalibre edilir. Çevrimdışı süre aynı world_clock hesabına dahildir; geçmiş dönem için yapay memory üretilmez.

---

## WADR-009 — Autonomy, Goals ve Reflection Sistemi

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Karakterlerin kendi hedeflerini oluşturma, eylem önerme, scene başlatma, deneyimleri değerlendirme ve zaman içinde kontrollü biçimde gelişme sınırları belirlenecektir.

### Karar

Core drives, hiyerarşik goals, izin verilen domain actions ve event-driven reflection kullanan sınırlandırılmış agency modeli kabul edilmiştir.

#### Agency ve goals

- Core drives, karakter tanımından türetilen ve goal seçimini etkileyen yavaş değişen motivasyonlardır.
- Long-term goals günler/haftalar, short-term goals sonraki somut adımlar, scene intentions ise tek sahnedeki amaçlar için kullanılır.
- Goal'lar `PROPOSED`, `ACTIVE`, `BLOCKED`, `PAUSED`, `COMPLETED`, `FAILED` ve `ABANDONED` durumlarıyla izlenir.
- LLM goal önerebilir; backend sayı, tekrar, uygulanabilirlik, dünya kuralları ve başka karakterlere yetkisiz sonuç dayatma kontrollerini yapar.
- Amaç sonuç garantisi değil girişim olarak ifade edilir.

#### İzin verilen eylemler

- Karakter yalnızca `request_scene`, `move_to_location`, `send_in_world_message`, `observe`, `reflect`, `update_goal` ve `wait` gibi allowlist domain action'ları önerebilir.
- Backend konum, zaman, müsaitlik, ilişki, bütçe, cooldown ve güvenlik doğrulamasından sonra eylemi uygular.
- İnternet, haricî mesaj, shell, dosya sistemi veya sınırsız tool erişimi ilk sürümde verilmez.

#### Reflection ve gelişim

- Reflection; önemli scene, relationship eşiği, goal sonucu, world event veya günlük consolidation gibi anlamlı tetikleyicilerde çalışır.
- Belief, goal, memory consolidation, diary ve self-model değişiklikleri yalnız öneri olarak üretilir ve backend tarafından doğrulanır.
- Mood kısa, belief/relationship/goal orta, personality/temperament ise çok uzun zaman ölçeğinde değişir.
- Büyük personality değişiklikleri World Owner incelemesine yönlendirilebilir.

#### Çalışma sıklığı

Planlama sürekli polling yerine event ve zaman bloğu değişimlerinde, bütçe kontrollü yapılır. Düşük önem durumunda LLM çağrısı olmadan deterministik `wait` seçilebilir.

---

## WADR-010 — Moderasyon ve Güvenlik Modeli

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Katkıcı girdilerinin, karakter tanımlarının, autonomous scene'lerin ve public projection'ların hangi otomatik ve insan denetimlerinden geçeceği belirlenecektir.

### Kabul edilen moderasyon mimarisi

Katmanlı otomatik kontroller, World Owner onayı ve internal/public yayın ayrımı kabul edilmiştir.

#### Katkı hattı

- Form şeması ve alan/uzunluk limitleri doğrulanır.
- Prompt injection, kişisel veri/gerçek kişi, yasaklı içerik ve telif riski sinyalleri taranır.
- Otomatik sistem `PASS`, `REVIEW` veya `BLOCK` sonucu ile gerekçeler üretir; karakteri kendi başına aktive etmez.
- Nihai karakter kabulü ve yayın kararı World Owner'a aittir.
- Ham katkı metni normalize edilmiş karakter tanımı ve sürümlü template üzerinden derlenir; doğrudan system prompt olmaz.

#### Runtime ve yayın güvenliği

- Scope edilmiş context, yapılandırılmış çıktı, allowlist domain actions, turn/token limitleri ve private memory sınırları uygulanır.
- Şüpheli çıktı scene'i durdurabilir veya quarantine'e gönderebilir.
- Autonomous scene varsayılan olarak `internal` oluşur.
- Public summary ayrı üretim ve moderasyon hattından geçer.
- MVP'de public summary'ler manuel onaylanır; düşük riskli otomatik yayın ancak sistem davranışı ölçüldükten sonra açılabilir.
- `featured` içerik yalnız World Owner'ın açık onayıyla yayınlanır.

#### Operasyonel kontroller

- Moderasyon sonucu, politika sürümü, risk kategorileri, reviewer kararı ve zamanları audit edilebilir biçimde tutulur.
- World Owner; autonomy'yi veya queue'ları duraklatabilir, karakteri askıya alabilir, public içeriği gizleyebilir ve model/prompt sürümünü devre dışı bırakabilir.
- Contributor başvuru sayısı, gönderim sıklığı ve medya yüklemeleri rate limit ve kötüye kullanım kontrollerine tabidir.

#### İçerik sürümü, medya ve yayından kaldırma

- Yayın adayı değiştirilemez içerik sürümü, kaynak referansları ve içerik hash'i taşır. İnsan onayı bu adayın kimliğine ve hash'ine bağlanır; publisher yalnız aynı onaylı içeriği yayınlar, yayın sırasında yeniden üretim yapmaz.
- Aday metin/medya değişirse eski onay yeni sürüm için geçerli olmaz. Yayın transaction'ı adayın onayını, kaynak uygunluğunu ve geri çekilmemiş olduğunu tekrar doğrular.
- Contributor taslakları ve inceleme bekleyen medya private Storage alanında tutulur. Erişim sahiplik/admin yetkisiyle kontrol edilir; gerekiyorsa kısa ömürlü signed URL kullanılır. Yayına yalnız doğrulanmış ve onaylı medya sürümü alınır.
- Dosya boyutu, gerçek içerik türü ve izin verilen formatlar doğrulanır; contributor onaylı nesneyi aynı yol üzerinden değiştiremez.
- Yayından kaldırma; projection, uygulama önbelleği ve yönetilen medya erişimini birlikte ele alır. Eski publisher retry'ı kaldırılan sürümü yeniden yayınlayamaz. Daha önce ziyaretçilerce indirilmiş kopyaların veya dış önbelleklerin geri alınabileceği garanti edilmez.

### İçerik politikası

- Bütün aktif karakterler açıkça yetişkindir.
- Dünya olgun fakat explicit olmayan anlatım kullanır.
- Romantizm, kıskançlık, ayrılık, ihanet ve karmaşık yetişkin ilişkileri işlenebilir.
- Ölüm, travma, bağımlılık ve psikolojik zorluklar dikkatli ve bağlama uygun ele alınabilir.
- Ölçülü yetişkin dili mümkündür.
- Cinsellik ima edilebilir ancak açık/graphic cinsel içerik üretilmez.
- Şiddet hikâyesel olabilir ancak graphic ayrıntı üretilmez.
- Taciz, kendine zarar verme ve benzeri hassas konular övülmez; public yayın öncesinde ek incelemeye düşer.
- Public summary, internal scene'den daha güvenli ve daha az ayrıntılı olabilir.

---

## WADR-011 — Güncellenmiş Teknoloji Yığını

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Deployment modeli, LLM ve embedding runtime'ı, backend, veri platformu, queue/worker, frontend ve gözlemlenebilirlik alt kararları sırasıyla değerlendirilecektir.

### Alt karar 1 — Deployment modeli: KABUL

Cloud control plane ve yerel AI worker modeli kabul edilmiştir.

```text
Cloud
├── Next.js public/contributor/admin arayüzleri
├── Hafif FastAPI control plane
└── Supabase: Auth, PostgreSQL, Storage, Realtime, Queues, Cron

Yerel AI makinesi
├── Python worker'lar
├── Yerel LLM runtime
├── Hermes
├── Embedding modeli
└── Opsiyonel reranker
```

- Public World Viewer ve katkı sistemi yerel AI makinesi çevrimdışıyken çalışmaya devam eder.
- Yerel makine çevrimdışıyken yeni AI işleri queue'da kalır ve autonomous scene üretimi duraklatılır.
- Yerel worker yalnız dışarı doğru güvenli bağlantı kurar; LLM runtime internete açılmaz.
- Worker heartbeat ve kapasite bilgisi control plane'e bildirilir.
- Queue mesajları büyük/hassas içerik yerine sürümlü kimlik referansları taşır.
- Worker uygulaması container/adapter sınırları sayesinde ileride GPU VPS'e taşınabilir.

### Alt karar 2 — LLM modeli ve runtime: ERTELENDİ

Kesin model, quantization, runtime ve context boyutu gerçek workload benchmark'larından sonra seçilecektir.

#### Bilinen donanım sınırları

- Hedef yerel AI makinesi Ryzen 9 5900HX, 32 GB RAM ve 8 GB VRAM'li RTX 3070 Laptop GPU'dur.
- İlk kapasite varsayımı tek eşzamanlı ana LLM üretimidir.
- Çok büyük context yerine memory retrieval ve conversation/scene summary kullanılacaktır.
- Embedding/reranking işlerinin ana LLM ile VRAM rekabeti ayrıca ölçülecektir.

#### Karardan bağımsız mimari gereksinim

Worker kodu belirli modele veya runtime'a doğrudan bağlanmayacaktır. Bir `LLMProvider` adapter sınırı üzerinden en az model kimliği, chat/streaming, yapılandırılmış çıktı, timeout, kullanım metrikleri ve health/capacity yetenekleri sunulacaktır.

#### Benchmark ölçütleri

- İlk token ve toplam yanıt gecikmesi
- Token/saniye ve VRAM/RAM kullanımı
- Türkçe diyalog ve karakter tutarlılığı
- JSON/şema doğrulama başarı oranı
- Çok turlu scene kalitesi
- Context uzunluğu ve prompt takip başarısı
- Uzun süreli worker kararlılığı ve sıcaklık

Hermes 3 8B quantized, Ollama ve llama.cpp yalnızca başlangıç adaylarıdır; henüz nihai karar değildir.

### Alt karar 3 — Backend ve worker dili: KABUL

Python ve FastAPI tabanlı control plane ile aynı domain paketlerini kullanan Python AI worker'ları kabul edilmiştir.

```text
Next.js ──► FastAPI control plane ──► Supabase / Queues
                     ▲
                     └── ortak Python domain paketleri ── AI workers
```

- Dünya ve karakter domain kuralları Python backend'de kalır; Next.js'e taşınmaz.
- FastAPI ile worker'lar character, scene, memory, affect, relationship, moderation ve queue message şemalarını paylaşır.
- Pydantic v2 API, queue ve LLM yapılandırılmış çıktı sınırlarında doğrulama sağlar.
- Başlangıç araç seti Python 3.12+, FastAPI, Pydantic v2, Uvicorn, pytest, Ruff ve statik tip kontrolüdür.
- Domain kodu FastAPI, Supabase ve LLM runtime ayrıntılarına doğrudan bağımlı olmayacaktır.

### Alt karar 4 — Veri platformu: KABUL

MVP ve ilk production sürümü için managed Supabase kabul edilmiştir.

- PostgreSQL ana source of truth'tür.
- Supabase Auth, Storage, Realtime, pgvector, Queues ve Cron yetenekleri kullanılır.
- Ana domain verisi standart PostgreSQL tablolarında ve Git'te tutulan SQL migration'larla yönetilir.
- Domain servisleri Supabase SDK tiplerine bağlanmaz; repository, queue ve storage adapter sınırları kullanılır.
- Exposed şemalardaki kullanıcı verisi RLS ile korunur; internal world ve operasyon verileri Data API'ye açılmamış private şemalarda tutulur.
- Browser yalnız publishable key kullanır; secret/service-role anahtarları frontend'e verilmez.
- Anonymous erişim yalnız yayınlanmış public projection'larla sınırlıdır.
- Self-hosting veya bağımsız PostgreSQL bileşenlerine geçiş ilk sürümde yapılmaz; standart SQL ve adapter sınırlarıyla gelecekte mümkün bırakılır.

### Alt karar 5 — Frontend mimarisi: KABUL

Public World Viewer, Contributor Portal ve Admin Studio tek bir Next.js App Router uygulamasında ayrı route alanları olarak tutulacaktır.

- TypeScript, Tailwind CSS ve shadcn/ui ortak tasarım katmanını oluşturur.
- Supabase Auth için cookie tabanlı SSR yaklaşımı kullanılır; ilgili paket sürümleri kontrollü sabitlenir.
- Server Components public ve server-rendered okumalar için kullanılır.
- TanStack Query API/server state'i, React Hook Form katkı formları ve Zustand yalnızca karmaşık geçici UI state'i için kullanılır.
- Supabase Realtime yalnız izin verilen public veya operasyonel projection güncellemelerinde kullanılır.
- FastAPI OpenAPI şemasından TypeScript tipleri/client üretilerek Python ve TypeScript sözleşmelerinin elle çoğaltılması önlenir.
- Route gizleme yetkilendirme sayılmaz; FastAPI rol ve token'ı, PostgreSQL ise RLS/izinleri ayrıca doğrular.

### Alt karar 6 — PostgreSQL erişimi ve migration: KABUL

FastAPI ve worker'lar repository adapter'ları arkasında SQLAlchemy 2 ve psycopg 3 ile PostgreSQL'e bağlanacaktır.

- Basit entity işlemlerinde ORM, karmaşık retrieval/event sorgularında SQLAlchemy Core veya parametreli SQL kullanılabilir.
- Domain katmanı SQLAlchemy session/model tiplerini veya Supabase client'ını bilmez.
- Şema tarihçesinin source of truth'u Git'teki Supabase CLI SQL migration'larıdır; ayrı ve çakışan Alembic migration tarihçesi tutulmaz.
- Cloud API ve yerel worker ayrı database identity/credential ve minimum yetkiler kullanır.
- LLM çağrısı sırasında veritabanı transaction'ı açık tutulmaz.
- LLM öncesi state okunur; sonuç kısa transaction, version kontrolü ve optimistic concurrency ile uygulanır.
- Connection pool boyutları platform limitleri ve gerçek yük testine göre sınırlandırılır.

### Alt karar 7 — Queue ve worker organizasyonu: KABUL

Supabase Queues üzerinde rol bazlı Python worker'lar ve provider-bağımsız queue adapter kabul edilmiştir.

- GPU worker LLM ağırlıklı işleri başlangıçta concurrency 1 ile yürütür.
- CPU worker embedding, deterministik reranking, deduplication ve domain processing işlerini yürütür.
- Publisher worker onay/yayın projection'ları, Realtime bildirimleri ve Obsidian mirror işlerini yürütür.
- Maintenance worker consolidation, retention, integrity ve günlük dünya bakım işlerini yürütür.
- Roller aynı kod tabanı/container image üzerinde farklı başlangıç komutlarıyla çalışabilir; MVP'de düşük hacimli roller proses olarak birleştirilebilir.
- Worker'lar sürümlü payload, idempotency, visibility/lease, heartbeat, retry, quarantine/dead-letter ve graceful shutdown kurallarına uyar.
- Domain handler'ları `JobQueue` adapter sınırının arkasında kalır; `pgmq` ayrıntılarına bağlanmaz.
- Kesin olarak job üretmesi gereken state değişimleri queue mesajıyla aynı transaction'da veya transactional outbox ile güvence altına alınır.

#### Teslim, deneme ve tamamlanma protokolü

- Queue teslimi ile domain sonucunun tekilleştirilmesi ayrı sorumluluklardır. Visibility süresi dolunca yeniden teslim beklenir; uygulama sonuçların en fazla bir kez uygulanmasını unique anahtar ve transaction ile sağlar.
- Domain etkisi kimliği retry boyunca sabittir; `attempt_id` her denemede değişir. Örneğin scene/processing sürümü/etki türü/katılımcı kapsamı aynı etkiyi tanımlar; yeni deneme yeni domain etkisi yaratmaz.
- Worker görünmezlik/lease süresini gerçek zamanla yeniler. İş sahibi deneme ve artan sahiplik nesli sonuç commit'inde doğrulanır; lease kaybeden veya geç kalan worker sonucu uygulayamaz. Worker heartbeat tek başına iş sahipliği kanıtı değildir.
- İşlem sırası: işi al, geçerliliği doğrula, kısa transaction ile gerekli state/sahipliği oku veya ayır, transaction dışında üret, kısa transaction ile sonucu ve outbox'ı commit et, ardından queue mesajını onayla/arşivle. İş öncesinde kuyruktan kalıcı silme yapılmaz.
- Commit sonrası queue onayından önce crash olursa tekrar teslim edilen iş mevcut sonucu tanır ve domain etkisini yeniden üretmeden tamamlanır. Commit öncesi crash durumunda kaydedilmiş geçerli checkpoint'ten devam edilir; kaydedilmemiş üretim tekrar yapılabilir.
- Transient hata için sınırlı backoff/retry uygulanır; kalıcı validation/policy hatası veya deneme sınırının dolması quarantine/dead-letter durumuna gider. Manuel retry da aynı domain tekilleştirme kurallarına uyar.
- İş sözleşmesi gerekli state/definition sürümlerini, iptal durumunu ve zaman duyarlı işlerde geçerlilik zamanını içerir. Başlangıçta ve sonuç commit'inde yeniden kontrol yapılır. AK-002 uyarınca eski sahne adayları yeniden değerlendirilir, birikmiş rutin işleri birleştirilir; kalıcı mesaj ve sonuç uygulama işleri korunur. İş türüne özgü geçerlilik süreleri yapılandırılır.
- Reservation, bütçe ve başarısız processing kayıtlarını tarayan idempotent recovery işi bulunur. UI başarısız/inceleme bekleyen akışı görünür kılar; bekleyen iş sessizce başarıya çevrilmez.

### Alt karar 8 — Gözlemlenebilirlik: KABUL

Katmanlı ve aşamalı gözlemlenebilirlik kabul edilmiştir.

- Python servisleri standart logging/structlog ile JSON log üretir; Next.js server logları aynı correlation kimliklerini taşır.
- `request_id`, `job_id`, `scene_id`, `character_id`, `llm_run_id` ve `submission_id` akışlar arasında ilişkilendirme sağlar.
- Token, cookie, tam prompt, private memory, ham transcript ve özel mesaj varsayılan loglara yazılmaz.
- `llm_runs`, `job_runs`, `moderation_cases`, `audit_events`, `scene_processing_runs` ve `worker_heartbeats` önemli operasyon durumlarını PostgreSQL'de kalıcı tutar.
- Sentry benzeri hata izleme opsiyonel telemetry adapter'ı arkasında ve hassas alanları temizleyen redaction ile kullanılabilir.
- Liveness/readiness endpoint'leri ile worker heartbeat, model, queue, GPU/VRAM, sıcaklık ve son başarılı iş durumu Admin Studio'da izlenir.
- OpenTelemetry, Prometheus/Grafana ve dağıtık tracing gerçek ölçek ihtiyacı oluştuğunda eklenir.

### Alt karar 9 — Admin chat streaming: KABUL

Admin chat için private Supabase Realtime Broadcast üzerinden ephemeral token stream'i ve PostgreSQL'de kalıcı final mesaj modeli kabul edilmiştir.

- FastAPI admin mesajını ve idempotent chat job'ını güvenilir biçimde oluşturur.
- Admin Studio konuşmaya özel private, yalnız-okuma Broadcast kanalına abone olur.
- Yerel GPU worker token delta ve durum olaylarını yayınlar; prompt, memory veya gizli context payload'a eklenmez.
- Tam model cevabı yalnızca tamamlandığında kalıcı message kaydı olarak yazılır ve source of truth olur.
- Stream koparsa LLM işi devam eder; UI yeniden bağlandığında kesin mesajı API/PostgreSQL'den alır.
- Realtime kullanılamazsa job polling ve final mesaj sorgusu fallback olur.
- Contributor ve anonymous roller admin chat kanallarına katılamaz; kanal adı tek başına yetki sağlamaz ve Realtime Authorization/RLS uygulanır.

#### Stream sözleşmesi ve hata davranışı

- Her stream olayı `conversation_id`, `message_id`, `attempt_id`, artan `sequence` ve olay türü taşır. UI tekrarları eler; farklı üretim denemelerinin parçalarını birleştirmez.
- Kalıcı job/message durumu en az `queued`, `generating`, `completed`, `failed` ve `cancelled` ayrımını yapar. Token parçaları geçici ön izlemedir; canonical mesaj veya domain etkisi değildir.
- Yeniden bağlanan UI kesin mesajı ve güncel job/attempt durumunu API'den okur. İş sürüyorsa eksik parçaların geri getirileceği vaat edilmez; eksik ön izleme sıfırlanabilir ve final mesaj/polling beklenir.
- Worker çökerse UI'da yarım ön izleme tamamlanmış cevap olarak gösterilmez. Yeni deneme ayrı attempt olarak başlar. Final mesajı kaydedilmiş iş yalnız final bildirim kayboldu diye yeniden üretilmez.
- Canonical final mesaj, generation sonucu ve gerekli domain processing outbox kaydı birlikte commit edilir. Mesajın tamamlanması ile memory/affect processing'in tamamlanması ayrı izlenir; sonraki etkileşim gerekli state etkileri uygulanmadan başlamaz.
- GPU worker stream'i kendi sınırlı servis kimliğiyle yetkili yayın adapter'ına iletir. Admin read-only, worker ilgili topic'lerde write yetkilidir; browser veya yerel worker'a geniş `service_role` anahtarı verilmesi çözüm olarak kullanılmaz.
- Realtime bağlantısında izinler önbelleğe alınabildiği için rol/session iptali yalnız politika değişimine bırakılmaz. Yeni üretim ve yayın sırasında yetki tekrar doğrulanır; iptal edilen erişime yayın kesilir, kanal/oturum sonlandırma ve token yenileme davranışı test edilir.
- Token başına zorunlu ağ mesajı yerine sınırlı aralık/boyutta chunk yayınlanabilir; final mesaj canonical kaynak olmaya devam eder.

### Alt karar 10 — Deployment paketleme: KABUL

Container-first, provider-neutral deployment; GitHub Actions CI ve manuel production onayı kabul edilmiştir.

- Next.js web, FastAPI API ve rol parametresi alan Python worker deploy edilebilir artefact'lardır.
- Yerel AI plane Docker Compose ile çalışır; cloud API standart container olarak deploy edilebilir.
- Next.js container veya uyumlu managed frontend platformunda çalışabilir; uygulama kodu tek sağlayıcıyı varsaymaz.
- CI frontend lint/typecheck/test/build; backend lint/typecheck/test/container build; database migration/RLS kontrollerini çalıştırır.
- Production migration/deploy otomatik ve onaysız olarak her `main` push'unda çalışmaz.
- Cloud ve yerel worker ayrı, minimum yetkili secret'lar kullanır; `.env` dosyaları Git'e eklenmez.
- Managed platform HTTPS sağlıyorsa Caddy/Nginx zorunlu değildir; VPS ihtiyacında yeniden değerlendirilir.
- Kesin cloud sağlayıcısı maliyet, bölge, container, cold-start, secret/log ve Supabase gecikmesi ölçüldükten sonra seçilecektir.

### Kabul edilen teknoloji özeti

| Katman | Karar |
| --- | --- |
| Public/control plane | Cloud deployment |
| AI plane | Yerel, dışarı doğru bağlanan worker'lar |
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| Database erişimi | SQLAlchemy 2 + psycopg 3 |
| Veri platformu | Managed Supabase PostgreSQL |
| Platform servisleri | Auth, Storage, Realtime, pgvector, Queues, Cron |
| Frontend | Next.js App Router, TypeScript, Tailwind, shadcn/ui |
| Frontend state/form | TanStack Query, React Hook Form, Zod; sınırlı Zustand |
| Worker | Rol bazlı Python worker'lar, queue adapter |
| Streaming | Private Realtime Broadcast + kalıcı PostgreSQL mesajı |
| Gözlemlenebilirlik | JSON logs, operasyon tabloları, redacted error tracking |
| Paketleme | Container-first, Docker Compose, GitHub Actions |
| LLM/embedding | Benchmark sonrası seçilecek; provider adapter zorunlu |

---

## WADR-012 — Veritabanı ve Event Şeması

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

İlişkisel veri ile JSONB sınırı, şema modülleri, kimlik/zaman kuralları, event ve snapshot tabloları, indeksler ve retention yaklaşımı sırasıyla değerlendirilecektir.

### Alt karar 1 — İlişkisel çekirdek ve JSONB sınırı: KABUL

- Yetkilendirme, RLS, foreign key, join, filtreleme, sıralama, unique constraint, domain invariant ve sık indeks gerektiren alanlar gerçek ilişkisel kolon/tablo olur.
- Katılımcılar, sahiplik ve karakterler arası bağlantılar yalnız JSON dizilerinde tutulmaz; junction/relationship tabloları kullanılır.
- Sürümlenmiş character definition snapshot'ları, doğrulanmış LLM çıktıları, event delta ayrıntıları, provider metadata'sı ve nadir sorgulanan esnek payload'lar JSONB olabilir.
- Her JSONB payload belgelenmiş Pydantic şemasına ve `schema_version` alanına sahip olur; yazılmadan önce doğrulanır.
- JSONB güvenlik/sahiplik için tek kaynak olmaz ve kontrolsüz metadata deposu olarak kullanılmaz.
- Sık sorgulanmaya başlayan JSONB alanları sonraki migration ile gerçek kolona çıkarılır.
- Güncel snapshot ve append-only event geçmişi ayrılır; ilgili event ile snapshot değişimi aynı transaction içinde yapılır.
- Character definition sürümlenir ve aktif sürüm karakter kaydından referanslanır; katkı kaynağı ve onay bilgisi korunur.

### Alt karar 2 — PostgreSQL şema sınırları: KABUL

Erişim sınırına göre `public`, `world_private` ve `ops_private` uygulama şemaları kabul edilmiştir.

- `public`, RLS ile korunan profile/katkı kayıtları ve anonim okunabilen güvenli fiziksel projection tablolarıyla sınırlıdır.
- `world_private`, karakter tanımı/runtime state'i, dünya/konum, scene, admin konuşması, memory, social graph, affect ve agency source-of-truth tablolarını içerir ve Data API'ye açılmaz.
- `ops_private`, LLM/job/worker çalışmaları, moderasyon, audit, prompt/model registry ve sistem ayarlarını içerir ve Data API'ye açılmaz.
- Supabase'in yönettiği `auth`, `storage`, `realtime`, `pgmq` ve `cron` şemaları uygulama şemalarından ayrı kalır.
- Publisher Worker, onaylanan internal içeriği `public` fiziksel projection tablolarına yazar; public istemci internal tablolara view ile doğrudan bağlanmaz.
- Gerekli sınırlı view'lar açık kolon listesi, minimum grant, RLS testi ve `security_invoker` yaklaşımıyla oluşturulur.

### Alt karar 3 — Kimlik, zaman ve event standartları: KABUL

- Ana kayıtlar PostgreSQL tarafından üretilen UUID primary key kullanır; public slug kimlikten ayrıdır ve foreign key olarak kullanılmaz.
- Gerçek timestamp'ler `timestamptz` ile UTC anlamında saklanır; arayüzde görüntüleme saat dilimine çevrilir.
- Dünya zamanı sistem zamanından ayrı `world_clock` state'iyle temsil edilir.
- Event'ler dünyadaki olay zamanı için `occurred_at`, sisteme kayıt zamanı için `recorded_at` taşıyabilir.
- Değişebilir snapshot tabloları integer `version` ve `updated_at` ile optimistic concurrency uygular.
- Generic soft delete yerine domain lifecycle durumları; gerçek silme/anonimleştirme için açık retention süreçleri kullanılır.
- Tek dev event tablosu yerine emotion, relationship, goal, presence ve world gibi domain'e özel append-only event tabloları kullanılır.
- Event'ler source, schema version, causation ve correlation bilgilerini taşır; düzeltmeler eski event'i değiştirmek yerine correction/reversal/superseding event üretir.
- Tekrarlanabilir komut ve job'lar kapsamı içinde unique `idempotency_key` kullanır.
- State değişikliğiyle birlikte kesin job/notification gerektiren akışlar transactional outbox veya aynı transaction içinde güvenli queue enqueue kullanır.
- Uygulama rollerinin append-only event tablolarında normal akışta UPDATE/DELETE yetkisi yoktur.

### Alt karar 4 — Constraint, indeks ve retention: KABUL

- Domain invariant'ları mümkün olduğunda CHECK, UNIQUE, foreign key ve exclusion benzeri veritabanı constraint'leriyle de korunur.
- Kullanılan foreign key ve RLS sahiplik kolonları dahil olmak üzere beklenen erişim yollarına temel indeksler eklenir.
- Aktif kayıtların baskın olduğu sorgularda ölçülü partial index kullanılabilir.
- Başlangıçta event tabloları partition edilmez ve pgvector HNSW zorunlu değildir.
- Exact vector search ve kritik sorgular gerçekçi veriyle, RLS açıkken `EXPLAIN (ANALYZE, BUFFERS)` kullanılarak ölçülür; HNSW/partitioning ancak kanıtlanan ihtiyaçta eklenir.
- Retention süreleri kod içine dağılmaz; domain event/audit uzun, yüksek hacimli operasyon/debug kayıtları daha kısa veya aggregate edilebilir politikalarla yönetilir.
- Silme ve arşivleme işleri küçük batch'ler hâlinde, gözlemlenebilir ve idempotent çalışır.

---

## WADR-013 — Backend, Worker ve Frontend Mimarisi

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Repo sınırı, modüler backend yapısı, frontend feature sınırları, ortak sözleşmeler ve bağımlılık yönleri sırasıyla değerlendirilecektir.

### Karar

Yapılandırılmış monorepo, tek Python backend paketi, modüler monolith ve FastAPI OpenAPI'den üretilen frontend sözleşmeleri kabul edilmiştir.

### Repo yapısı

```text
cognitive-character-engine/
├── apps/
│   └── web/
├── services/
│   └── backend/
├── supabase/
│   ├── migrations/
│   ├── tests/
│   └── config.toml
├── infrastructure/
│   ├── docker/
│   └── compose/
├── obsidian/
│   └── templates/
├── docs/
│   ├── architecture/
│   ├── decisions/
│   └── operations/
├── scripts/
└── .github/workflows/
```

- Python bağımlılıkları `uv` ve `pyproject.toml`, frontend bağımlılıkları `pnpm` ve lockfile ile yönetilir.
- Model dosyaları, runtime cache, secret'lar ve generated Obsidian vault içeriği Git'e eklenmez.
- Boş klasör ve soyutlama önceden topluca üretilmez; sınırlar gerçek özelliklerle birlikte oluşturulur.

### Backend yapısı

```text
services/backend/src/cce/
├── api_entrypoint.py
├── worker_entrypoint.py
├── core/
├── modules/
│   ├── identity/
│   ├── contributions/
│   ├── characters/
│   ├── world/
│   ├── scenes/
│   ├── memory/
│   ├── social/
│   ├── affect/
│   ├── agency/
│   ├── moderation/
│   └── publishing/
└── infrastructure/
    ├── database/
    ├── llm/
    ├── embeddings/
    ├── queues/
    ├── storage/
    ├── realtime/
    └── telemetry/
```

- Her modül ihtiyaca göre router/schema/service/domain/repository bileşenlerine ayrılır.
- Router HTTP, application service use-case orkestrasyonu, domain saf kurallar, infrastructure dış sistem adapter'larıyla ilgilenir.
- Domain FastAPI, SQLAlchemy, Supabase, queue veya LLM runtime import etmez.
- Modüller başka modülün tablolarına gelişigüzel yazmaz; application service veya açık domain port'u üzerinden çalışır.
- API ve bütün worker rolleri aynı backend paketini ve domain kurallarını kullanır.

### Frontend yapısı

```text
apps/web/src/
├── app/
│   ├── (public)/
│   ├── (auth)/
│   ├── contributor/
│   └── admin/
├── features/
│   ├── world-viewer/
│   ├── character-submissions/
│   ├── moderation/
│   ├── admin-chat/
│   └── operations/
├── components/
└── lib/
    ├── api/generated/
    └── supabase/
```

- Route klasörleri sayfa composition ve erişim sınırlarını, feature klasörleri davranış ve feature UI'ını taşır.
- FastAPI OpenAPI şemasından TypeScript client/tipleri üretilir; generated kod elle değiştirilmez.
- Server state TanStack Query/Server Components, geçici karmaşık UI state'i sınırlı Zustand ile yönetilir.
- Yetkilendirme yalnız frontend route kontrolüne bırakılmaz.

### Test sınırları

- Domain unit testleri dış servis olmadan çalışır.
- Repository ve migration integration testleri yerel Supabase/PostgreSQL üzerinde çalışır.
- API contract testleri generated frontend client ile uyumu doğrular.
- RLS testleri anonymous, contributor, World Owner ve worker rollerini ayrı ayrı kapsar.
- Scene/memory/relationship akışları sabit model çıktıları kullanan deterministic fixture'larla test edilir; canlı LLM testleri ayrı eval/benchmark grubudur.

---

## WADR-014 — MVP Kapsamı ve Fazlama

**Durum:** `KABUL`  
**Tarih:** 2026-09-21

Ortak dünyanın ilk yayınlanabilir sürümünde bulunacak dikey ürün akışı, ertelenecek özellikler ve tamamlanma ölçütleri belirlenecektir.

### Karar

Maksimum 50 karakteri destekleyecek mimari korunurken ilk test dünyası 3–5 aktif karakterle başlayan uçtan uca dikey MVP olarak geliştirilecektir.

#### MVP kapsamı

- Contributor kayıt/giriş, yapılandırılmış karakter taslağı, başvuru, durum, geri bildirim ve revizyon akışı
- World Owner başvuru inceleme, moderasyon sinyalleri, kabul/ret/değişiklik talebi ve karakter aktivasyonu
- Aktif karakteri askıya alma/arşivleme ve karakter tanımı ön izlemesi
- World Owner ile aktif karakter arasında private, streaming chat
- Tek dünya, merkezî world clock, temel konumlar ve character presence
- İki karakterli autonomous scene, kurallı aday puanı, bütçe/cooldown ve turn-based scene engine
- Core, episodic ve temel semantic memory; provenance ve scope kontrollü retrieval
- VAD (valence/arousal/dominance) mood/emotion events ve yönlü relationship snapshot/events; karaktere özgü baseline'a zamana bağlı dönüş kabul edilmiştir, sayısal aralık ve hızlar senaryo testleriyle kalibre edilir
- Basit short-term goals ve önemli scene sonrası reflection
- Sabit temel kişilik/ana değerler üzerinde deneyime bağlı görüş, ilişki ve goal gelişimi; reflection çekirdek kişiliği değiştiremez
- Public karakter profilleri, konumlar, ilişki açıklamaları ve manuel onaylı scene/timeline özetleri
- Contributor kredisi yalnız katkıcının tercihine bağlı public projection olarak gösterilir
- RLS rol testleri, queue worker'ları, idempotency/outbox, heartbeat, log/ops tabloları ve kill switch

#### MVP dışında

- 20–50 karakterin tamamını başlangıçta aktif çalıştırmak
- Üç veya daha fazla karakterli scene ve çoklu dünya
- Ayrıntılı harita, ekonomi, envanter veya sürekli yaşam simülasyonu
- Voice, animasyon, mobil uygulama ve Discord/Telegram
- Otomatik public yayın ve contributor'ın aktif karakteri doğrudan düzenlemesi
- Tam personality evolution, kapsamlı long-term planning ve zorunlu diary
- İnternet/haricî tool erişimi, gelişmiş director ve cross-encoder reranker
- Obsidian Generated mirror ve kontrollü authoring/import akışı
- Kubernetes, çoklu GPU ve dağıtık worker orkestrasyonu

#### Tamamlanma ölçütü

Bir contributor karakter tasarlayıp başvurduğunda; World Owner inceleme/revizyon/onay akışını tamamlayıp karakteri aktive edebildiğinde; World Owner karakterle private konuşabildiğinde; karakter başka bir karakterle geçerli autonomous scene yaşayıp katılımcıya özgü memory ve yönlü relationship değerlendirmeleri oluşturduğunda; World Owner güvenli özeti public timeline'a yayınlayabildiğinde ve contributor/anonymous kullanıcılar internal state veya chat'e erişemediğinde uçtan uca ürün akışı sağlanır. Relationship değerlendirmesi geçerli biçimde sıfır değişimle sonuçlanabilir; sırf etkileşim oldu diye state değişikliği zorlanmaz.

MVP'nin tamamlanması için bu akışa ek olarak aşağıdaki kabul koşulları da sağlanır:

- `AK-001`–`AK-004` kararları sonuçlandırılmış ve seçilen davranışlar ilgili akış/testlere işlenmiş olmalıdır.
- Duplicate job, commit sonrası crash ve eski worker sonucu çift mesaj, memory veya event üretmemelidir. Katılımcı etkileri kısmi uygulanmışken sahne tamamlandı sayılmamalıdır.
- Worker kesintisi ve tekrar bağlantı, seçilmiş dünya zamanı politikasıyla tutarlı çalışmalı; başarısız işler UI'da görünür ve güvenle yeniden ele alınabilir olmalıdır.
- AK-002 için gece–öğlen ve çok günlük kesinti senaryolarında dünya saati ilerlemeli, güncel presence/rutinler uzlaştırılmalı, eski sahne kotası birikmemeli ve gerçekleşmemiş konuşma/memory üretilmemelidir. Kesinti öncesi commit edilmiş turn etkileri kaybolmamalı veya çift uygulanmamalıdır.
- AK-003 için turn üretimi, turn sınırı ve processing sırasında admin mesajı test edilmelidir: durma isteğinden sonra yeni sahne turn'ü başlamamalı, geçerli transcript etkileri bir kez uygulanmalı ve admin yanıtı güncel state ile üretilmelidir. Timeout/processing hatası görünür olmalı; henüz başlamamış sahne için deneyim uydurulmamalıdır.
- Askıya alma, iptal, yetki değişimi ve onay geri çekme sonrası eski işler izinsiz state/yayın üretememelidir.
- Definition revizyonu geçmiş olayları sessizce değiştirmemeli; yeni yaşam olayı ile veri hatası düzeltmesi ayrı sınanmalıdır. Düzeltmede kaynak/audit geçmişi korunmalı, geçersizleşmiş bilgi güncel context veya eski onayla public projection'a geri dönmemelidir.
- Mood testlerinde yeni etki olmadığında karaktere özgü baseline'a yaklaşma, küçük/güçlü olayların farklı etki süreleri ve çevrimdışı zaman uyarlaması doğrulanmalıdır. Aynı olay/zaman aralığı tekrar işlendiğinde çift etki oluşmamalı; sakinleşme memory veya ilişki güvenini sıfırlamamalıdır.
- Memory testlerinde önemli deneyimin korunması, gündelik ayrıntının önceliğinin azalması ve ilgili eski kaydın konu yeniden açıldığında bulunabilmesi doğrulanmalıdır. Consolidation kaynak/gizlilik/iddia ayrımını korumalı; dayanağı olmayan ayrıntı gerçek memory'ye dönüşmemeli ve decay fiziksel silme yapmamalıdır.
- Kişilik testlerinde tekrarlı chat/reflection temel personality, temperament, ana değerler veya bunlardan türetilen baseline'ı otomatik değiştirmemelidir. Buna karşılık kaynak deneyime dayanan ilişki/görüş/goal değişimleri mümkün olmalı; kişiye özgü yakınlık genel kişilik dönüşümü olarak kaydedilmemelidir.
- Contributor A, contributor B'nin taslağını veya medyasını görememeli/değiştirememeli; aynı pooled bağlantının tekrar kullanımı kimlik sızdırmamalıdır. Anonymous/contributor private chat stream'ine erişememelidir.
- Yasak bilgi doğrudan memory'den veya türetilmiş reflection/summary/goal üzerinden alıcı context'ine girmemeli; ortak transcript içsel intent/affect alanlarını taşımamalıdır. Public projection ve medya yalnız onaylanan sürümü sunmalıdır.
- Bozuk JSON, geçersiz domain action, timeout ve retry sınırı deterministic hata/quarantine akışına gitmeli; başarısızlık uydurma başarılı sonuçla örtülmemelidir.
- Model benchmark'ında Türkçe karakter tutarlılığı, provenance koruma, retrieval başarısı, şema başarısı, ilk token/toplam gecikme ve uzun süreli kararlılık ölçülmelidir. Sayısal kabul eşikleri benchmark sonrası, MVP kabul değerlendirmesinden önce sürümlü eval planında sabitlenmelidir; yalnız şema geçmesi davranış kalitesi sayılmaz.
- Backup/restore ve recovery tatbikatı uygulanmalı; bu belgede testlerin tanımlanmış olması testlerin geçtiği anlamına gelmemelidir.

## Son İnceleme

**Durum:** `KABUL` — Teknik çapraz inceleme düzeltmeleri ve AK-001–AK-004 kararları işlendi; karar seti kullanıcının bütünsel gözden geçirmesine hazır.

**Tarih:** 2026-09-21

### Sistem invariant'ları

Aşağıdaki kurallar bütün modül ve fazlarda geçerlidir:

1. İnsan kullanıcılar arasında yalnız World Owner aktif AI karakterlerle konuşabilir; AI karakterler dünya kuralları içinde birbirleriyle konuşabilir.
2. Contributor yalnız taslak, başvuru ve revizyon önerir; canlı karakter state'ini doğrudan değiştiremez.
3. AI karakter yalnız gerçekten erişebildiği bilgi ve memory kapsamıyla hareket eder.
4. LLM kalıcı state'i, domain action'ı veya yayın kararını doğrudan uygulayamaz; yalnız yapılandırılmış öneri üretir.
5. Private/internal veri public projection'a otomatik olarak kopyalanmaz.
6. Public içerik ayrı moderasyon ve yayın akışından geçer; MVP'de insan onayı zorunludur.
7. Event geçmişi append-only, güncel okuma snapshot tabanlıdır; birlikte değişmeleri gereken kayıtlar transaction ile korunur.
8. Queue/job işleme idempotenttir; retry duplicate domain sonucu üretmez.
9. Browser'a secret/service credential verilmez; worker ve API ayrı minimum yetkili kimlikler kullanır.
10. Modelden gizli chain-of-thought istenmez veya saklanmaz; yalnız gerekli kısa gerekçe, sinyal ve yapılandırılmış karar verisi tutulur.
11. Autonomous üretim bütçe, cooldown, concurrency ve kill switch sınırları olmadan çalışmaz.
12. Maksimum aktif karakter sayısı yapılandırılabilir sistem limitiyle 50'yi aşamaz; limit değişikliği World Owner audit event'i üretir.
13. Bir işin kuyruğa alınması veya geçmişte onaylanması güncel çalışma yetkisi sayılmaz; state sürümü, lifecycle, iptal ve deneme sahipliği sonuç uygulamadan önce doğrulanır.
14. Bilgi dönüşümü erişim/paylaşım kapsamını kendiliğinden genişletemez; yayın onayı yalnız incelenen değiştirilemez içerik sürümü için geçerlidir.

### Tutarlılık düzeltmeleri

- Karakter başına günlük 2 katılım sınırıyla 3 karakter için autonomous scene hedefi 2–3/gün, 4–5 karakter için 2–4/gün olarak düzeltildi. 10–15/gün hedefi daha fazla aktif karakter bulunan ölçek aşamasındadır.
- Obsidian mirror yeni ürün modelinin MVP tamamlanma ölçütü için gerekli değildir ve sonraki faza alındı.
- Full hierarchical agency mimarisi korunurken MVP yalnız basit short-term goals ve önemli olay reflection'ı uygular.
- Modelin desteklediği teorik context uzunluğu kapasite kabul edilmez; gerçek VRAM ve scene benchmark'ı belirleyicidir.
- Public projection ile world-internal `world` görünürlüğünün farklı kavramlar olduğu teyit edildi.
- `internal` insan erişimi ile AI bilgi kapsamı ayrıldı; `secret` epistemik tür yerine ayrı hassasiyet niteliği olarak tanımlandı.
- Deployment diyagramındaki kesin Hermes adı kaldırıldı; model seçiminin benchmark'a bağlı olduğu korundu.
- VAD'nin mevcut MVP tercihi korundu; AK-004 mood alt kararıyla karaktere özgü baseline, zamana bağlı dönüş ve çevrimdışı süre davranışı kabul edildi. Sayısal aralık/katsayı/hızlar uygulama sırasında senaryo testleriyle kalibre edilecektir.
- Şema doğrulama, RLS, idempotency ve insan onayı ifadelerinin hangi transaction, kimlik, sürüm ve recovery kurallarıyla uygulanacağı ilgili bölümlere eklendi.

### Kullanıcıyla ele alınan ürün kararları

AK-001, AK-002, AK-003 ve AK-004 kullanıcıyla tek tek değerlendirilerek kabul edilmiştir. Bu dört başlık altında açık ürün davranışı kararı kalmamıştır. Aşağıdaki özet bütünsel gözden geçirme içindir; ertelenmiş model/sağlayıcı seçimleri ve sonraki faz özellikleri ayrıca listelenir. Karar onayı, uygulama veya testlerin tamamlandığı anlamına gelmez.

| Kimlik | Konu | Karar / açık kapsam | Bağlı bölümler / kararın gerekli olduğu aşama |
| --- | --- | --- | --- |
| AK-001 | World Owner'ın dünya içindeki kimliği ve sohbet etkisi — KABUL | Ayrı yönetici yetkileriyle kalıcı insan katılımcı; karaktere özgü memory ve insana yönelik ilişki; sohbet dünya içi deneyimdir, yönetici emri değildir. Özel sohbet bilgisi varsayılan olarak aralarında kalır; yalnız açık, bilgi/alıcı kapsamlı izinle başka karaktere aktarılabilir. | Aktörler, WADR-004/007/008/011; kimlik ve paylaşım davranışı kararlaştırıldı |
| AK-002 | Çevrimdışı zaman ve geri dönüş — KABUL | Dünya saati ilerler; AI etkileşimleri bekler. Dönüşte güncel konum/rutinler uzlaştırılır, eski sahne adayları yeniden değerlendirilir; gerçekleşmemiş konuşmalar geçmişte yaşanmış gibi üretilmez. Kalıcı mesaj/sonuçlar korunur; rutin işler birleştirilir. | WADR-004/005/011; çevrimdışı zaman ve geri dönüş davranışı kararlaştırıldı |
| AK-003 | Devam eden sahneye karşı admin sohbeti — KABUL | Mevcut turn tamamlanır, yeni turn başlatılmadan sahne kesintili olarak sonlandırılır; yaşanmış etkileşimin etkileri kaydedilir, sonra admin chat güncel state ile başlar. UI bekleme durumunu gösterir; yarım kalan konu ileride yeni sahnede ele alınabilir. | WADR-005/006/011; güvenli sonlandırma ve rezervasyon devri kararlaştırıldı |
| AK-004 | Karakter değişimi, mood ve hafıza davranışı — KABUL | Geçmiş korunur; yaşam değişiklikleri yeni olaylarla, hatalar onaylı düzeltmeyle ele alınır. Mood baseline'a yaklaşır; memory/güven ayrıdır. Önemli anılar korunur, gündelik ayrıntıların önceliği azalır; özetler kaynak/gizliliği korur. MVP'de temel kişilik ve ana değerler sabit; görüş/ilişki/goal gelişebilir. Yavaş temel kişilik gelişimi sonraki fazda, büyük dönüşümler Owner onaylıdır. | WADR-001/008/009/014; bütün alt kararlar tamamlandı |

Teknik doğrulama, erişim kısıtları ve eski sonuçları reddetme kuralları ürün kararlarının yerine geçmez. Admin GPU önceliği AK-003'teki güvenli turn/processing sınırına uyar. Durable queue, kabul edilen AK-002 politikasını uygular; geçmiş olayları koşulsuz oynatma yetkisi vermez.

### Teknik doğrulama kaynakları

Çapraz incelemede aşağıdaki resmî kaynaklar kullanılmıştır. Uygulama aşamasında seçilen sürümlere göre bağlantı/pooler, API ve yetkilendirme davranışları yeniden doğrulanacaktır.

- [PostgREST transaction ve request bağlamı](https://postgrest.org/en/latest/references/transactions.html): request claim'lerinin transaction kapsamında taşınması; doğrudan SQL bağlantısının ayrı bağlam gerektirmesinin dayanağı.
- [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html): tablo sahibi ve `BYPASSRLS` istisnaları; gerçek runtime rolleriyle test gereksinimi.
- [Supabase Queues / PGMQ](https://supabase.com/docs/guides/queues/pgmq): visibility süresi, yeniden teslim ve archive işlemleri; domain idempotency'nin uygulama sorumluluğu olması.
- [Supabase Realtime Authorization](https://supabase.com/docs/guides/realtime/authorization): private kanal izinleri ve bağlantı süresince yetki önbelleği.
- [Supabase Storage bucket erişimi](https://supabase.com/docs/guides/storage/buckets/fundamentals): private/public medya ayrımı ve public nesnelerin URL ile okunabilmesi.

### Ertelenmiş önemli kararlar

Uygulama başlamadan değil, ilgili milestone öncesinde sonuçlandırılacaktır:

| Karar | En geç ne zaman? | Karar ölçütü |
| --- | --- | --- |
| Ana LLM, quantization, runtime ve context | İlk gerçek admin chat/scene eval'ından önce | Türkçe kalite, schema başarısı, gecikme, VRAM, sıcaklık |
| Embedding modeli ve dimension | Memory migration'ı kesinleşmeden önce | Türkçe retrieval eval'ı, hız, RAM/VRAM, lisans |
| Cloud container ve web sağlayıcısı | Staging deployment öncesinde | Bölge, maliyet, cold start, container, secrets/logs |
| Otomatik moderasyon sağlayıcısı/modeli | Contributor başvuruları public açılmadan önce | İçerik politikası başarısı, gizlilik, maliyet, Türkçe |
| E-posta sağlayıcısı ve auth recovery | Contributor beta öncesinde | Teslimat, domain kurulumu, rate limit, maliyet |
| Hata izleme sağlayıcısı | Staging öncesinde | Redaction, retention, fiyat ve veri bölgesi |

### Ana riskler ve kontroller

| Risk | Etki | İlk kontrol |
| --- | --- | --- |
| Yerel AI makinesinin çevrimdışı olması | Chat/autonomy gecikir | Durable queue, heartbeat, UI durumu, güvenli resume |
| 8 GB VRAM ve laptop ısısı | Düşük throughput veya crash | Concurrency 1, benchmark, sıcaklık/VRAM telemetry, bütçe |
| Prompt injection içeren katkı | Karakter/world davranışı bozulur | Structured form, normalizasyon, template derleme, admin onayı |
| Karakterler arası bilgi sızıntısı | Dünya tutarlılığı ve gizlilik bozulur | Scope-first retrieval, provenance/shareability, negatif testler |
| Retry ile duplicate state | Çift memory/event/mesaj | Idempotency key, unique constraint, outbox, transaction |
| Public alana internal veri sızması | Gizlilik ihlali | Fiziksel projection, publisher allowlist, manuel yayın, RLS testleri |
| Küçük modelde karakter drift'i | Karakter kimliği zayıflar | Versioned definition, eval seti, memory bütçesi, reflection sınırları |
| Queue backlog büyümesi | Dünya geriden gelir | Adaptive scene üretimi, priority queue, oldest-job metriği |
| Maliyet/kapsam büyümesi | MVP tamamlanmaz | 3–5 karakter, iki kişilik scene, manuel yayın, ertelenen özellik listesi |

### Uygulama sırası

1. **Foundation:** Monorepo, CI, local Supabase, FastAPI/Next.js iskeleti, config/secrets ve temel health kontrolleri.
2. **Identity & contribution:** Auth, roller, RLS, contributor taslağı/başvurusu/revizyonu ve admin inceleme akışı.
3. **Character activation:** Sürümlü definition, prompt compilation sınırı, moderasyon kaydı ve lifecycle.
4. **AI transport:** Queue/outbox, worker heartbeat, LLM provider fake adapter, Admin chat ve Realtime streaming fallback.
5. **World vertical slice:** World clock, konum/presence, iki karakterli scene lifecycle ve deterministic candidate selection.
6. **Cognitive state:** Scoped memory, embedding/retrieval, affect, yönlü relationship ve basit goals/reflection.
7. **Publishing:** Güvenli summary adayı, manuel moderation, public projection ve World Viewer.
8. **Hardening:** RLS/adversarial testler, idempotency/recovery, load/eval benchmark, backup/restore tatbikatı ve staging.

Her aşama fake/deterministic model adapter'ıyla test edilebilir olmalıdır. Gerçek model seçimi domain ve ürün akışının geliştirilmesini bloke etmemelidir.

## Değişiklik Geçmişi

| Tarih | Değişiklik |
| --- | --- |
| 2026-09-21 | Ortak AI dünyası ürün modeli tanımlandı; WADR-001 katkı ve onay modeliyle kabul edildi; WADR-002 tartışmaya açıldı. |
| 2026-09-21 | WADR-002 küratörlü public World Viewer ve katmanlı görünürlük modeliyle kabul edildi; WADR-003 tartışmaya açıldı. |
| 2026-09-21 | WADR-003 yapılandırılmış form, kontrollü yaratıcı alanlar ve World Owner onayıyla kabul edildi; WADR-004 tartışmaya açıldı. |
| 2026-09-21 | WADR-004 merkezî dünya saati, ayrık konumlar ve scene tabanlı event-driven simülasyonla kabul edildi; WADR-005 tartışmaya açıldı. |
| 2026-09-21 | WADR-005 kurallı aday üretimi, puanlama, sınırlı director ve katmanlı bütçelerle kabul edildi; WADR-006 tartışmaya açıldı. |
| 2026-09-21 | WADR-006 karaktere özel context kullanan sınırlı turn-based scene engine olarak kabul edildi; WADR-007 tartışmaya açıldı. |
| 2026-09-21 | WADR-007 objektif bağlar, yönlü çok boyutlu state ve append-only relationship geçmişiyle kabul edildi; WADR-008 tartışmaya açıldı. |
| 2026-09-21 | WADR-008 kapsam, provenance, confidence ve shareability taşıyan epistemik memory modeliyle kabul edildi; WADR-009 tartışmaya açıldı. |
| 2026-09-21 | WADR-009 sınırlandırılmış agency, hiyerarşik goals ve event-driven reflection ile kabul edildi; WADR-010 tartışmaya açıldı. |
| 2026-09-21 | WADR-010 katmanlı moderasyon ve explicit olmayan olgun içerik politikasıyla kabul edildi; WADR-011 tartışmaya açıldı. |
| 2026-09-21 | WADR-011 cloud control plane, yerel AI plane ve provider-neutral stack ile kabul edildi; LLM/embedding ve cloud sağlayıcısı ertelendi, WADR-012 tartışmaya açıldı. |
| 2026-09-21 | WADR-012 ilişkisel çekirdek, erişim şemaları, event standartları ve ölçüme dayalı optimizasyonla kabul edildi; WADR-013 tartışmaya açıldı. |
| 2026-09-21 | WADR-013 yapılandırılmış monorepo, modüler monolith ve üretilmiş API sözleşmeleriyle kabul edildi; WADR-014 tartışmaya açıldı. |
| 2026-09-21 | WADR-014 3–5 karakterle başlayan uçtan uca dikey MVP olarak kabul edildi; karar seti son incelemeye alındı. |
| 2026-09-21 | Son inceleme tamamlandı; MVP scene bütçesi düzeltildi, invariant'lar, ertelenmiş kararlar, riskler ve sekiz aşamalı uygulama sırası eklendi. |
| 2026-09-21 | Ayrıntılı çapraz inceleme sonrası teknik yetki, bilgi gizliliği, sürüm/onay, concurrency, queue recovery, streaming ve MVP kabul kuralları netleştirildi. Sahne kotası ve terim tutarsızlıkları düzeltildi. Son inceleme yeniden açıldı; kullanıcıyla sonuçlandırılacak AK-001–AK-004 açık kararları kaydedildi. Yalnız karar belgesi güncellendi; uygulama kodu oluşturulmadı. |
| 2026-09-21 | AK-001 kapsamında World Owner'ın karakterlerle ilişki kuran dünya içi insan katılımcı olması kabul edildi; yönetici yetkisi, karaktere özgü memory ve insana yönelik ilişki ayrımı işlendi. Sohbet bilgisinin diğer karakterlerle paylaşılma varsayılanı açık bırakıldı. |
| 2026-09-21 | Özel sohbet bilgisinin varsayılan olarak World Owner ile ilgili karakter arasında kalması ve diğer karakterlere yalnız açık izinle paylaşılması kabul edildi. AK-001 tamamlandı; açık ürün kararı sayısı üçe indi. |
| 2026-09-21 | AK-002 kabul edildi: çevrimdışıyken dünya saati ilerler, AI etkileşimleri bekler; geri dönüşte güncel rutin/konumlar uzlaştırılır ve eski adaylar değerlendirilir. Gerçekleşmemiş geçmiş konuşmalar üretilmez. Açık ürün kararı sayısı ikiye indi. |
| 2026-09-21 | AK-003 kabul edildi: admin mesajında mevcut turn tamamlanır, sahne güvenli biçimde sonlandırılır ve etkileri kaydedildikten sonra chat başlar. Bekleme/hata görünürlüğü ve sonraki sahnede devam sınırı işlendi. Yalnız AK-004 açık kaldı. |
| 2026-09-21 | AK-004 geçmiş/revizyon alt kararı kabul edildi: yaşanmış geçmiş korunur, anlamlı yaşam değişiklikleri yeni olaylarla gerçekleşir; gerçek hatalar World Owner onaylı, etkileri incelenmiş ve audit kayıtlı düzeltmeyle ele alınır. Mood, hafıza ve deneyimlerle kişilik gelişimi alt kararları açık kaldı. |
| 2026-09-21 | AK-004 mood alt kararı kabul edildi: olaylarla değişen ruh hâli, çevrimdışı süre dahil zamanla karaktere özgü baseline'a yaklaşır; güçlü etkiler daha uzun sürebilir, hafıza ve ilişki state'i ayrı kalır. Sayısal kalibrasyon testlere bırakıldı; hafıza ve kişilik gelişimi alt kararları açık kaldı. |
| 2026-09-21 | AK-004 hafıza alt kararı kabul edildi: önemli deneyimler korunur; gündelik ayrıntıların retrieval önceliği zamanla azalır. Unutma fiziksel silme değildir; ilgili eski anılar tekrar hatırlanabilir, özetler kaynak ve gizliliği korur, eksik ayrıntılar uydurulmaz. Yalnız kişilik gelişimi alt kararı açık kaldı. |
| 2026-09-21 | AK-004 kişilik alt kararı kabul edildi: MVP'de temel kişilik/ana değerler sabit, görüş/ilişki/goal gelişimi mümkündür. Yavaş temel kişilik gelişimi sonraki fazdadır; büyük dönüşümler World Owner onayı gerektirir. AK-001–AK-004 tamamlandı; karar seti bütünsel kullanıcı incelemesine hazırlandı. Kodlama başlatılmadı. |
