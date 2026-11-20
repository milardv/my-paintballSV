#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f build/web/index.html ]; then
  unity build unity --target WebGL --execute-method PaintballScene.BuildWeb
fi
exec python3 -m http.server 8086 --bind 127.0.0.1 --directory build/web
