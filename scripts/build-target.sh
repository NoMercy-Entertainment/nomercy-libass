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

# meson reads a cross file literally: "$NDK_BIN/aarch64-linux-android29-clang"
# is the NAME of a compiler it then cannot find, not a path it expands. Every
# Android job failed with "Unknown compiler(s)" on exactly that. So the file is
# resolved into build/ with the environment substituted, and the checked-in one
# stays readable with the variable in it.
if grep -q '\$NDK_BIN' "$CROSS"; then
    [ -n "${NDK_BIN:-}" ] || { echo "NDK_BIN is not set and $TARGET needs it" >&2; exit 2; }
    mkdir -p "$ROOT/build/cross"
    RESOLVED="$ROOT/build/cross/$TARGET.ini"
    sed "s|\$NDK_BIN|$NDK_BIN|g" "$CROSS" > "$RESOLVED"
    CROSS="$RESOLVED"
fi

ASM_TARGETS="linux-x86-64 android-arm64-v8a android-x86_64"

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
        --pkg-config-path "$PREFIX/lib/pkgconfig" \
        --buildtype release \
        "$@"
    meson compile -C "$OUT/$name"
    meson install -C "$OUT/$name"
}

meson_build freetype -Ddefault_library=static -Dwerror=false -Dharfbuzz=disabled -Dbrotli=disabled -Dbzip2=disabled -Dpng=disabled
meson_build fribidi -Ddefault_library=static -Dwerror=false -Ddocs=false -Dbin=false
# --werror off for the dependencies, on nothing of ours.
#
# harfbuzz builds with warnings-as-errors and newer clang added
# -Wunused-template, so hb-meta.hh fails on code upstream ships and considers
# fine. Treating a third party's warnings as our build gate means our pinned
# version stops building the day a runner's compiler updates — which is the
# opposite of the reproducibility this repo exists for.
meson_build harfbuzz -Ddefault_library=static -Dwerror=false -Dfreetype=enabled -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dtests=disabled -Ddocs=disabled
# No system font provider, and that is deliberate rather than a concession.
#
# libass insists on DirectWrite, Core Text or Fontconfig unless told otherwise,
# because a player that only renders fonts embedded in the subtitle is unusual.
# Ours is exactly that: SubtitlePlugin fetches every face the .ass names from
# the item's font manifest and hands them over with ass_add_font before the
# track loads. Linking a system provider would let a missing manifest entry
# resolve to whatever the machine happens to have, which renders the wrong
# typeface and reports nothing — the failure that is invisible until somebody
# who knows the show looks at it.
# Assembly where the toolchain can actually assemble it.
#
# arm64 Android built with -Dasm=enabled and every other target stopped at
# "Assembly was requested, but cannot be built": nasm on the runner does not
# serve armv7, wasm or a mingw cross, and libass turns a request it cannot
# honour into a hard failure rather than a fallback. ASM_TARGETS is the list
# that has been shown to build it; everything else takes the C path, which is
# slower per frame and correct, and RenderScheduler already keeps a static cue
# from being redrawn at all.
case " $ASM_TARGETS " in
    *" $TARGET "*) asm=enabled ;;
    *) asm=disabled ;;
esac

meson_build libass -Ddefault_library=shared -Dfontconfig=disabled -Dasm="$asm"     -Drequire-system-font-provider=false

echo "== built $TARGET -> $PREFIX"
find "$PREFIX/lib" -maxdepth 1 -name 'libass*' -print
