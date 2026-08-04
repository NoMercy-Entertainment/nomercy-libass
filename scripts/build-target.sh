#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Build libass and its three dependencies for ONE target.
#
#   scripts/build-target.sh linux-x86-64
#   scripts/build-target.sh windows-x86-64
#   scripts/build-target.sh android-arm64-v8a
#   scripts/build-target.sh wasm
#
# Every target runs the same four builds in the same order against the same
# sources; only the toolchain file differs. That is the single origin: a
# subtitle drawn in a browser and one drawn on a television came out of the same
# code, compiled the same way.
#
# The dependency order is not a preference. harfbuzz wants freetype, libass
# wants all three, and building them in any other order silently produces a
# libass with shaping or bidi missing — which renders Latin correctly and drops
# Arabic and Japanese, the exact failure that is invisible until somebody who
# reads the language looks at it.
set -euo pipefail

TARGET="${1:?usage: build-target.sh <target>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/build/src"
OUT="$ROOT/build/out/$TARGET"
PREFIX="$ROOT/build/prefix/$TARGET"
CROSS="$ROOT/cross/$TARGET.ini"

[ -d "$SRC/libass" ] || { echo "run scripts/fetch.sh first" >&2; exit 2; }
[ -f "$CROSS" ] || { echo "no cross file for $TARGET at $CROSS" >&2; exit 2; }

mkdir -p "$OUT" "$PREFIX"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"

# Static dependencies, one shared libass. A consumer links one file and gets
# freetype, fribidi and harfbuzz inside it at the versions this repo pinned —
# rather than whatever the host happens to have, which is how a build works on a
# developer's machine and not on a user's.
meson_build() {
    local name="$1"
    shift
    echo "== $TARGET / $name"
    rm -rf "$OUT/$name"
    meson setup "$OUT/$name" "$SRC/$name" \
        --cross-file "$CROSS" \
        --prefix "$PREFIX" \
        --default-library static \
        --buildtype release \
        "$@"
    meson compile -C "$OUT/$name"
    meson install -C "$OUT/$name"
}

meson_build freetype -Dharfbuzz=disabled -Dbrotli=disabled -Dbzip2=disabled -Dpng=disabled
meson_build fribidi -Ddocs=false -Dbin=false
meson_build harfbuzz -Dfreetype=enabled -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dtests=disabled -Ddocs=disabled
meson_build libass -Ddefault_library=shared -Dfontconfig=disabled -Dasm=enabled

echo "== built $TARGET -> $PREFIX"
find "$PREFIX/lib" -maxdepth 1 -name 'libass*' -print
