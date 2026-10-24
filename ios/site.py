"""iOS uygulamasının içine konacak sayfayı hazırlar (derleme sırasında çalışır).

  python3 ios/site.py --html app/src/main/assets/index.html --out ios/gen/Jalon/site

Sayfa olduğu gibi kopyalanır; yalnızca Android sürümüne ait bölümler
(/*android:start*/ ... /*android:end*/ ve <!--android:start--> ... <!--android:end-->) iOS kopyasına hiç girmez.
"""
import argparse
import re
import shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--html", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

out = Path(a.out)
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)


def strip_android(text, name):
    pats = [(r"/\*android:start\*/", r"/\*android:end\*/"), (r"<!--android:start-->", r"<!--android:end-->")]
    for a_, b_ in pats:
        if len(re.findall(a_, text)) != len(re.findall(b_, text)):
            raise SystemExit(f"{name}: android:start/end işaretleri eşleşmiyor")
        text = re.sub(a_ + r"[\s\S]*?" + b_, "", text)
    return text


html = strip_android(Path(a.html).read_text(encoding="utf-8"), a.html)
(out / "index.html").write_text(html, encoding="utf-8")
print(f"{out}: {sum(1 for _ in out.rglob('*'))} dosya")
