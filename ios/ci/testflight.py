"""Bütün uygulamalarda TestFlight'ın dahili test grubunu kurar (GitHub Actions'ta elle çalıştırılır).

Her uygulama için "Ben" adlı dahili grup açılır (yoksa), bütün derlemeler otomatik olarak bu gruba
gider ve App Store Connect hesabının sahibi (Account Holder) gruba test kullanıcısı olarak eklenir.
Gerekenler: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8 ve BUNDLE_IDS (boşlukla ayrılmış).
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

API = "https://api.appstoreconnect.apple.com/v1"
KEY_ID = os.environ["ASC_KEY_ID"].strip()
ISSUER = os.environ["ASC_ISSUER_ID"].strip()
P8 = os.environ["ASC_KEY_P8"].strip().encode()
GROUP = "Ben"


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def token():
    key = serialization.load_pem_private_key(P8, password=None)
    head = b64u(json.dumps({"alg": "ES256", "kid": KEY_ID, "typ": "JWT"}).encode())
    now = int(time.time())
    body = b64u(json.dumps({"iss": ISSUER, "iat": now, "exp": now + 900, "aud": "appstoreconnect-v1"}).encode())
    r, s = decode_dss_signature(key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{head}.{body}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def api(method, path, data=None, ok409=False):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if ok409 and e.code == 409:
            print("  (zaten var)", detail[:200])
            return None
        print(f"::warning::{method} {path} -> {e.code} {detail[:400]}")
        return None


# Hesap sahibini bul
users = api("GET", "/users?limit=50") or {"data": []}
owner = next((u for u in users["data"] if "ACCOUNT_HOLDER" in u["attributes"].get("roles", [])),
             users["data"][0] if users["data"] else None)
if not owner:
    sys.exit("::error::App Store Connect kullanıcısı bulunamadı")
email = owner["attributes"]["username"]
first, last = owner["attributes"].get("firstName", ""), owner["attributes"].get("lastName", "")
print(f"Test kullanıcısı: {first} {last} <{email}>")

for bundle in os.environ["BUNDLE_IDS"].split():
    print(f"\n== {bundle}")
    apps = (api("GET", f"/apps?filter[bundleId]={bundle}&limit=1") or {}).get("data", [])
    if not apps:
        print(f"::warning::{bundle} için App Store Connect'te uygulama kaydı yok, atlandı")
        continue
    app = apps[0]
    print("  uygulama:", app["attributes"]["name"])
    groups = (api("GET", f"/apps/{app['id']}/betaGroups?limit=50") or {}).get("data", [])
    group = next((g for g in groups if g["attributes"]["name"] == GROUP), None)
    if not group:
        res = api("POST", "/betaGroups", {"data": {"type": "betaGroups", "attributes": {
            "name": GROUP, "isInternalGroup": True, "hasAccessToAllBuilds": True},
            "relationships": {"app": {"data": {"type": "apps", "id": app["id"]}}}}})
        if not res:
            continue
        group = res["data"]
        print("  grup oluşturuldu (bütün derlemeler otomatik gelir)")
    else:
        print("  grup zaten var")
    testers = (api("GET", f"/betaGroups/{group['id']}/betaTesters?limit=50") or {}).get("data", [])
    if any(t["attributes"].get("email", "").lower() == email.lower() for t in testers):
        print("  test kullanıcısı zaten grupta")
        continue
    res = api("POST", "/betaTesters", {"data": {"type": "betaTesters",
              "attributes": {"email": email, "firstName": first, "lastName": last},
              "relationships": {"betaGroups": {"data": [{"type": "betaGroups", "id": group["id"]}]}}}}, ok409=True)
    if res is None:
        # kullanıcı başka bir grupta zaten kayıtlıysa bu gruba ekle
        found = (api("GET", f"/betaTesters?filter[email]={email}&limit=1") or {}).get("data", [])
        if found:
            api("POST", f"/betaGroups/{group['id']}/relationships/betaTesters",
                {"data": [{"type": "betaTesters", "id": found[0]["id"]}]})
            print("  test kullanıcısı gruba eklendi")
    else:
        print("  test kullanıcısı eklendi")
