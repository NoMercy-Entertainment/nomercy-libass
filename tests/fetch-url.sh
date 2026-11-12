#!/usr/bin/env bash
# fetch.sh must build every download URL from versions.env, so a bump of
# FREETYPE_VERSION fetches that version and not a hardcoded tag.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/root/scripts" "$tmp/bin" "$tmp/seed/x"
cp "$ROOT/scripts/fetch.sh" "$tmp/root/scripts/fetch.sh"
: > "$tmp/seed/x/file"
tar -cf "$tmp/seed.tar" -C "$tmp/seed" x
sha="$(sha256sum "$tmp/seed.tar" | cut -d' ' -f1)"

cat > "$tmp/root/versions.env" <<EOF
LIBASS_VERSION=0.0.1
LIBASS_SHA256=$sha
FREETYPE_VERSION=9.9.9
FREETYPE_SHA256=$sha
FRIBIDI_VERSION=0.0.1
FRIBIDI_SHA256=$sha
HARFBUZZ_VERSION=0.0.1
HARFBUZZ_SHA256=$sha
EOF

# Fake curl: `curl -fsSL URL -o FILE`. Logs the URL, hands back the seed tar.
cat > "$tmp/bin/curl" <<EOF
#!/usr/bin/env bash
echo "\$2" >> "$tmp/urls"
cp "$tmp/seed.tar" "\$4"
EOF
chmod +x "$tmp/bin/curl"

PATH="$tmp/bin:$PATH" bash "$tmp/root/scripts/fetch.sh" > /dev/null
if grep 'freetype/archive/refs/tags/VER-9-9-9.tar.gz' "$tmp/urls" > /dev/null; then
    echo "PASS: freetype URL follows FREETYPE_VERSION"
else
    echo "FAIL: freetype URL ignores FREETYPE_VERSION: $(grep freetype "$tmp/urls")"
    exit 1
fi
