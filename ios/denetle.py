"""iOS derlemesine giren dosyaları denetler: uygulamada kullanılmayan, kapalı ya da gizli tutulan
hiçbir özellik iPhone sürümüne girmemeli. Yasak bir ifade bulunursa derleme durur.

  python3 ios/denetle.py ios/gen/Jalon/site ios/Jalon ios/project.yml

Jalon yalnızca dosya seçme, kaydetme ve kopyalama yapar; konum, bildirim ve ağ isteği kullanmaz.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

YASAK = [
    # Android'e ait kod ve işaret artıkları
    r"AndroidBridge", r"android:start", r"android:end",
    # reklam ve satın alma
    r"[Aa]d[Mm]ob", r"[Rr]eklam", r"[Rr]ewarded", r"[Pp]urchase", r"[Bb]illing", r"StoreKit",
    # ayarla açılıp kapanan kabuk özellikleri
    r"ExtraCSS", r"Geolocation", r"Reminders", r"ProxyOrigin",
    # Jalon'da olmayan telefon özellikleri
    r"CLLocationManager", r"CoreLocation", r"NSLocation\w*UsageDescription",
    r"UNUserNotificationCenter", r"UserNotifications",
    r"URLSession", r"__vekil__", r"[Pp]roxy", r"workers\.dev",
]
UZANTI = (".html", ".js", ".swift", ".yml", ".plist")

hatalar = []
for kok in sys.argv[1:]:
    yol = Path(kok)
    if not yol.exists():
        hatalar.append(f"{yol}: bulunamadı")
        continue
    dosyalar = [yol] if yol.is_file() else sorted(p for p in yol.rglob("*") if p.suffix in UZANTI)
    for f in dosyalar:
        metin = f.read_text(encoding="utf-8", errors="ignore")
        for y in YASAK:
            for m in re.finditer(y, metin):
                satir = metin.count("\n", 0, m.start()) + 1
                hatalar.append(f"{f}:{satir}: yasak ifade: {m.group(0)}")
        if f.suffix == ".html":
            # Sayfadaki betikler bozulmadan kalmış mı (işaretli bölüm çıkarıldıktan sonra)
            betikler = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)</script>", metin)
            for i, (nit, kod) in enumerate(betikler):
                tur = re.search(r"\btype=[\"']?([^\"'\s>]+)", nit)
                tur = tur.group(1).lower() if tur else ""
                if tur not in ("", "text/javascript", "module"):
                    continue
                with tempfile.NamedTemporaryFile("w", suffix=".mjs" if tur == "module" else ".js",
                                                 delete=False, encoding="utf-8") as t:
                    t.write(kod)
                try:
                    r = subprocess.run(["node", "--check", t.name], capture_output=True, text=True)
                finally:
                    os.unlink(t.name)
                if r.returncode:
                    hatalar.append(f"{f}: betik {i + 1} sözdizimi hatası: {r.stderr.strip()[:300]}")
if hatalar:
    print("\n".join(hatalar))
    sys.exit(1)
print("iOS denetimi: temiz")
