#!/usr/bin/env bash
# Build the deployable Photo Addendum site into an output folder:
#   index.html (app template with jsPDF 2.5.1 inlined so PDFs work offline),
#   sw.js, manifest.webmanifest and the icons.
# Usage: bash tools/build.sh [output_dir]   (default: the repo root, i.e. the deployed site)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/.."
OUT="${1:-$ROOT}"
mkdir -p "$OUT"
WORK="$(mktemp -d)"
LIB=""
if (cd "$WORK" && npm init -y >/dev/null 2>&1 && npm install jspdf@2.5.1 --no-save --silent >/dev/null 2>&1); then
  LIB="$WORK/node_modules/jspdf/dist/jspdf.umd.min.js"
fi
if [ -z "$LIB" ] || [ ! -f "$LIB" ]; then
  echo "npm unavailable — extracting jsPDF from v3/index.html instead"
  python3 - "$ROOT/v3/index.html" "$WORK/jspdf.umd.min.js" <<'PY'
import re, sys
html = open(sys.argv[1], encoding='utf-8').read()
m = re.search(r'<!-- jsPDF \(inlined for offline use\) -->\s*<script>(.*?)</script>', html, re.S)
assert m, 'could not find inlined jsPDF in v3/index.html'
open(sys.argv[2], 'w', encoding='utf-8').write(m.group(1).replace('<\\/script>', '</script>'))
PY
  LIB="$WORK/jspdf.umd.min.js"
fi
python3 - "$ROOT/src/app-template.html" "$LIB" "$OUT/index.html" <<'PY'
import sys
template, lib_path, out = sys.argv[1:4]
lib = open(lib_path, encoding='utf-8').read().replace('</script>', '<\\/script>')
html = open(template, encoding='utf-8').read()
assert '/*__JSPDF_LIB__*/' in html, 'marker /*__JSPDF_LIB__*/ missing in template'
open(out, 'w', encoding='utf-8').write(html.replace('/*__JSPDF_LIB__*/', lib))
print('wrote', out)
PY
cp "$ROOT/src/sw.js" "$ROOT/src/manifest.webmanifest" "$OUT/"
python3 "$HERE/make_icons.py" "$OUT" >/dev/null
rm -rf "$WORK"
echo "Built into $OUT:"; ls -la "$OUT"
