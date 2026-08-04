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

ASM_TARGETS="linux-x86-64 windows-x86-64 android-arm64-v8a"

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

# freetype's own zlib, not the host's.
#
# gzip support needs zlib.h, and on a runner that has one this quietly linked
# whatever the machine happened to provide — the exact drift this repo exists to
# end. mingw has none, so the Windows cross was the target that said so out
# loud. `internal` builds the copy freetype ships, identically on all seven.
meson_build freetype -Ddefault_library=static -Dwerror=false -Dzlib=internal -Dharfbuzz=disabled -Dbrotli=disabled -Dbzip2=disabled -Dpng=disabled
meson_build fribidi -Ddefault_library=static -Dwerror=false -Ddocs=false -Dbin=false
# harfbuzz promotes its own warnings, so werror is not the lever.
#
# hb.hh carries a block of `#pragma GCC diagnostic error` guarded by
# HB_NO_PRAGMA_GCC_DIAGNOSTIC_ERROR, so a newer clang adding -Wunused-template
# fails the build no matter what meson's werror says. Defining the guard is what
# actually stops our pinned version breaking the day a toolchain updates, which
# is the reproducibility this repo exists for. Nothing of ours compiles here, so
# no warning of ours is silenced.
meson_build harfbuzz -Ddefault_library=static -Dwerror=false -Dcpp_args=-DHB_NO_PRAGMA_GCC_DIAGNOSTIC_ERROR -Dfreetype=enabled -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dtests=disabled -Ddocs=disabled
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
# Assembly on every target whose toolchain has an assembler.
#
# x86 needs nasm, and nasm has to be named in the cross file: a cross build
# resolves binaries from that file alone, so an installed nasm is still "not
# found for the host machine". arm64 assembles through the NDK's own clang and
# needs nothing declared.
#
# android-x86_64 is the exception: Android mandates position-independent code
# and meson's Nasm compiler refuses it outright — "Language Nasm does not
# support position-independent executable" — with b_pie already false. armeabi-v7a
# and wasm have no assembly path in libass at all, and libass turns a request it cannot honour into a hard failure rather
# than a fallback, so they take the C path — slower per frame and identical in
# output, with RenderScheduler already keeping a static cue from being redrawn.
case " $ASM_TARGETS " in
    *" $TARGET "*) asm=enabled ;;
    *) asm=disabled ;;
esac

# Static for wasm, shared everywhere else.
#
# A browser cannot dlopen anything and ld.wasm says so outright — "does not
# support shared libraries". build-wasm-worker.sh links the archives into the
# worker itself, which is the artifact the web actually loads.
case "$TARGET" in
    # Apple ships an XCFramework of static slices — cinterop links libass into
    # the app rather than loading it — and a browser cannot dlopen anything.
    wasm|apple-*) libass_linkage=static ;;
    *) libass_linkage=shared ;;
esac

# CoreText off with the rest of them.
#
# libass enables it by default on Apple, which would let a font the manifest
# never named resolve to whatever the device happens to have — the one platform
# quietly disagreeing with the other six about which typeface a sign is drawn
# in, reported by nothing.
case "$TARGET" in
    apple-*) providers="-Dcoretext=disabled" ;;
    *) providers="" ;;
esac

meson_build libass -Ddefault_library="$libass_linkage" -Dfontconfig=disabled -Dasm="$asm" -Drequire-system-font-provider=false $providers

echo "== built $TARGET -> $PREFIX"
find "$PREFIX/lib" -maxdepth 1 -name 'libass*' -print
