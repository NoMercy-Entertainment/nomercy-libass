#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Fetch every source this pipeline builds, verified by digest.
#
# Verified, not merely downloaded. A tarball taken on trust is a build that
# changes under you, and the whole reason this repo exists is that four
# third-party libass builds drifted apart and each fell short somewhere
# different.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/build/src"
# shellcheck source=../versions.env
. "$ROOT/versions.env"

mkdir -p "$SRC"

digest() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

# Downloads once, checks always. A cached tarball whose digest no longer matches
# is a corrupted cache or a moved tag, and both are worth stopping for.
fetch() {
    local name="$1" version="$2" want="$3" url="$4"
    # The extension comes from the URL, not from an assumption: libass and
    # freetype ship .tar.gz, fribidi and harfbuzz ship .tar.xz, and hardcoding
    # gzip made tar fail on half the sources with "not in gzip format".
    local ext="tar.gz"
    case "$url" in *.tar.xz) ext="tar.xz" ;; esac
    local file="$SRC/$name-$version.$ext"

    if [ ! -f "$file" ]; then
        echo "== fetch $name $version"
        curl -fsSL "$url" -o "$file.part"
        mv "$file.part" "$file"
    fi

    local got
    got="$(digest "$file")"
    if [ "$got" != "$want" ]; then
        echo "$name $version digest mismatch" >&2
        echo "  expected $want" >&2
        echo "  got      $got" >&2
        exit 1
    fi

    rm -rf "$SRC/$name"
    mkdir -p "$SRC/$name"
    tar -xf "$file" -C "$SRC/$name" --strip-components=1
    echo "== ok $name $version"
}

fetch libass "$LIBASS_VERSION" "$LIBASS_SHA256" \
    "https://github.com/libass/libass/releases/download/$LIBASS_VERSION/libass-$LIBASS_VERSION.tar.gz"

fetch freetype "$FREETYPE_VERSION" "$FREETYPE_SHA256" \
    "https://github.com/freetype/freetype/archive/refs/tags/VER-2-13-3.tar.gz"

fetch fribidi "$FRIBIDI_VERSION" "$FRIBIDI_SHA256" \
    "https://github.com/fribidi/fribidi/releases/download/v$FRIBIDI_VERSION/fribidi-$FRIBIDI_VERSION.tar.xz"

fetch harfbuzz "$HARFBUZZ_VERSION" "$HARFBUZZ_SHA256" \
    "https://github.com/harfbuzz/harfbuzz/releases/download/$HARFBUZZ_VERSION/harfbuzz-$HARFBUZZ_VERSION.tar.xz"

echo "sources in $SRC"
