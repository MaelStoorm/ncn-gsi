"""App Store Connect hazırlığı (GitHub Actions'ta çalışır).

Yaptıkları:
  1. Paket kimliğini (bundle ID) Apple'da kaydeder, yoksa oluşturur; ekip kimliğini (Team ID) buradan öğrenir.
  2. Ortak dağıtım sertifikasını getirir. Sertifika ve anahtarı, ASC_KEY_P8'den türetilen anahtarla şifrelenip
     MaelStoorm/ncn-gsi deposunun "ios-imza" dalında tek dosya olarak durur; Jalon, Deprem Atlası ve Pafta aynı
     sertifikayı kullanır. Böylece her derlemede yeni sertifika oluşmaz ve Apple'ın sertifika sınırı dolmaz.
     Dosya yoksa ya da sertifika artık geçerli değilse yenisi oluşturulur ve dala yazılır.
  3. Bu uygulama için App Store imza profilini hazırlar ve kurar.
  4. App Store Connect'te uygulama kaydı olup olmadığına bakar (yoksa yükleme atlanır, derleme yine yapılır).

Gerekenler (ortam değişkenleri): ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8, BUNDLE_ID, APP_NAME
Çıktılar GITHUB_ENV'e yazılır: TEAM_ID, PROFILE_NAME, APP_EXISTS, SIGN_KEY, SIGN_CERT
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID

API = "https://api.appstoreconnect.apple.com/v1"
SHARED_REPO = "MaelStoorm/ncn-gsi"
SHARED_BRANCH = "ios-imza"
SHARED_FILE = "imza.bin"

KEY_ID = os.environ["ASC_KEY_ID"].strip()
ISSUER = os.environ["ASC_ISSUER_ID"].strip()
P8 = os.environ["ASC_KEY_P8"].strip().encode()
BUNDLE_ID = os.environ["BUNDLE_ID"].strip()
APP_NAME = os.environ["APP_NAME"].strip()
TMP = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
REPO = os.environ.get("GITHUB_REPOSITORY", "")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def fail(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def token():
    key = serialization.load_pem_private_key(P8, password=None)
    head = b64u(json.dumps({"alg": "ES256", "kid": KEY_ID, "typ": "JWT"}).encode())
    now = int(time.time())
    body = b64u(json.dumps({"iss": ISSUER, "iat": now, "exp": now + 900, "aud": "appstoreconnect-v1"}).encode())
    r, s = decode_dss_signature(key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{head}.{body}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def api(method, path, data=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if e.code == 401:
            fail("Apple anahtarı kabul edilmedi (401). ASC_KEY_ID, ASC_ISSUER_ID ve ASC_KEY_P8 değerlerini kontrol edin.")
        if e.code == 403:
            fail("Apple anahtarının yetkisi yetmiyor (403). Anahtar 'Admin' rolüyle oluşturulmalı. Ayrıntı: " + detail)
        fail(f"App Store Connect isteği başarısız: {method} {path} -> {e.code} {detail}")


def env_out(**kv):
    with open(os.environ.get("GITHUB_ENV", TMP / "env.txt"), "a") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")
            print(f"{k}={v if k not in ('SIGN_KEY',) else '***'}")


# ---------- 1. Paket kimliği ve ekip kimliği ----------
def bundle():
    found = [b for b in api("GET", f"/bundleIds?filter[identifier]={BUNDLE_ID}&limit=200")["data"]
             if b["attributes"]["identifier"] == BUNDLE_ID]
    if found:
        b = found[0]
    else:
        print(f"{BUNDLE_ID} Apple'da kaydediliyor...")
        b = api("POST", "/bundleIds", {"data": {"type": "bundleIds", "attributes": {
            "identifier": BUNDLE_ID, "name": APP_NAME, "platform": "IOS"}}})["data"]
    return b["id"], b["attributes"]["seedId"]


# ---------- 2. Ortak dağıtım sertifikası ----------
def box_key():
    return hashlib.sha256(P8 + b"|ios-imza|v1").digest()


def load_shared():
    url = f"https://raw.githubusercontent.com/{SHARED_REPO}/{SHARED_BRANCH}/{SHARED_FILE}"
    try:
        with urllib.request.urlopen(url) as r:
            blob = r.read()
        plain = AESGCM(box_key()).decrypt(blob[:12], blob[12:], None)
        return json.loads(plain)
    except Exception as e:  # yok, ya da başka bir Apple anahtarıyla şifrelenmiş
        print(f"Ortak sertifika kullanılamadı ({type(e).__name__}); gerekirse yenisi oluşturulacak.")
        return None


def cert_valid(cert_id):
    req = urllib.request.Request(f"{API}/certificates/{cert_id}", headers={"Authorization": f"Bearer {token()}"})
    try:
        with urllib.request.urlopen(req) as res:
            attrs = json.loads(res.read())["data"]["attributes"]
            exp = attrs.get("expirationDate", "")
            return exp > time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 7 * 86400))
    except urllib.error.HTTPError:
        return False


def create_cert():
    if REPO.lower() != SHARED_REPO.lower():
        fail(f"Ortak sertifika bulunamadı. Önce {SHARED_REPO} deposunda iOS derlemesini bir kez çalıştırın.")
    print("Yeni dağıtım sertifikası oluşturuluyor...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = (x509.CertificateSigningRequestBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MaelStoorm CI"),
                                    x509.NameAttribute(NameOID.COUNTRY_NAME, "TR")]))
           .sign(key, hashes.SHA256()))
    pem_csr = csr.public_bytes(serialization.Encoding.PEM).decode()
    res = api("POST", "/certificates", {"data": {"type": "certificates", "attributes": {
        "certificateType": "DISTRIBUTION", "csrContent": pem_csr}}})["data"]
    shared = {
        "id": res["id"],
        "cert": res["attributes"]["certificateContent"],
        "key": key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                 serialization.NoEncryption()).decode(),
    }
    nonce = os.urandom(12)
    blob = nonce + AESGCM(box_key()).encrypt(nonce, json.dumps(shared).encode(), None)
    d = TMP / "ios-imza"
    d.mkdir(exist_ok=True)
    (d / SHARED_FILE).write_bytes(blob)
    (d / "BENIOKU.md").write_text(
        "Jalon, Deprem Atlası ve Pafta'nın iOS derlemelerinde kullanılan ortak Apple dağıtım sertifikası.\n"
        "Dosya, GitHub'daki ASC_KEY_P8 gizli değerinden türetilen anahtarla AES-256-GCM ile şifrelidir.\n"
        "Bu dal derleme tarafından otomatik yazılır, elle değiştirmeyin.\n", encoding="utf-8")
    url = f"https://x-access-token:{GH_TOKEN}@github.com/{REPO}.git"
    run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)
    run("git", "init", "-q", "-b", SHARED_BRANCH)
    run("git", "config", "user.name", "github-actions")
    run("git", "config", "user.email", "github-actions@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "Ortak iOS dağıtım sertifikası")
    run("git", "push", "-f", url, SHARED_BRANCH)
    return shared


def certificate():
    shared = load_shared()
    if shared and cert_valid(shared["id"]):
        print("Ortak dağıtım sertifikası kullanılıyor.")
        return shared
    return create_cert()


# ---------- 3. İmza profili ----------
def profile(bundle_pk, cert_id):
    name = f"{APP_NAME} App Store CI"
    res = api("GET", f"/profiles?filter[name]={urllib.parse.quote(name)}&include=certificates&limit=50")
    chosen = None
    for p in res.get("data", []):
        certs = [c["id"] for c in p["relationships"]["certificates"]["data"]]
        if p["attributes"]["profileState"] == "ACTIVE" and cert_id in certs and p["attributes"]["name"] == name:
            chosen = p
        else:
            api("DELETE", f"/profiles/{p['id']}")
    if not chosen:
        print("İmza profili oluşturuluyor...")
        chosen = api("POST", "/profiles", {"data": {"type": "profiles",
            "attributes": {"name": name, "profileType": "IOS_APP_STORE"},
            "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": bundle_pk}},
                              "certificates": {"data": [{"type": "certificates", "id": cert_id}]}}}})["data"]
    content = base64.b64decode(chosen["attributes"]["profileContent"])
    uuid = chosen["attributes"]["uuid"]
    for d in (Path.home() / "Library/MobileDevice/Provisioning Profiles",
              Path.home() / "Library/Developer/Xcode/UserData/Provisioning Profiles"):
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{uuid}.mobileprovision").write_bytes(content)
    return name


# ---------- 4. Uygulama kaydı ----------
def app_exists():
    return bool(api("GET", f"/apps?filter[bundleId]={BUNDLE_ID}&limit=1").get("data"))


bundle_pk, team = bundle()
shared = certificate()
key_file, cert_file = TMP / "dist.key.pem", TMP / "dist.cer"
key_file.write_text(shared["key"])
cert_file.write_bytes(base64.b64decode(shared["cert"]))
prof = profile(bundle_pk, shared["id"])
exists = app_exists()
if not exists:
    print(f"::warning::App Store Connect'te {BUNDLE_ID} için uygulama kaydı yok. Uygulama derlenecek ama yüklenmeyecek. "
          f"App Store Connect > Uygulamalar > + > Yeni Uygulama ile '{BUNDLE_ID}' paket kimliğini seçerek kaydı oluşturun, "
          f"sonra bu derlemeyi yeniden çalıştırın.")
env_out(TEAM_ID=team, PROFILE_NAME=prof, APP_EXISTS="1" if exists else "0",
        SIGN_KEY=str(key_file), SIGN_CERT=str(cert_file))
