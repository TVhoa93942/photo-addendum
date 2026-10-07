#!/usr/bin/env bash
# Build into a temp folder, generate fixtures, and run the full test suite:
#   tests/wk_test.py     — WebKit (Safari's engine) at iPhone + iPad size: walkthrough, v3 upgrade, offline
#   tests/touch_test.py  — real touch input (Chromium, iPhone emulation): swipes, double-tap zoom, finger signature
#   tests/stress_test.py — 240-photo inspection: save speed, PDF and backup size
# One-time setup on Ubuntu:
#   apt-get install -y webkit2gtk-driver xvfb
#   pip install selenium playwright && python3 -m playwright install chromium
# Usage: bash tests/run_all.sh [output_dir]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/test-output}"
WWW="$(mktemp -d)"
bash "$ROOT/tools/build.sh" "$WWW" >/dev/null
python3 "$ROOT/tests/make_fixtures.py" "$WWW/fx" >/dev/null
if ! pgrep -x Xvfb >/dev/null; then (Xvfb :99 -screen 0 1600x1400x24 >/dev/null 2>&1 &); sleep 1; fi
export DISPLAY=:99 WWW FX="$WWW/fx"
status=0
python3 "$ROOT/tests/wk_test.py" http://127.0.0.1:8765/ "$OUT/webkit" all || status=1
(cd "$WWW" && exec python3 -m http.server 8765 --bind 127.0.0.1 >/dev/null 2>&1) & SRV=$!
sleep 1
python3 "$ROOT/tests/touch_test.py" http://127.0.0.1:8765/ "$OUT/touch" || status=1
python3 "$ROOT/tests/stress_test.py" http://127.0.0.1:8765/ "$OUT/stress" || status=1
kill $SRV 2>/dev/null || true
rm -rf "$WWW"
echo; [ $status -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED — see output above"
exit $status
