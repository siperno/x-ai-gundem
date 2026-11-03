# X AI gündemi — @kuytancaglar

GitHub Actions → kaynak ve tarih kontrolü → yerel Türkçe çeviri → özgün bilgi kartı → Buffer → X.
Mac kapalıyken GitHub ve Buffer sunucularında çalışır. Ücretli AI API'si veya Metricool kullanmaz.

## Zamanlama

Hazırlık her gün **07:47 Europe/Berlin**, yedek deneme **08:12**. Buffer hedef yayın saati **08:30**.
**09:45** kontrolü Buffer'ın `sent` teslim durumunu doğrular; eksik/hatalı yayında Actions çalışması hata verir.
IANA saat dilimi ve Python zoneinfo yaz/kış saatini otomatik uygular.
GitHub Actions kesin zaman garantisi vermez. Geç başlayan çalışma güncel verileri yeniden toplar ve
aynı günün yayını yoksa 3 dakika sonrasına zamanlar; 09:30 kesme saati yoktur.
08:30 hedefi korunur, geciken koşular geç yayınlanır. Hazırlık sırasında Berlin tarihi değişirse
eski günün içeriği gönderilmez; yeni gün için yeniden çalışma gerekir.
Haber penceresi hazırlık anından geriye tam 24 saattir; hazırlık ile 08:30 arasındaki haberleri kapsamaz.

## İçerik ve doğrulamanın kapsamı

- OpenAI ve Google AI resmi RSS duyuruları, Türkçe TRT Haber bilim/teknoloji RSS'i.
- RSS yayın tarihi, son 24 saat, gerçek HTTPS kaynak bağlantısı ve erişilebilirlik kontrolü.
- Bu kontrol, kurumun iddialarının bağımsız bilimsel doğrulaması değildir. Metinler kaynak duyurusu olarak sunulur.
- Başlıklar ücretsiz açık kaynak Argos Translate ile çalıştırıcıda çevrilir; makine çevirisi hata yapabilir.
- En fazla 3 haber ve 2 GitHub keşfi bir X zincirinde paylaşılır. Yeni haber yoksa açıkça belirtilir.
- GitHub API'de `artificial-intelligence` etiketi, en az 1.000 toplam yıldız,
  arşivlenmemiş/fork olmayan ve son 30 günde güncellenmiş depolar. İlk 30 sonuçtan günlük dönüşümlü seçim.
  Toplam yıldızlar günlük kazanılan yıldız veya trend skoru olarak sunulmaz.
- Her metin 280 karakter sınırına göre ihtiyatlı biçimde kontrol edilir.

## Görsel

Pillow ile özgün 1200×675 bilgi kartı üretilir; resim üretim aboneliği yoktur.
Kart bu açık deponun `media/` klasöründe saklanır, Buffer'a herkese açık ham dosya URL'si verilir.
Barındırma hatasında metin ve gerçek bağlantılarla devam edilir. Buffer'ın görseli sonradan reddetmesi
durumunda kör yeniden deneme yapılmaz. Bu görsel, üretken AI ile çizilmiş resim değildir.

## Güvenlik ve kurulum

Tek sır: Settings → Secrets and variables → Actions → `BUFFER_API_KEY`.
Anahtarı koda, README'ye, loga veya sohbete yazmayın. Personal key'de hesap/kanal okuma,
gönderi okuma ve gönderi oluşturma/yazma izinleri gerekir. Gereksiz silme izinleri gerekmez.
API `https://api.buffer.com` GraphQL, Bearer kimlik doğrulaması kullanır.
Gerekli Personal key izinleri: `accountRead`, `postsRead`, `postsWrite`.
Anahtarın son kullanma tarihinden önce aynı GitHub secret güncellenmelidir; Buffer süreli anahtarlar kullanır.
`@kuytancaglar` X kimliği tekil eşleşmezse yayın durur.
GitHub'ın geçici `GITHUB_TOKEN` değeri otomatik sağlanır; ayrı GitHub PAT gerekmez.

Actions → AI gündemi → Run workflow:
- `check`: kanal ve okuma yetkilerini doğrular, yayın oluşturmaz.
- `preview`: haber, çeviri ve kart oluşturur; yalnızca 3 günlük artifact kaydeder.
- `draft`: içeriği Buffer'a yayınlanmayan taslak olarak göndererek yazma/görsel/zincir uyumunu test eder.
- `publish`: bugünkü yayını 08:30'a, hedef saat geçtiyse 3 dakika sonrasına zamanlar.
- `verify`: bugünkü Buffer gönderisinin teslim durumunu kontrol eder.

Otomatik schedule aktiftir; secret hazır olduğunda sonraki sabah çalışır.
`state/YYYY-MM-DD.json` kalıcı günlük kayıtları tekrarlı paylaşımı önler.
`attempting` kaydı kalırsa önce Buffer'da sonucu kontrol edin. Gönderi oluşmadığı kesinleşmeden
kaydı silmeyin: ağ zaman aşımında sunucu gönderiyi oluşturmuş olabilir.
`scheduled`, Buffer'ın kabul ettiğini gösterir; X'e teslim edildiğini garanti etmez.
09:45 kontrolü gönderinin son teslim durumunu Buffer'dan okur. Hatalarda GitHub Actions bildirim
tercihleriniz geçerlidir; ayrıca Buffer kuyruğu ve hata bildirimlerini kontrol edebilirsiniz.

## Ücretsiz sınırlar

Açık depoda standart `ubuntu-latest` Actions çalıştırıcısı ücretsizdir; ücretli/larger runner kullanılmaz.
Özel depoya taşınırsa hesabın ücretsiz kotası diğer depolarla ortaktır (GitHub Free için
2.000 standart Linux dakika eşdeğeri; güncel faturalamada dahil hesaplama kredisi olarak da gösterilebilir).
Artifact saklama 3 günle sınırlıdır. Argos modeli her içerik koşusunda indirilir; ilk kurulum birkaç dakika sürebilir.
Buffer Free: 1 API anahtarı, kanal başına 30 günde 1.000 istek, toplam en fazla 3.000;
diğer entegrasyonlarla ortak limitler ve daha kısa hız sınırları geçerlidir.
Buffer Free kuyruğu sınırlıdır; dolu kuyruk ve kopmuş X bağlantısı yayını engelleyebilir.
Açık depoda 60 gün etkinlik olmazsa GitHub schedule devre dışı kalabilir.
Normal başarılı günlük kart/kayıt commitleri etkinlik üretir; uzun süren arızalarda Actions'ı kontrol edin.
Sıfır ücret, hizmetlerin ücretsiz plan ve politikaları sürdüğü sürece geçerlidir; süreklilik garantisi değildir.

## Kaynaklar

- https://developers.buffer.com/guides/authentication.html
- https://developers.buffer.com/guides/posts-and-scheduling.html
- https://developers.buffer.com/examples/create-threaded-post.html
- https://developers.buffer.com/examples/create-image-post.html
- https://support.buffer.com/articles/using-buffers-api-GtIYIQilz5
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://argos-translate.readthedocs.io/en/stable/index.html

Yerel test: `python -m unittest -v`. Testler ağ erişimi veya anahtar gerektirmez.

