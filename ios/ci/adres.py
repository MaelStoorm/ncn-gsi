"""App Store'daki destek ve tanıtım adreslerini ios/magaza/magaza.json'dakilerle günceller.
Yalnızca bu iki adrese dokunur; düzenlenebilir durumdaki sürümlerin tüm dillerinde değiştirir.
Gerekenler: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8."""
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
LOCALE = "tr"


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



KOK = Path(__file__).resolve().parent.parent / "magaza"
DUZENLENIR = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED"}
apps = json.loads((KOK / "magaza.json").read_text())
# Bu listede olmayan, kendi deposundan yönetilen uygulamalar
apps["vitray"] = {"bundle": "com.vitrayatolyesi.oyun", "support": "https://maelstoorm.github.io/destek.html", "marketing": "https://maelstoorm.github.io/vitray-atolyesi/"}
for key, app in apps.items():
    if not isinstance(app, dict) or not app.get("bundle"):
        continue
    print(f"\n== {key} ({app['bundle']})")
    r = api("GET", f"/apps?filter[bundleId]={app['bundle']}") or {}
    if not r.get("data"):
        print("  App Store Connect'te kayıt yok")
        continue
    app_id = r["data"][0]["id"]
    vers = (api("GET", f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS&limit=10") or {}).get("data", [])
    for v in vers:
        st = v["attributes"]["appStoreState"]
        print(f"  sürüm {v['attributes']['versionString']}: {st}")
        if st not in DUZENLENIR:
            continue
        for loc in (api("GET", f"/appStoreVersions/{v['id']}/appStoreVersionLocalizations") or {}).get("data", []):
            attrs = {"supportUrl": app["support"]}
            if app.get("marketing"):
                attrs["marketingUrl"] = app["marketing"]
            ok = api("PATCH", f"/appStoreVersionLocalizations/{loc['id']}", {"data": {"type": "appStoreVersionLocalizations", "id": loc["id"], "attributes": attrs}})
            print(f"    {loc['attributes']['locale']}: {'güncellendi' if ok else 'güncellenemedi'}")
