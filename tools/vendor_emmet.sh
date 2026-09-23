#!/bin/sh
# Re-vendor the py-emmet core library into ./emmet from its PyPI wheel.
#
# Usage: tools/vendor_emmet.sh [VERSION]
#
# The wheel's SHA-256 is checked against the digest PyPI publishes for it.
# The vendored code is never edited by hand: bump the version here and rerun.
# Source: https://pypi.org/project/py-emmet/ (https://github.com/emmetio/py-emmet)
set -eu

VERSION="${1:-1.3.1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 - "$VERSION" "$TMP" <<'PY'
import hashlib, json, sys, urllib.request
version, tmp = sys.argv[1], sys.argv[2]
with urllib.request.urlopen(f"https://pypi.org/pypi/py-emmet/{version}/json", timeout=30) as r:
    meta = json.load(r)
wheel = next(u for u in meta["urls"] if u["packagetype"] == "bdist_wheel")
with urllib.request.urlopen(wheel["url"], timeout=60) as r:
    data = r.read()
digest = hashlib.sha256(data).hexdigest()
if digest != wheel["digests"]["sha256"]:
    sys.exit(f"sha256 mismatch for {wheel['filename']}: {digest}")
with open(f"{tmp}/py_emmet.whl", "wb") as f:
    f.write(data)
print(f"{wheel['filename']} sha256={digest}")
PY

cd "$TMP"
python3 -m zipfile -e py_emmet.whl unpacked
rm -rf "$ROOT/emmet"
cp -R unpacked/emmet "$ROOT/emmet"
cp unpacked/py_emmet-*.dist-info/LICENSE "$ROOT/emmet/LICENSE"
find "$ROOT/emmet" -name '__pycache__' -prune -exec rm -rf {} +
echo "py-emmet $VERSION vendored into $ROOT/emmet"
