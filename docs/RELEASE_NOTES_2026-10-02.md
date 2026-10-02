# Bekleyen sürüm notu — M3.3 fixture aktivasyonu ve şema v6

2026-10-02. Bu sürümde gerçek karakter aktivasyonu açılmadı. `cce-local` veritabanı ve
mevcut World Owner kaydı değiştirilmedi; migration yalnız `cce-integration` izole
test yığınına uygulandı. Uygulama kodu şema v6 ister; v1–v5 ile startup reddedilir.
Eski API de v6 üzerinde hazır kabul edilmez. Migration ve API aynı yayın paketi
olarak, trafiği durdurup tam veritabanı yedeği aldıktan sonra uygulanmalıdır;
rollback için uyumlu tam yedek + eski API birlikte gerekir. Yalnız `schema_version`
değerini geri yazmak bir rollback değildir.

Yeni `world_private.characters`, `character_initial_state`, kapasite ve audit
tabloları FORCE RLS altındadır. Aktivasyon önce kapasite satırını, sonra başvuruyu
kilitler. Kaynak revizyonu, Owner onayı, fixture moderasyonu, derlenmiş artifact
hash'i ve hazır avatar bağını denetler. AI person kimliği, karakter, kaynak bağlı
başlangıç snapshot'ı ve audit event tek transaction'da oluşturulur. Geç gelen
audit hatası bütün yazımları geri alır. Tekrar aynı karakteri döndürür; ikinci
audit veya kapasite tüketimi yaratmaz. Aktif limitin üst sınırı 50'dir; 0 yeni
aktivasyonları durdurur. Limit değişimi Owner gerekçesi, beklenen mevcut değer ve
idempotency kimliği ile audit edilir.

Başlangıç snapshot'ındaki memory/drive/goal/relationship/secret kayıtları kaynak
önerileridir; yaşanmış deneyim değildir. Başlangıç duygu katsayıları geçici,
Owner ilişkisi deneyimsizdir. Runtime memory/relationship/mood motorları M4/M6
işidir. `ACTIVE` dışına geçiş ve restore komutları M3.4'e bırakıldı.

Fixture komutu için dört kapı birlikte gereklidir: API test ortamı, fixture
moderasyon ve definition kaynağı, mevcut fixture onay politikası ve varsayılanı
kapalı `fixture_activation_policy`. Sonuncusu yalnız izole test provisioner'ında
`--activation-fixtures` ile açılır. Public/Data API, worker ve contributor rolleri
bu kapıyı değiştiremez veya karakter başlangıç durumuna doğrudan yazamaz.
Gerçek içerik için migration'da aktivasyon komutu yoktur; gerçek yerel metin/avatar
tarayıcılarının seçimi ve kabulü ayrıca yapılacaktır. Normal web görünümünde
fixture komutu gösterilmez; izole testte World Owner gerekçe girerek deneyebilir.

Yerel doğrulama için `CCE_ENVIRONMENT=test` ile ayrı `--isolated-test-stack`
üzerinde `scripts/setup_local_db.py --isolated-test-stack --activation-fixtures`
çalıştırılır. Bu bayrak normal local ortamda reddedilir. Gerçek DB migration'ı,
test ve çalışma komutları kullanıcı verisi olan bir yığına uygulanmamalıdır.

Doğrulama sonucu: 101 pgTAP, 56 izole DB/Auth/Storage entegrasyon testi
(iki browser wrapper seçimi atlandı), 140 backend birim testi, 38 web testi,
üç gerçek Chrome senaryosu, backend/web lint, format, mypy, typecheck ve
production web build geçti. SQL lint hata vermedi; önceki `finish_moderation`
kullanılmayan değişken uyarısı sürüyor. Yeni GitHub CI sonucu henüz yoktur.
