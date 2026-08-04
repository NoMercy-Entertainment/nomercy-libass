#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Apple is an XCFramework, not a library: iOS device, iOS simulator, tvOS device
# and tvOS simulator are four separate slices Xcode refuses to mix. Everything
# else in this repo builds one file per target; this one builds four and wraps
# them, which is why it is its own script rather than another cross file.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/prefix/apple"
mkdir -p "$OUT/lib"

slice() {
    local name="$1" sdk="$2" arch="$3" minflag="$4"
    local sysroot
    sysroot="$(xcrun --sdk "$sdk" --show-sdk-path)"

    cat > "$ROOT/cross/apple-$name.ini" <<INI
[binaries]
c = 'clang'
cpp = 'clang++'
ar = 'ar'
strip = 'strip'
pkg-config = 'pkg-config'

[built-in options]
c_args = ['-arch', '$arch', '-isysroot', '$sysroot', '$minflag']
c_link_args = ['-arch', '$arch', '-isysroot', '$sysroot', '$minflag']

[host_machine]
system = 'darwin'
cpu_family = '$( [ "$arch" = "arm64" ] && echo aarch64 || echo x86_64 )'
cpu = '$arch'
endian = 'little'
INI

    "$ROOT/scripts/build-target.sh" "apple-$name"
}

slice ios-arm64        iphoneos          arm64  -mios-version-min=15.0
slice ios-sim-arm64    iphonesimulator   arm64  -mios-simulator-version-min=15.0
slice tvos-arm64       appletvos         arm64  -mtvos-version-min=15.0
slice tvos-sim-arm64   appletvsimulator  arm64  -mtvos-simulator-version-min=15.0

rm -rf "$OUT/lib/libass.xcframework"
xcodebuild -create-xcframework \
    $(for s in ios-arm64 ios-sim-arm64 tvos-arm64 tvos-sim-arm64; do
        printf ' -library %s/build/prefix/apple-%s/lib/libass.a -headers %s/build/prefix/apple-%s/include' "$ROOT" "$s" "$ROOT" "$s"
      done) \
    -output "$OUT/lib/libass.xcframework"

echo "== built apple -> $OUT/lib/libass.xcframework"
