# Jalon — NCN ⇄ GSI Dönüştürücü

© 2026 Egemen Çalıkoğlu. Tüm hakları saklıdır. Ayrıntılar için [LICENSE](LICENSE).

Sahada çalışan herkes bilir: Total station'dan gelen Leica GSI dosyasını Netcad'e almak ya da Netcad'deki NCN noktalarını alete atmak her seferinde ayrı bir uğraş. Birden fazla NCN dosyasını birleştirmek de cabası. Bu işi telefondan tek ekranda halledebilmek için Jalon'u yapıyorum.

**Jalon neler yapıyor?**

- Netcad NCN ve Leica GSI (GSI-8 / GSI-16) dosyalarını iki yönde dönüştürüyor
- Birden fazla nokta dosyasını tek dosyada birleştiriyor
- Noktaları planda gösteriyor, sonucu `.GSI` / `.NCN` olarak kaydediyor ya da panoya kopyalıyor
- Dosya yöneticisinden "Birlikte aç" veya "Paylaş" ile gelen dosyaları doğrudan listeye ekliyor

Uygulama şu an geliştirme aşamasında; ilk hedefim Google Play. Ücretsiz olacak, alt kısımda küçük bir reklam alanı bulunacak.

## Proje yapısı (kendime not)

- Uygulamanın kendisi `app/src/main/assets/index.html` dosyası (web sürümüyle aynı sayfa).
- `MainActivity.java` bu sayfayı açıyor; dosya seçme, kaydetme, panoya kopyalama ve reklamları yönetiyor.

## APK nasıl derlenir?

Android Studio kurmama gerek yok. Her `main` gönderiminde **GitHub Actions** uygulamayı kendisi derliyor:

1. GitHub'da deponun **Actions** sekmesini açın, en son "Android derleme" çalışmasına tıklayın.
2. Sayfanın altındaki **Artifacts** bölümünden **NCN-GSI-Donusturucu** dosyasını indirin. İçinde:
   - `NCN-GSI-Donusturucu.apk` → telefona kurulan uygulama
   - `NCN-GSI-Donusturucu.aab` → Play Console'a yüklenecek paket (anahtar gizli değerleri girildiyse)

İstersem Android Studio ile de açıp `Build > Build App Bundle(s) / APK(s)` diyebilirsiniz.

## GitHub gizli değerleri (Settings › Secrets and variables › Actions)

| Ad | Ne |
|---|---|
| `KEYSTORE_BASE64` | Yükleme anahtarının base64 hali |
| `KEYSTORE_PASSWORD` | Anahtar deposu şifresi |
| `KEY_ALIAS` | `ncngsi` |
| `KEY_PASSWORD` | Anahtar şifresi |
| `ADMOB_APP_ID` | AdMob uygulama kimliği (`ca-app-pub-…~…`) |
| `ADMOB_BANNER_ID` | AdMob banner reklam birimi (`ca-app-pub-…/…`) |

AdMob değerleri girilmezse sürüm derlemesi de Google'ın **test** reklamlarını kullanır; bu haliyle para kazandırmaz. Anahtar girilmeden derlenen APK her zaman test reklamı gösterir. Kendi reklamıma tıklamamalıyım, AdMob hesabı kapatılabilir.

## Play Store'a yükleme kontrol listem

1. **Google Play Console** geliştirici hesabı (bir kerelik 25 $). Yeni kişisel hesaplarda yayından önce 12 test kullanıcısıyla 14 günlük kapalı test zorunludur.
2. **AdMob** hesabı açın, uygulamayı ekleyin, bir *Banner* reklam birimi oluşturun → kimlikleri GitHub'a girin.
3. AdMob'da **Gizlilik ve mesajlaşma › GDPR** mesajını oluşturup yayınlayın (uygulamadaki izin ekranı buradan gelir).
4. **Gizlilik politikası**: `docs/gizlilik.html` hazır. İçindeki `[E-POSTA ADRESİNİZ]` kısmını doldurun, depo ayarlarından *Pages › Branch: main › /docs* seçin. Web uygulaması `https://maelstoorm.github.io/ncn-gsi/`, gizlilik politikası `https://maelstoorm.github.io/ncn-gsi/gizlilik.html` adresinde yayınlanır; gizlilik adresini Play Console'a girin.
5. Play Console'da: *Uygulama içeriği* → Reklam içeriyor: **Evet**, Reklam kimliği kullanımı: **Evet (Reklam)**, Veri güvenliği formu (AdMob: cihaz kimlikleri, yaklaşık konum, uygulama etkileşimleri), Hedef kitle: 18+.
6. Mağaza girişi görselleri `store/` klasöründe: 512×512 ikon ve 1024×500 öne çıkan görsel. En az 2 telefon ekran görüntüsünü test APK'sından alın.
7. `ncn-gsi-play-store-aab` içindeki `.aab` dosyasını *Test › Kapalı test* (sonra *Üretim*) sürümüne yükleyin. **Play Uygulama İmzalama** açık kalsın.

## iOS (App Store)

iOS sürümü de aynı `index.html` sayfasını açar; Mac gerekmez, GitHub'ın Mac sunucusu derler.

- `ios/project.yml` : Xcode projesinin tarifi (XcodeGen). `ios/Jalon/` : Swift kodu ve ikon.
- `.github/workflows/ios.yml` : `ios/` veya sayfa değişince çalışır; elle de *Actions › iOS derleme › Run workflow* ile başlatılır.
- `ios/ci/asc.py` : Apple tarafını otomatik hazırlar (paket kimliği, ortak dağıtım sertifikası, imza profili).
  Sertifika şifreli olarak bu deponun `ios-imza` dalında durur; Deprem Atlası ve Pafta da aynısını kullanır.

GitHub gizli değeri (App Store Connect › Users and Access › Integrations › App Store Connect API, rol **Admin**):

| Ad | Ne |
|---|---|
| `ASC_KEY_P8` | İndirilen `.p8` dosyasının tüm içeriği |

Key ID ve Issuer ID gizli değildir, iş akışında yazılıdır. Anahtar değişirse `ASC_KEY_ID` ve `ASC_ISSUER_ID` adıyla gizli değer girmek yeterli, iş akışındakilerin yerine geçer.

İlk derlemeden sonra App Store Connect › Uygulamalar › **+** › Yeni Uygulama ile `com.egemen.jalon` paket kimliğini seçip uygulama kaydını oluşturun, derlemeyi yeniden çalıştırın; derleme TestFlight'a yüklenir.

## Paket adı

`com.egemen.jalon`. Play Store'a ilk yüklemeden sonra değiştirilemez; değiştirmek gerekirse `app/build.gradle` içindeki `namespace` ve `applicationId` satırlarını ve `java/com/egemen/ncngsi` klasörünü birlikte değiştirin.

## Sürüm güncelleme

`versionCode` her GitHub Actions çalışmasında otomatik artar. Görünen sürüm adı için `app/build.gradle` içindeki `versionName` değerini değiştirin.

## Play Store mağaza bilgileri (öneri)

- **Uygulama adı (en fazla 30 karakter):** Jalon: NCN GSI Dönüştürücü
- **Kısa açıklama (en fazla 80 karakter):** Netcad NCN ve Leica GSI nokta dosyalarını birleştir, dönüştür, planda gör.
