#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Package a built target as the archive the player already looks for.
#
# NativeArchives in nomercy-player-core-kmp resolves
# `libass-<version>-<platform>.tar.gz` under `natives-libass-<version>/`, and
# HostPlatform spells the platform `windows-x64`, `linux-x64`, `linux-arm64`,
# `macos-x64`, `macos-arm64`. Emitting raw .so and .dll files instead means the
# two halves never meet: the pipeline publishes and the desktop still reports
# "libass is not installed on this machine".
#
#   scripts/package.sh linux-x86-64 linux-x64
set -euo pipefail

TARGET="${1:?usage: package.sh <build-target> <host-platform-id>}"
PLATFORM="${2:?usage: package.sh <build-target> <host-platform-id>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../versions.env
. "$ROOT/versions.env"

PREFIX="$ROOT/build/prefix/$TARGET"
STAGE="$ROOT/build/stage/$PLATFORM"
DIST="$ROOT/build/dist"

[ -d "$PREFIX/lib" ] || { echo "nothing built for $TARGET" >&2; exit 2; }

rm -rf "$STAGE"
mkdir -p "$STAGE" "$DIST"

# Flat, and only the shared library. AssRenderers.jvm looks for libass-9.dll,
# libass.so.9 or libass.dylib directly inside the payload directory — a nested
# lib/ would resolve to nothing with no error, which is the silent-miss this
# whole repo exists to remove.
# bin/ as well as lib/, because a mingw target puts the DLL in bin.
#
# Only the import library (libass.dll.a) lands in lib/, and packaging that would
# ship an archive with no runtime in it: the desktop would look for libass-9.dll,
# find nothing, and report libass as not installed on a machine that had just
# downloaded it.
# Only the directories that exist: every target other than Windows has no bin,
# and find takes a missing path as an error rather than as nothing to search.
SEARCH=("$PREFIX/lib")
[ -d "$PREFIX/bin" ] && SEARCH+=("$PREFIX/bin")

find "${SEARCH[@]}" -maxdepth 1 \( -name 'libass*.dll' -o -name 'libass.so*' -o -name 'libass*.dylib' \) \
    -exec cp -P {} "$STAGE/" \;

[ -n "$(ls -A "$STAGE")" ] || { echo "no libass shared library in $PREFIX/lib or $PREFIX/bin" >&2; exit 1; }

ARCHIVE="$DIST/libass-$LIBASS_VERSION-$PLATFORM.tar.gz"
tar -czf "$ARCHIVE" -C "$STAGE" .

echo "== packaged $PLATFORM"
tar -tzf "$ARCHIVE" | sed 's/^/   /'
echo "   -> $ARCHIVE"
