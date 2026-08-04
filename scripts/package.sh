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

rm -rf "$STAGE"
mkdir -p "$STAGE" "$DIST"

# Every target ships one archive, and only its payload.
#
# The publish job uploaded the raw prefix trees and collided on the first header
# two targets had in common: "Uploading fterrors.h..." twice, and the release
# failed after seven green builds. A consumer wants the thing it loads, not the
# headers it was compiled against.
case "$TARGET" in
    apple)
        # An XCFramework is a directory, so it goes in whole. cinterop links
        # against the slice for the platform it is building.
        [ -d "$PREFIX/lib/libass.xcframework" ] || { echo "no xcframework for $TARGET" >&2; exit 1; }
        cp -R "$PREFIX/lib/libass.xcframework" "$STAGE/"
        ;;

    wasm)
        # The worker, its wasm and the preloaded font. A browser loads all three
        # and the .js resolves the other two by name beside it.
        for part in js wasm data; do
            cp "$ROOT/build/dist/wasm/nomercy-libass-worker.$part" "$STAGE/"
        done
        ;;

    *)
        # Flat, and only the shared library. AssRenderers.jvm looks for
        # libass-9.dll, libass.so.9 or libass.dylib directly inside the payload
        # directory — a nested lib/ would resolve to nothing with no error,
        # which is the silent-miss this whole repo exists to remove.
        #
        # bin/ as well as lib/, because a mingw target leaves only the import
        # library in lib/ and puts the DLL in bin. Packaging the import library
        # would ship an archive with no runtime in it, and the desktop would
        # report libass missing on a machine that had just downloaded it. Every
        # other target has no bin, and find takes a missing path as an error.
        [ -d "$PREFIX/lib" ] || { echo "nothing built for $TARGET" >&2; exit 2; }
        SEARCH=("$PREFIX/lib")
        [ -d "$PREFIX/bin" ] && SEARCH+=("$PREFIX/bin")

        find "${SEARCH[@]}" -maxdepth 1 \( -name 'libass*.dll' -o -name 'libass.so*' -o -name 'libass*.dylib' \)             -exec cp -P {} "$STAGE/" \;
        ;;
esac

[ -n "$(ls -A "$STAGE")" ] || { echo "nothing to package for $TARGET" >&2; exit 1; }

ARCHIVE="$DIST/libass-$LIBASS_VERSION-$PLATFORM.tar.gz"
tar -czf "$ARCHIVE" -C "$STAGE" .

echo "== packaged $PLATFORM"
tar -tzf "$ARCHIVE" | sed 's/^/   /'
echo "   -> $ARCHIVE"
