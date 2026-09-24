# CCE — Implementation Aksiyon Planı

**Hazırlanma tarihi:** 2026-09-22

**Planlanan başlangıç:** 2026-09-23 (`Europe/Istanbul`)

**Durum:** M1 ve M2.1 tamamlandı. M2 inceleme/feedback/revizyon ve private avatar dilimleri uygulandı; son birleşik CI ve iki oturumlu tarayıcı doğrulaması bekleniyor. Bu kanıt gelmeden M2 kapatılmadı.

**Mimari kaynak:** [WORLD_ARCHITECTURE_DECISIONS.md](WORLD_ARCHITECTURE_DECISIONS.md), uygulama başlangıcındaki son mimari commit `bb34875`.

## Hedef ve kullanım

İlk hedef, 3 aktif karakterle contributor başvurusundan private admin chat'e, iki karakterli scene'e ve manuel onaylı public özete kadar çalışan bir MVP'dir. Bu akış doğrulandıktan sonra test dünyası 4–5 karaktere çıkarılır. Mimari en fazla 50 aktif karakter sınırını korur; başlangıçta 50 karakter işletmek hedef değildir.

Bu plan mimari kararları iş sırasına dönüştürür. Davranışın source of truth'u WADR belgesidir. Bir uygulama tercihi kabul edilmiş davranışı değiştiriyorsa önce ilgili karar güncellenir. İş kutuları, kod ve belirtilen doğrulama kanıtı tamamlanınca işaretlenir; dokümanda yazılı olmaları tamamlandıkları anlamına gelmez.

Her aşama küçük, gözden geçirilebilir commitlerle ilerler. Migration, ilgili backend kuralı ve o kuralın integration testi birlikte ele alınır. Kullanıcıya açılan her akışın UI, API, yetki, hata ve recovery davranışı aynı aşamada tamamlanır. Aşamalar günlük süre taahhüdü değildir; sonraki aşamaya geçiş çıkış koşuluna bağlıdır.

## İlk çalışma oturumu

İlk günün hedefi M1'dir: temiz checkout'tan kurulabilen, yerel veritabanına bağlanan API, basit web ekranı ve çalışan CI. GPU veya gerçek model ilk günü bloke etmez.

1. `main` ve çalışma ağacını kontrol et; bu plan ile WADR-011/012/013'ü aç. Geliştirme makinesinde Git, Docker, Python, Node, `uv`, `pnpm` ve Supabase CLI kullanılabilirliğini doğrula. GPU makinesine erişimi ayrıca not et; geliştirme ortamıyla aynı makine olduğunu varsayma.
2. **M1.1–M1.2:** Kullanılacak araç sürümlerini uyum kontrolünden sonra sabitle; yalnız ilk özellik için gereken repo iskeletini ve bağımlılık dosyalarını oluştur.
3. **M1.3:** Yerel Supabase'i başlat, ilk migration ile şema/rol temelini kur ve API'nin minimum yetkili bağlantısını doğrula. Gerçek cloud verisini seed/reset hedefi yapma.
4. **M1.4–M1.5:** API health/readiness, web health ekranı, yapılandırma ve temel testleri çalıştır. Model çağrısı veya contributor yetkileri hazırmış gibi davranan ekranlar ekleme.
5. **M1.6:** Aynı kontrolleri CI'da çalıştır; temiz kurulum adımlarını README'ye yaz ve M1 çıkış koşulunu doğrula. Güne sığmazsa kalan M1 işlerini açık bırak; M2'ye geçmek için sırf takvim nedeniyle tamamlandı işaretleme.

İlk commit grupları: repo/bağımlılık temeli; yerel veri tabanı ve health akışı; CI ve kurulum belgesi. Oturum sonunda çalışan komutları, test sonucunu ve sıradaki açık iş kimliğini kısa bir ilerleme notuna yaz.

## Aşamalar ve bağımlılıklar

| Aşama | Ön koşul | Somut çıktı | İlgili kararlar |
| --- | --- | --- | --- |
| M1 — Foundation | Yok | Yerel web/API/DB ve CI | WADR-011/012/013 |
| M2 — Kimlik ve katkı | M1 | İzole kullanıcılar, başvuru/revizyon ve inceleme UI'ı | WADR-001/002/003/010/011/012 |
| M3 — Aktivasyon ve lifecycle | M2 | Sürümlü karakter, moderasyon kapısı, askı/arşiv/restore | WADR-001/003/009/010/012 |
| M4 — İş altyapısı ve admin chat | M3 | Durable işler, atomik sonuç protokolü, private streaming chat | WADR-005/006/008/011/012 |
| M5 — Dünya ve scene | M4 | Saat/presence, aday seçimi, iki karakterli scene, AK-002/003 | WADR-004/005/006/009 |
| M6 — Bilişsel state ve gerçek model | M5; model/embedding kararları ilgili entegrasyon öncesinde | Yetkili retrieval, memory/mood/relationship/goal/reflection | WADR-007/008/009/011 |
| M7 — Public yayın | M6 | Onaylı projection'lar ve World Viewer | WADR-002/007/010/012/014 |
| M8 — Kabul ve staging | M7; staging sağlayıcı kararları | Recovery/eval/restore kanıtları ve 3–5 karakterli pilot | WADR-011/013/014 |

M6, bilişsel işlemlerin tamamlanma aşamasıdır. Chat/scene'in doğru state ile çalışmasını sağlayan minimum memory/affect/relationship kayıtları ve sonuç protokolü M3–M4'te kurulur. Retrieval, consolidation ve gerçek model kalitesi daha sonra bu temelin üzerine gelir. Geçici test sağlayıcısı, production'da her şeyi sıfır değişimle başarılı sayan bir fallback olmaz.

## M1 — Foundation

**Hedef:** Uygulamanın temiz ortamda kurulması ve tek bir health akışının web → API → DB boyunca çalışması.

- [x] **M1.1 — Araç ve sürümler:** WADR'deki teknoloji seçimlerini koruyarak Python 3.12+ ailesinden desteklenen bir sürüm, Node ve paket yöneticilerini sabitle. Paket sürümlerini implementation sırasında resmî uyumluluk belgelerinden doğrula; lockfile'ları commit et.
- [x] **M1.2 — Minimum repo:** `apps/web`, `services/backend`, `supabase` ve gereken CI/config dosyalarını oluştur. Python paketi `services/backend/src/cce` altında olsun. Henüz kullanılmayan bütün domain modüllerini veya boş adapter klasörlerini topluca üretme.
- [x] **M1.3 — DB temeli:** Supabase CLI SQL migration hattını, `public`/`world_private`/`ops_private` sınırlarını ve migration/API/worker rol ayrımını kur. Yerel geliştirme fixture'larını açıkça test ortamıyla sınırla; uygulama migration sahibiyle bağlanmasın.
- [x] **M1.4 — Çalışan iskelet:** FastAPI liveness/readiness, web health görünümü, validated config ve correlation kimlikli hassas veri içermeyen logları ekle. Test edilebilir `world_clock` arayüzünü oluştur; tam dünya simülasyonu M5'te gelecek.
- [x] **M1.5 — Geliştirme akışı:** `.env.example`, `.gitignore`, README kurulum/çalıştırma adımları ve yerel servis başlatma düzenini ekle. Secret veya gerçek kullanıcı verisi repoya girmesin.
- [x] **M1.6 — CI:** Backend lint/typecheck/test, frontend lint/typecheck/test/build ve mevcut migration kontrollerini kur. Kod eklendikçe container build, contract ve gerçek rol testleri aynı pipeline'a dahil edilsin. Production deploy otomatikleşmesin.

**Çıkış kanıtı:** Temiz checkout ve boş, yalnız teste ayrılmış yerel DB üzerinde kurulum tekrarlanır; migration, health akışı, lint/typecheck ve build geçer. DB erişilemezken readiness uygun hata verir. README komutları fiilen denenmiştir.

## M2 — Kimlik, katkı ve inceleme

**Hedef:** Contributor yalnız kendi taslak/başvurusunu görür; World Owner güvenilir komutlarla inceleme yapar.

- [x] **M2.1 — Kimlik:** Supabase Auth giriş/kayıt ve SSR oturum akışını kur. World Owner bootstrap'ını güvenilir, audit edilen yönetim yoluyla yap; kullanıcı metadata'sı rol yükseltemesin. Yönetici hesabına bağlı kalıcı dünya içi insan kimliğini ayrıca modelle.
- [ ] **M2.2 — Yetki sözleşmesi:** JWT doğrulama, actor bağlamının transaction ile sınırlandırılması, rol/grant/RLS ve Data API yazma sınırlarını uygula. SQLAlchemy havuzunda actor bilgisinin istekler arasında taşınmadığını doğrula.
- [ ] **M2.3 — Başvuru modeli:** Taslak, değiştirilemez gönderilmiş revizyon, feedback ve audit migration'larını ekle. `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `CHANGES_REQUESTED`, `REJECTED`, `APPROVED`, `WITHDRAWN` davranışlarını başvuruya ait tut; canlı karakter lifecycle'ıyla tek enum'da birleştirme.
- [ ] **M2.4 — Katkı UI/API:** Yapılandırılmış form, ön izleme, gönderim, revizyon, geri çekme ve durum ekranını yap. OpenAPI'den TypeScript client üret; Zod yalnız form UX doğrulaması için kullanılsın. Eşzamanlı geri çekme/onay işlemlerinde yalnız tek geçerli geçiş commit edilsin.
- [ ] **M2.5 — İnceleme UI/API:** World Owner için sürüm farkı, gerekçeli ret/değişiklik talebi ve moderasyon sonucunu göster. Moderasyon adapter'ını test fixture'larıyla kur; gerçek aktivasyon kapısı M3'tedir.
- [ ] **M2.6 — Medya:** Avatar önerilerini private Storage alanında sahiplik kontrollü yükle; boyut/içerik türü/format kontrollerini uygula. Onay için referanslanan medya sürümü değiştirilemesin. Contributor başvuru/yükleme limitlerini ekle.

**Çıkış kanıtı:** İki contributor ile ayrı oturumlarda taslak/medya izolasyonu; anonymous ve doğrudan Data API/SQL erişim denemeleri; pooled bağlantının A → B → kimliksiz kullanımı sınanır. Geri çekilen başvuru canlı state yaratmaz ve tekrar açılmaz. Moderasyon fixture'ı kullanılan akış yerel/test ortamı olarak görünürdür.

## M3 — Karakter aktivasyonu ve lifecycle

**Hedef:** Yalnız doğru sürümü onaylanmış karakter atomik ve denetlenebilir biçimde aktive edilir.

- [ ] **M3.1 — Definition:** Sürümlü karakter tanımı, schema version, onay referansı ve prompt template derlemesini kur. Serbest metni system prompt olarak kullanma. Core memory ve başlangıç goal/affect adaylarını türet; türetmenin onaylı kaynakla ilişkisini kaydet.
- [ ] **M3.2 — Moderasyon kapısı:** `PASS`, olumlu/olumsuz `REVIEW`, `BLOCK` ve tarama hatasını ayır. Owner'ın kendi karakterleri de aynı hattan geçsin. `BLOCK` override edilemesin; düzeltilmiş yeni sürüm yeniden taransın. Gerçek içerik aktive edilmeden gerçek tarama entegrasyonu hazır olmalı.
- [ ] **M3.3 — Aktivasyon transaction'ı:** Karakter kimliği, aktif definition, minimum core memory/affect/goal ve gerekli başlangıç ilişkilerini tutarlı oluştur. Eşzamanlı aktivasyonlar yapılandırılmış aktif karakter sınırını aşamasın; limit 50'nin üzerinde olamasın. Başlangıçta vector dimension seçmek gerekmez.
- [ ] **M3.4 — Lifecycle:** `ACTIVE`, `SUSPENDED`, `ARCHIVED`, özel `ARCHIVED → SUSPENDED` restore ve ayrı yeniden aktivasyon komutlarını ekle. Actor/gerekçe audit'i, aynı kimliğin korunması ve güncel moderasyon/kapasite kontrollerini uygula. İş iptal sınırını M4'ün iş protokolüne bağla.
- [ ] **M3.5 — Değişiklik:** Onaylı definition revizyonu ile gerçek veri düzeltmesini ayır. Geçmişi yeniden yazmayan correction/superseding kayıtlarını kur; etkilenen türetilmiş kayıtları uzlaştırma işlerini tanımla. MVP'de temel kişilik, core drives ve baseline'ı normal revizyonla değiştirmenin önünü kapat.
- [ ] **M3.6 — Admin oluşturma/görünüm:** Owner'ın karakter oluşturmasını M2'deki yapılandırılmış form ve aynı doğrulama hattına bağla; kendi onayını gerçek actor ile audit et. Definition/sürüm, moderation, lifecycle ve audit sonucunu göster. Restore eski işler veya kaldırılmış yayınlar için otomatik yeniden başlatma üretmesin.

**Çıkış kanıtı:** Aynı onayın retry'ı duplicate karakter yaratmaz; eski sürüm onayı yeni içeriği aktive etmez; `BLOCK`/olumsuz `REVIEW` engeller. Askı/restore kimliği ve korunmuş geçmişi tutar. Eşzamanlı son kapasiteyi alma yarışı ve yetkisiz lifecycle komutları test edilir. Aktif karakter limiti doluyken hem `APPROVED → ACTIVE` hem `SUSPENDED → ACTIVE` reddedilir, ret World Owner UI'ında görünür kalır; limit değişikliği audit event üretir.

## M4 — İş altyapısı ve private admin chat

**Hedef:** AI işlerinin güvenilir yürütülmesi ve fake provider ile uçtan uca, doğru state sınırlarına sahip private chat.

- [ ] **M4.1 — Önce ortak protokol:** Kalıcı etkileşim rezervasyonu, worker lease/sahiplik nesli, domain etki tekilleştirmesi, atomik sonuç transaction'ı, job runs ve outbox'ı kur. Model/processing sürümü etki kimliğini değiştirmesin. Lease bitmesi karakteri müsait yapmasın.
- [ ] **M4.2 — Queue/worker:** `JobQueue` adapter'ı, Supabase Queues tüketimi, heartbeat, bounded retry/backoff, quarantine ve recovery taramasını kur. Sonuç commit edilmeden mesajı onaylama. CPU/GPU/publisher/maintenance rollerinin minimum yetkilerini migration'da tanımla.
- [ ] **M4.3 — Model sınırı:** `LLMProvider` ve deterministic fake implementasyonu, yapılandırılmış çıktı doğrulaması, token/süre/deneme bütçesi ve hata fixture'larını ekle. Ana LLM için AI plane genelinde concurrency 1 uygula; alt iş bekleyen parent GPU slotunu bırakabilsin.
- [ ] **M4.4 — Minimum gerçek processing hattı:** Kaynak kimliğine bağlı memory/affect/relationship/goal adaylarını doğrulayıp atomik uygulayan handler'ları kur. En az bir sıfır değişim ve bir gerçek state değişimi fixture'ıyla DB etkisini kanıtla. Henüz hazır olmayan bilişsel özellik için production'da sessiz başarı/no-op dönme.
- [ ] **M4.5 — Kabul ve teslim:** Admin mesajını idempotent kabul et; karaktere teslimi ayrı transaction'da `delivered_at` ve processing outbox ile kaydet. Gelen mesajın etkileri tamamlanmadan yanıt başlatma. Mesajları karakter bazlı kalıcı sıraya koy; aktif yanıtın girdi sınırını sabitle.
- [ ] **M4.6 — Yanıt ve stream:** Private Realtime kanalını, yalnız yetkili yanıt token'larını, `attempt_id`/sequence kontrolünü ve final mesaj commit'ini uygula. Gelen mesaj ile final yanıt etkileri ayrı tekilleştirilsin. Yeniden bağlantı ve Realtime arızasında API/job polling çalışsın.
- [ ] **M4.7 — Operasyon UI'ı:** Kabul, teslim, yanıt üretimi ve processing durumlarını ayrı göster. Worker offline, bekleyen iş, hata/quarantine, uygun manuel retry ve kill switch kontrollerini ekle. Retry yetkisi güncel actor/lifecycle doğrulamasından geçsin.

**Çıkış kanıtı:** Commit öncesi/sonrası crash, duplicate teslim, lease kaybı, geç worker sonucu ve processing sürümü değişiminde duplicate etki oluşmaz. Teslim öncesi iptal deneyim yaratmaz; teslim sonrası yanıt hatası gelen mesajın etkisini kaybettirmez. LLM isteyen alt processing işi GPU concurrency 1 altında kilitlenmez. Contributor/anonymous private stream'e erişemez; oturum/yetki iptali kontrol edilir.

## M5 — Dünya, planlama ve iki karakterli scene

**Hedef:** Geçerli tetikleyiciden başlayan, sınırlandırılmış ve sonuçları tutarlı uygulanan ilk autonomous scene.

- [ ] **M5.1 — Saat ve presence:** Merkezi `world_clock`, konumlar, zaman blokları ve esnek rutinleri kur. Operasyon timeout/lease saatini dünya saatinden ayır. Çevrimdışı dönüşte presence/rutinleri güncele uzlaştır; geçmiş diyalog üretme.
- [ ] **M5.2 — Aday ve bütçe:** Konum/kanal, lifecycle, müsaitlik, cooldown ve kaynak filtrelerini; açıklanabilir puan, fairness ve dünya/karakter/scene/worker bütçelerini uygula. Başlangıç konfigürasyonu WADR-005'teki 3 karakter için 2–3, 4–5 karakter için 2–4 scene/gün hedefini ve karakter başına en fazla 2 katılımı izlesin.
- [ ] **M5.3 — Sınırlı director:** Önce deterministik aday yolunu doğrula; ardından yalnız daraltılmış geçerli adaylar için provider adapter'ına bağlı sınırlı öneri adımını ekle. Backend son doğrulamayı ve başlatma yetkisini korusun; gelişmiş director ekleme.
- [ ] **M5.4 — Scene Controller:** WADR-006 geçiş tablosunu, karaktere özel context'i, tek karakter/tek turn çıktısını, commit edilmiş ortak transcript'i ve turn/token/idle sınırlarını uygula. `send_in_world_message` aynı engine'de uzaktan iletişim scene talebi olsun.
- [ ] **M5.5 — Sonuç ve recovery:** M4 protokolünü bütün katılımcı etkilerine tek transaction olarak uygula. `CANCELLED`, `INTERRUPTED`, `RESOLVED`, `FAILED` ve normal completion ayrımını koru. `RUNNING` kaynaklı commit edilmiş prefix'in recovery'si `RESOLVED` olur; `failed_from` ve sabit transcript sınırına göre recovery yap. Terminal kesintili veya çözülmüş scene'in processing retry'ı yeni turn açmasın.
- [ ] **M5.6 — Admin kesintisi:** AK-003 durma isteği, mevcut geçerli turn'ün bitişi, sonraki turn yasağı ve chat'e rezervasyon devrini atomik koordine et. Askı/arşiv/güvenlik durdurması halinde daha kısıtlayıcı commit kontrolü uygulansın.
- [ ] **M5.7 — Dünya UI'ı:** Dahili scene/transcript, katılımcı durumu, bütçe, kesinti nedeni ve processing sonucunu göster. Yeni state'e uygunluk yalnız scene terminal durumundan türetilmesin.

**Çıkış kanıtı:** İki karakter sahnesi fake provider ile tamamlanır ve iki katılımcının etkileri birlikte görünür. Admin mesajı turn üretimi/sınırı/processing sırasında denenir. Sıfır commit iptali, üç ayrı `FAILED` recovery yolu ve kesintili processing retry'ı doğrulanır. World Owner/güvenlik kesintisinde hiç turn commit edilmemişse `CANCELLED`, en az bir turn commit edilmişse `INTERRUPTED` sonucu doğrulanır; tek turn doğrulama hatası retry sınırına ulaştığında scene `FAILED` olur. Gece–öğlen ve çok günlük offline senaryoları geçmiş deneyim veya kota üretmez.

## M6 — Bilişsel state ve gerçek model entegrasyonu

**Hedef:** Karaktere özgü bilgi sınırları ve gerçek deneyime dayalı bilişsel değişim; ölçülmüş model davranışı.

- [ ] **M6.1 — Model kararı ve adapter:** Hedef GPU makinesinde ana LLM/runtime/quantization/context benchmark'ını yap; seçimi ve ölçümleri kaydet. Gerçek adapter'ı M4 sözleşmesine bağla. Fake sağlayıcıyla geçen testleri gerçek model davranışının kanıtı sayma.
- [ ] **M6.2 — Memory şeması ve retrieval:** Core/episodic/semantic sınıfını, epistemik türü, kapsam/paylaşım/sır niteliğini ve provenance'ı ayrı tut. Embedding modeli/dimension kararını vector migration'ından önce tamamla. Önce exact search; embedding bekleyen canonical memory için recent-memory yolu çalışsın.
- [ ] **M6.3 — Bilgi izolasyonu:** Context builder'da memory yanında definition, transcript, summary, goal ve reflection'ı alıcıya göre filtrele. `world_owner_only`, AK-001 kaynak mesaja bağlı bilgi/alıcı izinleri ve iç işleme ayrımını uygula; başka karakterin private kaydı retrieval adayı dahi olmasın.
- [ ] **M6.4 — Affect/social/agency:** Karaktere özgü VAD baseline, dünya zamanına bağlı decay, yönlü ilişki snapshot/event ve sınırlı short-term goal değişimlerini tamamla. World Owner insan kimliği için yalnız AI → insan yönünü üret. Backend delta ve sürüm kontrollerini koru.
- [ ] **M6.5 — Reflection/consolidation:** Önemli scene sonrası reflection ve temel semantic consolidation'ı kaynak sınırlı işler olarak ekle. Çelişkili iddiaları koru; tekrar claim'i fact yapmasın. Unutma fiziksel silme olmasın; temel kişilik/core drives sabit kalsın.
- [ ] **M6.6 — Eval ve kalibrasyon:** Türkçe tutarlılık, kaynak koruma, retrieval, JSON başarısı, ilk token/toplam süre, VRAM ve uzun çalışma kararlılığını ölç. Bütçe ve delta/decay parametrelerini sürümle; MVP kabul eşiklerini nihai kabulden önce eval planında sabitle.

**Çıkış kanıtı:** Gizli bilginin doğrudan ve türetilmiş context üzerinden sızmadığı deterministic testlerle gösterilir; gerçek LLM adversarial eval'ları ayrıca raporlanır. Aynı olay/zaman aralığı çift işlenmez. Duygusal sakinleşme memory veya güveni sıfırlamaz; önemli eski anı ilgili konuda yeniden bulunabilir. Gerçek chat/scene güncel, yetkili state ile çalışır.

## M7 — Public yayın ve World Viewer

**Hedef:** Yalnız incelenmiş içerik sürümlerinden oluşan, private state'ten ayrı public ürün.

- [ ] **M7.1 — Yayın adayı:** Internal scene'den güvenli özet adayı üret; kaynak referansı, değiştirilemez içerik/medya sürümü ve hash ile kaydet. Private Owner konuşması, private intent/affect/reflection veya yasak memory'yi yayın kaynağına katma.
- [ ] **M7.2 — Onay ve publisher:** Otomatik moderasyon ve manuel Owner onayını aynı aday sürümüne bağla. Publisher commit sırasında kaynak uygunluğu, hash, onay ve geri çekme durumunu doğrulasın; yayın sırasında yeniden üretim yapmasın.
- [ ] **M7.3 — Projection/UI:** Public karakter profili, konum, güvenli ilişki açıklaması ve timeline için fiziksel projection tablolarını ve RLS okumalarını kur. Ham mood/relationship sayıları açılmasın; contributor kredisi yalnız açık tercih varsa gösterilsin.
- [ ] **M7.4 — Medya ve kaldırma:** Onaylı medya sürümünü yayınla; yayından kaldırmada projection, yönetilen medya erişimi ve uygulama cache'ini birlikte ele al. Geç publisher retry'ı kaldırılan içeriği geri getirmesin.

**Çıkış kanıtı:** Aday onaydan sonra değiştiğinde yayın reddedilir; tam onaylı sürüm yayınlanır. Anonymous yalnız projection görür. Geri çekme/yayın retry yarışı, private medyaya erişim ve cache sonrası kaldırma test edilir. Contributor → aktivasyon → chat → scene → public özet akışı uçtan uca gösterilebilir.

## M8 — Kabul, staging ve pilot

**Hedef:** Ölçülmüş ve kurtarılabilir bir MVP; yerel başarının ötesinde staging kanıtı.

- [ ] **M8.1 — Kabul matrisi:** WADR-014'teki her kabul maddesini en az bir test/eval/runbook kanıtına bağla. M2–M7'de yazılmış testleri birleştir; eksik olanları tamamla. RLS ve recovery testlerini bu aşamaya kadar ertelemiş olma.
- [ ] **M8.2 — Dağıtım:** Seçilmiş cloud web/API sağlayıcısı, Supabase ortamları, container'lar, minimum yetkili secret'lar, gerçek Realtime/Storage ve yerel worker'ın dışarı bağlantısını staging'de doğrula. Migration/deploy için manuel production kapısını koru.
- [ ] **M8.3 — Hesap operasyonları:** Contributor beta öncesi e-posta teslimi ve auth recovery'yi gerçek sağlayıcıyla test et. Hata izleme kullanılacaksa redaction'ı doğrula; provider kararı opsiyonel kullanmama yönündeyse gerekçesiyle kaydet.
- [ ] **M8.4 — Recovery tatbikatı:** Worker/network kesintisi, lease kaybı, quarantine/manuel retry, deploy sırasında eski deneme, DB backup/restore ve medya referanslarının bütünlüğünü dene. Runbook'lar güvenli işlem hedefini, beklenen sonucu ve geri dönüş yolunu içersin.
- [ ] **M8.5 — Yük ve işletim:** Önce 3 karakterle günlük döngüyü çalıştır; scene sayısı yanında toplam AI token/süre/retry, queue yaşı ve GPU/ısıl kararlılığı izle. Kabul koşulları sağlandıktan sonra 4–5 karaktere çık; 20–50 karakteri pilot kapsamına ekleme.
- [ ] **M8.6 — Yayın kararı:** Açık hata/quarantine, zorunlu test/eval sonucu, backup/restore kanıtı ve sağlayıcı kararlarını gözden geçir. Production'da fake adapter ve test seed'lerinin etkinleşemediğini doğrula. Kabul kaydı tamamlandıktan sonra manuel production yayın adımını uygula.

**Çıkış kanıtı:** WADR-014 kabul matrisi tamamdır; test/eval sonuçları, staging uçtan uca akışı ve recovery/restore raporu kayıtlıdır. Altı ertelenmiş teknik karar ilgili kapıda sonuçlanmıştır. Başarısız işleri gizleyen veya sahte başarıyla ilerleyen fallback yoktur.

## Teknik karar kapıları

| Karar | Plan içindeki son tarih | Beklenen kayıt |
| --- | --- | --- |
| Ana LLM/runtime/quantization/context | M6.1; ilk gerçek chat/scene eval'ından önce | Hedef donanımdaki ölçümler ve adapter uyumu |
| Embedding modeli ve dimension | M6.2 vector migration'ından önce | Türkçe retrieval eval'ı, dimension, kaynak maliyeti |
| Cloud web/API sağlayıcısı | M8.2 staging deployment öncesi | Container, bölge/gecikme, secret/log ve maliyet değerlendirmesi |
| Otomatik moderasyon sağlayıcısı/modeli | M3.2 gerçek içerik aktivasyonundan önce; her durumda contributor public açılışından önce | Türkçe politika testleri ve PASS/REVIEW/BLOCK davranışı |
| E-posta sağlayıcısı ve auth recovery | M8.3; contributor beta öncesi | Teslimat ve hesap kurtarma testi |
| Hata izleme sağlayıcısı veya kullanmama kararı | M8 staging açılışından önce | Redaction/retention ve operasyonel görünürlük kararı |

Geliştirme için fake model/moderasyon sonuçları yalnız açıkça ayrılmış test ortamlarında kullanılabilir. Kararların ertelenmiş olması gerçek kullanıcı içeriğinde doğrulama atlama yetkisi değildir. Henüz seçilmemiş model/sağlayıcı bu planla seçilmiş sayılmaz.

## Test kanıtlarının yerleşimi

| Kanıt | İlk kurulacağı aşama | Son doğrulama |
| --- | --- | --- |
| Migration, gerçek rol/grant/RLS, bağlantı bağlamı | M1–M2 | M8 staging |
| Başvuru yarışı, sürüm/onay, moderasyon, lifecycle/restore | M2–M3 | M8 kabul matrisi |
| Job idempotency, crash, lease, rezervasyon, GPU bağımlılığı | M4 | M5 scene ve M8 recovery |
| Mesaj kabul/teslim/yanıt, private stream ve erişim iptali | M4 | M6 gerçek adapter ve M8 staging |
| AK-002 offline ve AK-003 admin kesintisi | M5 | M8 uzun çalışma |
| AK-001 context/izin ve AK-004 geçmiş/mood/memory/kişilik | M3–M6, ilgili özellik eklendikçe | M8 kabul matrisi |
| Public sürüm/hash, medya, geri çekme ve cache | M7 | M8 staging |
| Gerçek model kalitesi, retrieval ve performans | M6 | M8 sürümlü eval eşiği |
| Backup/restore ve operasyon runbook'ları | M8 | Pilot öncesi tatbikat |

Testler davranış ve hata sınırlarını doğrular; yalnız uygulamanın yaptığı işlemleri tekrar eden testler kabul kanıtı değildir. Her aşamada ilgili unit/integration/contract kontrolleri çalışır. Gerçek model ölçümleri deterministic testlerden ayrı tutulur.

## Çalışma ve teslim disiplini

- Bir sonraki açık iş kimliğini seç; bağımlı aşamanın çıkış koşulu tamamlanmadan ona dayanan canlı özellik açma.
- Önce en küçük çalışan akışı tamamla; schema, backend kuralı, gerekli test ve UI durumunu birlikte teslim et. Ortak domain kurallarını web/API/worker içinde kopyalama.
- Koddan üretilen OpenAPI client'ını güncelle; generated dosyaları elle düzeltme. SQL migration tarihçesinin tek kaynağı Supabase migration'ları olsun.
- İlgili kontroller geçtikten sonra anlamlı commit oluştur. Aynı committe ilgisiz dosya/değişiklik toplama; çalışma ağacındaki kullanıcı değişikliklerini koru.
- Oturum sonunda ilerlemeyi bu planda işaretle ve `Tarih / Tamamlanan iş / Commit / Doğrulama / Sıradaki iş` biçiminde kısa bir kayıt ekle. Gerçekleşmemiş test sonucunu veya tamamlanmamış işi tamamlandı yazma.
- Model/provider benchmark çıktıları için ihtiyaç doğduğunda `docs/operations`, yeni mimari karar için `docs/decisions` altında gerçek içerik oluştur. Boş klasör ağacı, Obsidian mirror veya sonraki faz altyapısını önceden hazırlama.

## İlerleme kaydı

| Tarih | Tamamlanan iş | Commit / doğrulama | Sıradaki iş |
| --- | --- | --- | --- |
| 2026-09-22 | Implementation planı hazırlandı; uygulama başlamadı | Plan dokümanı; çalışma zamanı testi yapılmadı | M1.1 |
| 2026-09-23 | M1 repo/bağımlılık temeli, sınırlı DB rolleri, health UI/API, container ve CI yapılandırması eklendi | `d3ea298`, `7d44fbc`; backend 9 unit + 2 DB testi, 15 pgTAP, frontend 5 test, lint/typecheck/build, DB lint/advisors ve container health smoke geçti. Yerel disposable DB reset sonrası migration tekrarlandı; gerçek kullanıcı verisi yoktu. Web portu 3100. | M1.6 — temiz CI koşusunu doğrula; ardından kutuları kapat |
| 2026-09-23 | M1.1–M1.6 tamamlandı; güncel Action sürümleri SHA ile ve runner Ubuntu 24.04 olarak sabitlendi | `3f49a46`, `fc1179b`; [Foundation CI 35835256902](https://github.com/burakbayramin/CCE/actions/runs/35835256902) üç job başarılı: checks, database, containers. Temiz checkout'ta kilitli kurulum, boş DB migration/reset tekrarı, gerçek rol testleri, OpenAPI drift, build ve web → API → DB smoke geçti. Yerelde iki container non-root ve health akışı doğrulandı. | M2.1 — kimlik ve Owner bootstrap; başlamadı |
| 2026-09-23 | M2.1 kimlik dilimi ve M2.2'nin JWT/transaction-context temeli uygulandı | Yerelde 20 unit, 4 DB/Auth integration, 27 pgTAP, 7 frontend testi ve gerçek Edge üzerinde kayıt/giriş/çıkış/SSR/admin-red tarayıcı testi geçti. Owner metadata yükseltmesi, ikinci Owner ataması, revoke sonrası eski token ve pooled A → B → kimliksiz erişim sınandı. Gerçek Owner seçilmedi. | Temiz CI; ardından M2.3 başvuru modeli. M2 bütünü tamamlanmadı. |
| 2026-09-23 | M2.1 temiz CI doğrulandı | `d288dfd`, `2d32861`; [CI 35864409030](https://github.com/burakbayramin/CCE/actions/runs/35864409030) checks/database/containers başarılı. | M2.3–M2.4 taslak dilimi |
| 2026-09-23 | M2.3–M2.4 taslak, immutable gönderim, geri çekme, yapılandırılmış form ve audit dilimi uygulandı | Yerelde 20 unit + 7 DB/Auth integration, 27 pgTAP, 7 frontend testi; lint/typecheck, production container build ve Edge uçtan uca akış geçti. İki kullanıcı izolasyonu, eşzamanlı oluşturma/kaydetme, eski sürüm, kota ve revizyon değişmezliği sınandı. Bu dilimin temiz CI sonucu henüz doğrulanmadı. | Önce son push CI sonucunu kontrol et; sonra M2.3–M2.5 inceleme/feedback/revizyon ve M2.6 private medya. Haftalık kullanımda %4 kaldığı ölçülünce kullanıcının %10 sınırı nedeniyle geliştirme durduruldu. |
| 2026-09-24 | Taslak diliminin temiz CI sonucu doğrulandı | `7f0ba01`, `4cd7681`; [CI 35866586457](https://github.com/burakbayramin/CCE/actions/runs/35866586457) checks/database/containers başarılı. | M2 inceleme dilimi |
| 2026-09-24 | Ayrı engine yetkisi, Owner inceleme/feedback, immutable revizyon geçmişi, değişiklik talebi ve moderasyon onay kapısı eklendi | Ayrı `cce-integration` stack'inde 38 backend testi ve 39 pgTAP başarılı; frontend 7 test, typecheck/lint/build geçti. Gerçek yerel Owner/verileri korunuyor. Windows/WSL saat farkından kaynaklı token hatası doğrulandı ve sınırlı 5 saniye tolerans test edildi. İki oturumlu inceleme tarayıcı testi CI'a eklendi; sonucu henüz doğrulanmadı. | Son CI/tarayıcı doğrulaması; ardından M2.6 private avatar. Gerçek moderasyon sağlayıcısı M3 karar kapısında; M2 bütünü tamamlanmadı. |
