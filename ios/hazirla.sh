#!/bin/bash
# iOS uygulamasının sayfasını hazırlar ve içeriğini denetler (GitHub Actions'ta derlemeden önce çalışır).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 ios/site.py --html app/src/main/assets/index.html --out ios/gen/Jalon/site
python3 ios/denetle.py ios/gen/Jalon/site ios/Jalon ios/project.yml
