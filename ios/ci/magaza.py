"""App Store sayfalarını doldurur (GitHub Actions'ta elle çalıştırılır).

ios/magaza/magaza.json içindeki her uygulama için:
  kategori, alt başlık, gizlilik adresi, açıklama, anahtar kelimeler, tanıtım metni, destek adresi,
  telif, yaş derecelendirmesi (hepsi "yok"), içerik hakları, ücretsiz fiyat, inceleme iletişim bilgisi,
  6.9 inç iPhone ekran görüntüleri (ios/magaza/<anahtar>/*.png) ve en son geçerli derleme.
App Privacy (veri toplama) formu API'de yok; App Store Connect'te elle doldurulur. İncelemeye gönderme de elle yapılır.
Gerekenler: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8, UYGULAMALAR (boşlukla ayrılmış anahtarlar ya da "hepsi").
"""
import base64
import hashlib
import json
import re
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

API = "https://api.appstoreconnect.apple.com"
KEY_ID = os.environ["ASC_KEY_ID"].strip()
ISSUER = os.environ["ASC_ISSUER_ID"].strip()
P8 = os.environ["ASC_KEY_P8"].strip().encode()
KOK = Path(__file__).resolve().parent.parent / "magaza"
LOCALE = "tr"
ILETISIM = {"contactFirstName": "Egemen", "contactLastName": "Çalıkoğlu",
            "contactEmail": "egementughan@gmail.com", "contactPhone": "+905461521244"}
TELIF = "2026 Egemen Çalıkoğlu"
NOTLAR = ("Uygulama hesap ya da giriş gerektirmez, internetsiz çalışır ve kişisel veri toplamaz. "
          "İnceleme için özel bir adım yoktur.")


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def token():
    key = serialization.load_pem_private_key(P8, password=None)
    head = b64u(json.dumps({"alg": "ES256", "kid": KEY_ID, "typ": "JWT"}).encode())
    now = int(time.time())
    body = b64u(json.dumps({"iss": ISSUER, "iat": now, "exp": now + 900, "aud": "appstoreconnect-v1"}).encode())
    r, s = decode_dss_signature(key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{head}.{body}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def api(method, path, data=None, quiet=False):
    url = path if path.startswith("http") else API + (path if path.startswith("/v") else "/v1" + path)
    req = urllib.request.Request(url, method=method, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if not quiet:
            try:
                errs = json.loads(detail).get("errors", [])
                detail = " | ".join(f"{x.get('title')}: {x.get('detail')} {json.dumps(x.get('meta', {}), ensure_ascii=False)}" for x in errs) or detail
            except Exception:
                pass
            print(f"  ! {method} {url.replace(API, '')} -> {e.code} {detail[:3000]}")
        return None


def tek(path):
    r = api("GET", path) or {}
    d = r.get("data", [])
    return d[0] if d else None


def kategori(app, info_id):
    rel = {"primaryCategory": {"data": {"type": "appCategories", "id": app["category"]}}}
    if app.get("sub"):
        rel["primarySubcategoryOne"] = {"data": {"type": "appCategories", "id": app["sub"]}}
    if app.get("sub2"):
        rel["primarySubcategoryTwo"] = {"data": {"type": "appCategories", "id": app["sub2"]}}
    if api("PATCH", f"/appInfos/{info_id}", {"data": {"type": "appInfos", "id": info_id, "relationships": rel}}):
        print("  kategori:", app["category"], app.get("sub") or "")


def bilgi_yerel(app, info_id):
    loc = next((l for l in (api("GET", f"/appInfos/{info_id}/appInfoLocalizations") or {}).get("data", [])
                if l["attributes"]["locale"].startswith(LOCALE)), None)
    attrs = {"subtitle": app["subtitle"], "privacyPolicyUrl": app["privacy"]}
    if loc:
        ok = api("PATCH", f"/appInfoLocalizations/{loc['id']}", {"data": {"type": "appInfoLocalizations", "id": loc["id"], "attributes": attrs}})
    else:
        ok = api("POST", "/appInfoLocalizations", {"data": {"type": "appInfoLocalizations", "attributes": dict(attrs, locale="tr"),
                                                             "relationships": {"appInfo": {"data": {"type": "appInfos", "id": info_id}}}}})
    if ok:
        print("  alt başlık ve gizlilik adresi")


METIN_ALANLAR = {"alcoholTobaccoOrDrugUseOrReferences", "contests", "gamblingSimulated", "gunsOrOtherWeapons",
                 "medicalOrTreatmentInformation", "profanityOrCrudeHumor", "sexualContentGraphicAndNudity",
                 "sexualContentOrNudity", "horrorOrFearThemes", "matureOrSuggestiveThemes", "violenceCartoonOrFantasy",
                 "violenceRealisticProlongedGraphicOrSadistic", "violenceRealistic"}


def yas(info_id):
    dec = (api("GET", f"/appInfos/{info_id}/ageRatingDeclaration") or {}).get("data")
    if not dec:
        return
    did = dec["id"]
    atla = {"kidsAgeBand", "ageRatingOverride", "ageRatingOverrideV2", "koreaAgeRatingOverride",
            "developerAgeRatingInfoUrl", "gracRatingClassificationNumber"}
    attrs = {k: ("NONE" if k in METIN_ALANLAR or isinstance(v, str) else False)
             for k, v in dec["attributes"].items() if k not in atla}
    for _ in range(8):
        body = json.dumps({"data": {"type": "ageRatingDeclarations", "id": did, "attributes": attrs}}).encode()
        req = urllib.request.Request(f"{API}/v1/ageRatingDeclarations/{did}", method="PATCH", data=body,
                                     headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req).read()
            print("  yaş derecelendirmesi: hepsi yok")
            return
        except urllib.error.HTTPError as e:
            errs = json.loads(e.read().decode(errors="replace")).get("errors", [])
        degisti = False
        for x in errs:
            m = re.search(r"attribute '(\w+)'", x.get("detail", ""))
            if not m or m.group(1) not in attrs:
                continue
            k, d = m.group(1), x.get("detail", "")
            if "Expected a BOOLEAN" in d:
                attrs[k] = False; degisti = True
            elif "Expected a STRING" in d or "Expected one of" in d:
                if attrs[k] != "NONE":
                    attrs[k] = "NONE"; degisti = True
            else:
                attrs.pop(k); degisti = True
        if not degisti:
            print("  ! yaş derecelendirmesi:", " | ".join(f"{x.get('title')}: {x.get('detail')}" for x in errs)[:800])
            return
    print("  ! yaş derecelendirmesi girilemedi")


def surum_yerel(app, ver_id):
    loc = next((l for l in (api("GET", f"/appStoreVersions/{ver_id}/appStoreVersionLocalizations") or {}).get("data", [])
                if l["attributes"]["locale"].startswith(LOCALE)), None)
    attrs = {"description": app["desc"], "keywords": app["keywords"], "promotionalText": app["promo"], "supportUrl": app["support"]}
    if app.get("marketing"):
        attrs["marketingUrl"] = app["marketing"]
    if loc:
        ok = api("PATCH", f"/appStoreVersionLocalizations/{loc['id']}", {"data": {"type": "appStoreVersionLocalizations", "id": loc["id"], "attributes": attrs}})
    else:
        res = api("POST", "/appStoreVersionLocalizations", {"data": {"type": "appStoreVersionLocalizations", "attributes": dict(attrs, locale="tr"),
                  "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": ver_id}}}}})
        ok = res
        loc = res["data"] if res else None
    if ok:
        print("  açıklama, anahtar kelimeler, tanıtım metni, destek adresi")
    return loc


def ekranlar(key, loc_id):
    ekran_seti(KOK / key, "APP_IPHONE_67", loc_id)
    if (KOK / key / "ipad").is_dir():
        ekran_seti(KOK / key / "ipad", "APP_IPAD_PRO_3GEN_129", loc_id)


def ekran_seti(klasor, tip, loc_id):
    files = sorted(klasor.glob("*.png"))
    if not files:
        return
    from PIL import Image
    w, h = Image.open(files[0]).size
    sets = (api("GET", f"/appStoreVersionLocalizations/{loc_id}/appScreenshotSets") or {}).get("data", [])
    s = next((x for x in sets if x["attributes"]["screenshotDisplayType"] == tip), None)
    if not s:
        res = api("POST", "/appScreenshotSets", {"data": {"type": "appScreenshotSets", "attributes": {"screenshotDisplayType": tip},
                  "relationships": {"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": loc_id}}}}})
        if not res:
            return
        s = res["data"]
    for old in (api("GET", f"/appScreenshotSets/{s['id']}/appScreenshots") or {}).get("data", []):
        api("DELETE", f"/appScreenshots/{old['id']}")
    n = 0
    for f in files:
        data = f.read_bytes()
        res = api("POST", "/appScreenshots", {"data": {"type": "appScreenshots", "attributes": {"fileName": f.name, "fileSize": len(data)},
                  "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": s["id"]}}}}})
        if not res:
            continue
        shot = res["data"]
        for op in shot["attributes"]["uploadOperations"]:
            part = data[op["offset"]:op["offset"] + op["length"]]
            req = urllib.request.Request(op["url"], method=op["method"], data=part,
                                         headers={h["name"]: h["value"] for h in op.get("requestHeaders", [])})
            urllib.request.urlopen(req).read()
        if api("PATCH", f"/appScreenshots/{shot['id']}", {"data": {"type": "appScreenshots", "id": shot["id"],
               "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()}}}):
            n += 1
    print(f"  ekran görüntüleri {tip}: {n}/{len(files)} ({w}x{h})")


def derleme(app_id, ver_id):
    b = tek(f"/builds?filter[app]={app_id}&filter[processingState]=VALID&sort=-uploadedDate&limit=1")
    if not b:
        print("  ! geçerli derleme yok (TestFlight'ta işleniyor olabilir)")
        return
    if api("PATCH", f"/appStoreVersions/{ver_id}/relationships/build", {"data": {"type": "builds", "id": b["id"]}}) is not None:
        print("  derleme seçildi:", b["attributes"]["version"])


def fiyat(app_id):
    if (api("GET", f"/apps/{app_id}/appPriceSchedule", quiet=True) or {}).get("data"):
        sched = api("GET", f"/apps/{app_id}/appPriceSchedule/manualPrices?limit=1", quiet=True) or {}
        if sched.get("data"):
            print("  fiyat zaten ayarlı")
            return
    pts = (api("GET", f"/apps/{app_id}/appPricePoints?filter[territory]=USA&limit=200") or {}).get("data", [])
    free = next((p for p in pts if float(p["attributes"].get("customerPrice") or 0) == 0), None)
    if not free:
        print("  ! ücretsiz fiyat noktası bulunamadı")
        return
    body = {"data": {"type": "appPriceSchedules", "relationships": {
                "app": {"data": {"type": "apps", "id": app_id}},
                "baseTerritory": {"data": {"type": "territories", "id": "USA"}},
                "manualPrices": {"data": [{"type": "appPrices", "id": "${f0}"}]}}},
            "included": [{"type": "appPrices", "id": "${f0}", "attributes": {"startDate": None},
                          "relationships": {"appPricePoint": {"data": {"type": "appPricePoints", "id": free["id"]}}}}]}
    if api("POST", "/appPriceSchedules", body):
        print("  fiyat: ücretsiz")


def uygunluk(app_id):
    if (api("GET", f"/apps/{app_id}/appAvailabilityV2", quiet=True) or {}).get("data"):
        print("  ülkeler zaten ayarlı")
        return
    terr = []
    url = "/territories?limit=200"
    while url:
        r = api("GET", url) or {}
        terr += [t["id"] for t in r.get("data", [])]
        url = (r.get("links") or {}).get("next")
    inc = [{"type": "territoryAvailabilities", "id": f"${{{t}}}", "attributes": {"available": True},
            "relationships": {"territory": {"data": {"type": "territories", "id": t}}}} for t in terr]
    body = {"data": {"type": "appAvailabilities", "attributes": {"availableInNewTerritories": True},
                     "relationships": {"app": {"data": {"type": "apps", "id": app_id}},
                                       "territoryAvailabilities": {"data": [{"type": "territoryAvailabilities", "id": i["id"]} for i in inc]}}},
            "included": inc}
    if api("POST", "/v2/appAvailabilities", body):
        print(f"  ülkeler: {len(terr)} ülkede açık")


def inceleme(ver_id):
    det = (api("GET", f"/appStoreVersions/{ver_id}/appStoreReviewDetail", quiet=True) or {}).get("data")
    attrs = dict(ILETISIM, demoAccountRequired=False, notes=NOTLAR)
    if det:
        ok = api("PATCH", f"/appStoreReviewDetails/{det['id']}", {"data": {"type": "appStoreReviewDetails", "id": det["id"], "attributes": attrs}})
    else:
        ok = api("POST", "/appStoreReviewDetails", {"data": {"type": "appStoreReviewDetails", "attributes": attrs,
                 "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": ver_id}}}}})
    if ok:
        print("  inceleme iletişim bilgisi")


secim = os.environ.get("UYGULAMALAR", "hepsi").split()
kayit = json.loads((KOK / "magaza.json").read_text(encoding="utf-8"))
if secim and secim[0] == "gonder":
    # incelemeye gönder: gonder [anahtarlar...]
    hedef = secim[1:] or list(kayit)
    for key in hedef:
        app = kayit[key]
        a = tek(f"/apps?filter[bundleId]={app['bundle']}&limit=1")
        vers = (api("GET", f"/apps/{a['id']}/appStoreVersions?filter[platform]=IOS&limit=3") or {}).get("data", [])
        ver = next((v for v in vers if v["attributes"]["appStoreState"] in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED")), None)
        if not ver:
            print(f"{key}: gönderilecek sürüm yok ({', '.join(v['attributes']['appStoreState'] for v in vers)})")
            continue
        subs = (api("GET", f"/reviewSubmissions?filter[app]={a['id']}&filter[platform]=IOS&filter[state]=READY_FOR_REVIEW,UNRESOLVED_ISSUES&limit=1") or {}).get("data", [])
        if subs:
            sub = subs[0]
        else:
            r = api("POST", "/reviewSubmissions", {"data": {"type": "reviewSubmissions", "attributes": {"platform": "IOS"},
                    "relationships": {"app": {"data": {"type": "apps", "id": a["id"]}}}}})
            if not r:
                print(f"{key}: gönderim açılamadı"); continue
            sub = r["data"]
        items = (api("GET", f"/reviewSubmissions/{sub['id']}/items", quiet=True) or {}).get("data", [])
        if not items:
            if api("POST", "/reviewSubmissionItems", {"data": {"type": "reviewSubmissionItems",
                   "relationships": {"reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sub["id"]}},
                                     "appStoreVersion": {"data": {"type": "appStoreVersions", "id": ver["id"]}}}}}) is None:
                print(f"{key}: sürüm gönderime eklenemedi (yukarıdaki hataya bakın)"); continue
        if api("PATCH", f"/reviewSubmissions/{sub['id']}", {"data": {"type": "reviewSubmissions", "id": sub["id"],
               "attributes": {"submitted": True}}}) is not None:
            print(f"{key}: İNCELEMEYE GÖNDERİLDİ")
        else:
            print(f"{key}: gönderilemedi (yukarıdaki hataya bakın)")
    raise SystemExit
if secim == ["durum"]:
    # yalnızca okur: her uygulamanın sürüm durumu ve inceleme gönderimleri
    for key, app in kayit.items():
        a = tek(f"/apps?filter[bundleId]={app['bundle']}&limit=1")
        if not a:
            print(f"{key}: kayıt yok")
            continue
        vers = (api("GET", f"/apps/{a['id']}/appStoreVersions?filter[platform]=IOS&limit=3") or {}).get("data", [])
        sv = ", ".join(f"{v['attributes']['versionString']}={v['attributes']['appStoreState']}" for v in vers) or "sürüm yok"
        subs = (api("GET", f"/reviewSubmissions?filter[app]={a['id']}&limit=5", quiet=True) or {}).get("data", [])
        ss = ", ".join(f"{x['attributes'].get('state')}@{(x['attributes'].get('submittedDate') or '')[:16]}" for x in subs) or "gönderim yok"
        print(f"{key}: {sv} | inceleme: {ss}")
    raise SystemExit
for key, app in kayit.items():
    if secim != ["hepsi"] and key not in secim:
        continue
    print(f"\n== {key} ({app['bundle']})")
    a = tek(f"/apps?filter[bundleId]={app['bundle']}&limit=1")
    if not a:
        print("  ! App Store Connect'te uygulama kaydı yok, atlandı")
        continue
    app_id = a["id"]
    api("PATCH", f"/apps/{app_id}", {"data": {"type": "apps", "id": app_id, "attributes": {
        "contentRightsDeclaration": "USES_THIRD_PARTY_CONTENT" if app.get("third_party") else "DOES_NOT_USE_THIRD_PARTY_CONTENT"}}})
    infos = (api("GET", f"/apps/{app_id}/appInfos") or {}).get("data", [])
    info = next((i for i in infos if i["attributes"].get("appStoreState") in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", None)
                 or i["attributes"].get("state") in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED")), infos[0] if infos else None)
    if info:
        kategori(app, info["id"])
        bilgi_yerel(app, info["id"])
        yas(info["id"])
    vers = (api("GET", f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS&limit=5") or {}).get("data", [])
    ver = next((v for v in vers if v["attributes"]["appStoreState"] in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED")), None)
    if not ver:
        print("  ! düzenlenebilir sürüm yok")
        continue
    api("PATCH", f"/appStoreVersions/{ver['id']}", {"data": {"type": "appStoreVersions", "id": ver["id"],
        "attributes": {"copyright": TELIF, "releaseType": "AFTER_APPROVAL"}}})
    loc = surum_yerel(app, ver["id"])
    if loc:
        ekranlar(key, loc["id"])
    derleme(app_id, ver["id"])
    fiyat(app_id)
    uygunluk(app_id)
    inceleme(ver["id"])
print("\nBitti. Kalan: her uygulamada App Privacy formu ve 'Add for Review'.")
