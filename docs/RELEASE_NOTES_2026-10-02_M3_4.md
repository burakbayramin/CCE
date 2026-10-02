# Bekleyen sürüm notu — M3.4 fixture lifecycle ve şema v7

2026-10-02. Şema v7, fixture karakter için `ACTIVE`, `SUSPENDED`, `ARCHIVED`
geçişlerini, ayrı restore/yeniden aktivasyon komutlarını ve append-only lifecycle
audit geçmişini ekler. Restore karakteri aynı UUID/person ve korunmuş başlangıç
state'iyle yalnız `SUSPENDED` durumuna döndürür; aktif dünyaya dönüş sonraki
komuttur. Askı/arşiv gerekçesi Owner ekranında görünür. Yeni etkileşim izni
`lifecycle_version` ile pinlenir; M4'teki iş protokolü bu değeri commit öncesi
tekrar denetlemek zorundadır. M4 karakter işi henüz oluşturulmadığı için eski
işleri otomatik yeniden başlatma veya iptal etme davranışı bu sürümde yoktur.

Her geçişte durum, sürüm, actor, gerekçe ve definition audit'e eklenir. Aynı
`request_id` ve payload tekrarında mevcut event döner; çelişen tekrar reddedilir.
Arşiv restore'u arşiv gerekçesinin incelenmesini ve güncel fixture kaynak/onay
geçerliliğini gerektirir. Yeniden aktivasyon ayrıca askı gerekçesini ve kapasite
sınırını doğrular. Kapasite doluyken sunucu `409` döndürür ve Owner ekranında
görünür. Doğrudan runtime tablo yazımı ve contributor erişimi yasaktır.

Migration yalnız ayrı `cce-integration` yığınında denendi. Boş izole veritabanında
18 migration, 110 pgTAP, 60 gerçek DB/Auth/Storage entegrasyon testi (iki mevcut
browser wrapper seçimi atlandı), 140 backend birim testi, 38 web testi ve üç
Chrome senaryosu geçti. Ruff, mypy ve web lint/typecheck/build temiz. SQL lint
hata vermedi; eski `finish_moderation` kullanılmayan değişken uyarısı sürüyor.
Database advisor önceki v6'dan kalan çoklu `cce_migrator` SELECT politikası için
bir performans uyarısı verdi; yeni lifecycle tablolarında güvenlik hatası yok.
Yeni GitHub CI sonucu henüz yoktur.

Uygulama v7 şemasını bekler. `cce-local` hâlâ v1'dir ve mevcut Owner verisi
değiştirilmedi. v7'ye yayın veya geri dönüş için v6 sürüm notundaki tam DB
yedeği, trafik durdurma ve uyumlu API/DB eşleştirme kuralları geçerlidir.
Model kararı ertelendiğinden gerçek moderasyon ve gerçek karakter lifecycle
komutları kapalı kalır.
