# NCN ⇄ GSI Dönüştürücü (Android)

© 2026 Egemen Çalıkoğlu. Tüm hakları saklıdır. Ayrıntılar için [LICENSE](LICENSE).

Netcad NCN ve Leica GSI (GSI-8 / GSI-16) nokta dosyalarını iki yönde birleştirip dönüştüren Android uygulaması. Alt kısımda AdMob banner reklamı gösterir.

- Uygulamanın kendisi `app/src/main/assets/index.html` dosyasıdır (web sürümüyle aynı sayfa).
- `MainActivity.java` bu sayfayı açar; dosya seçme, `.GSI` / `.NCN` olarak kaydetme, panoya kopyalama ve reklamları yönetir.
- Dosya yöneticisinden "Birlikte aç" veya "Paylaş" ile gelen dosyalar doğrudan listeye eklenir.

## APK nasıl derlenir?

Bilgisayara Android Studio kurmak gerekmez. Proje GitHub'a yüklendiğinde **GitHub Actions** her `main` gönderiminde otomatik derler:

1. GitHub'da deponun **Actions** sekmesini açın, en son "Android derleme" çalışmasına tıklayın.
2. Sayfanın altındaki **Artifacts** bölümünden **NCN-GSI-Donusturucu** dosyasını indirin. İçinde:
   - `NCN-GSI-Donusturucu.apk` → telefona kurulan uygulama
   - `NCN-GSI-Donusturucu.aab` → Play Console'a yüklenecek paket (anahtar gizli değerleri girildiyse)

İsterseniz Android Studio ile de açıp `Build > Build App Bundle(s) / APK(s)` diyebilirsiniz.

## GitHub gizli değerleri (Settings › Secrets and variables › Actions)

| Ad | Ne |
|---|---|
| `KEYSTORE_BASE64` | Yükleme anahtarının base64 hali |
| `KEYSTORE_PASSWORD` | Anahtar deposu şifresi |
| `KEY_ALIAS` | `ncngsi` |
| `KEY_PASSWORD` | Anahtar şifresi |
| `ADMOB_APP_ID` | AdMob uygulama kimliği (`ca-app-pub-…~…`) |
| `ADMOB_BANNER_ID` | AdMob banner reklam birimi (`ca-app-pub-…/…`) |

AdMob değerleri girilmezse sürüm derlemesi de Google'ın **test** reklamlarını kullanır; bu haliyle para kazandırmaz. Anahtar girilmeden derlenen APK her zaman test reklamı gösterir: kendi reklamınıza tıklamak AdMob hesabının kapatılmasına yol açabilir.

## Play Store'a yükleme kontrol listesi

1. **Google Play Console** geliştirici hesabı (bir kerelik 25 $). Yeni kişisel hesaplarda yayından önce 12 test kullanıcısıyla 14 günlük kapalı test zorunludur.
2. **AdMob** hesabı açın, uygulamayı ekleyin, bir *Banner* reklam birimi oluşturun → kimlikleri GitHub'a girin.
3. AdMob'da **Gizlilik ve mesajlaşma › GDPR** mesajını oluşturup yayınlayın (uygulamadaki izin ekranı buradan gelir).
4. **Gizlilik politikası**: `docs/index.html` hazır. İçindeki `[E-POSTA ADRESİNİZ]` kısmını doldurun, depo ayarlarından *Pages › Branch: main › /docs* seçin. Adres `https://<kullanıcı>.github.io/<depo>/` olur; bunu Play Console'a girin.
5. Play Console'da: *Uygulama içeriği* → Reklam içeriyor: **Evet**, Reklam kimliği kullanımı: **Evet (Reklam)**, Veri güvenliği formu (AdMob: cihaz kimlikleri, yaklaşık konum, uygulama etkileşimleri), Hedef kitle: 18+.
6. Mağaza girişi görselleri `store/` klasöründe: 512×512 ikon ve 1024×500 öne çıkan görsel. En az 2 telefon ekran görüntüsünü test APK'sından alın.
7. `ncn-gsi-play-store-aab` içindeki `.aab` dosyasını *Test › Kapalı test* (sonra *Üretim*) sürümüne yükleyin. **Play Uygulama İmzalama** açık kalsın.

## Paket adı

`com.egemen.ncngsi`. Play Store'a ilk yüklemeden sonra değiştirilemez; değiştirmek isterseniz `app/build.gradle` içindeki `namespace` ve `applicationId` satırlarını ve `java/com/egemen/ncngsi` klasörünü birlikte değiştirin.

## Sürüm güncelleme

`versionCode` her GitHub Actions çalışmasında otomatik artar. Görünen sürüm adı için `app/build.gradle` içindeki `versionName` değerini değiştirin.
