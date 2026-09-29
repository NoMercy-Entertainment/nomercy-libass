#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Refuse an Android library that is not linked for 16 KB pages.
#
# A 16 KB-page device cannot map a library whose load segments are aligned to
# 4 KB, so libass fails to load there, and Google Play refuses the whole app
# bundle that carries it ("Validation of uploaded file failed"). The
# v0.17.5-1 Android payloads shipped aligned to 4096 and nothing here noticed.
#
#   scripts/check-page-size.sh build/prefix/android-arm64-v8a
#
# Every .so under the given paths is read with readelf; the smallest PT_LOAD
# alignment has to be at least 16384.
set -euo pipefail

[ "$#" -gt 0 ] || { echo "usage: check-page-size.sh <dir-or-file>..." >&2; exit 2; }

READELF="${NDK_BIN:+$NDK_BIN/llvm-readelf}"
READELF="${READELF:-readelf}"

checked=0
failed=0
while IFS= read -r -d '' lib; do
    align=""
    for value in $("$READELF" -lW "$lib" | awk '$1 == "LOAD" { print $NF }'); do
        if [ -z "$align" ] || [ $((value)) -lt $((align)) ]; then align="$value"; fi
    done
    [ -n "$align" ] || { echo "no LOAD segment in $lib" >&2; failed=$((failed + 1)); continue; }
    checked=$((checked + 1))
    if [ $((align)) -lt 16384 ]; then
        echo "FAIL $lib is aligned to $((align)), needs 16384" >&2
        failed=$((failed + 1))
    else
        echo "ok   $lib ($((align)))"
    fi
done < <(find "$@" -name '*.so' -type f -print0)

[ "$checked" -gt 0 ] || { echo "no .so found under $*" >&2; exit 1; }
[ "$failed" -eq 0 ] || exit 1
