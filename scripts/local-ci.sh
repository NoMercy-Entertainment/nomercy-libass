#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Run a release-matrix target locally, in the same container the runner uses.
#
#   scripts/local-ci.sh linux-x86-64
#   scripts/local-ci.sh windows-x86-64
#   scripts/local-ci.sh wasm
#
# This exists because the alternative was pushing a one-line fix and waiting for
# seven cloud jobs to tell me whether it worked, which costs real money per
# attempt and hides the one file worth reading: meson-log.txt stays inside the
# runner and never reaches the summary. Here it stays on disk.
#
# Apple is the one target this cannot run — an XCFramework needs macOS SDKs.
set -euo pipefail

TARGET="${1:?usage: local-ci.sh <target>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="nomercy-libass-build"
# docker on Windows takes a Windows path for a bind mount and for a build
# context; the MSYS spelling is not a path it can resolve.
WINROOT="$(cygpath -w "$ROOT" 2>/dev/null || echo "$ROOT")"

case "$TARGET" in
    apple) echo "apple needs macOS; build it on the Mac mini, not here" >&2; exit 2 ;;
esac

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "== building $IMAGE"
    (cd "$ROOT" && docker build -t "$IMAGE" -f scripts/Dockerfile.build .)
fi

# Built in the container's own filesystem, then copied back.
#
# A Windows bind mount carries the host's clock, and meson refuses a build
# directory whose files are stamped in the future: "Clock skew detected. File
# coredata.dat has a time stamp 0.02s in the future." Nothing about the build is
# wrong; the two clocks simply disagree by milliseconds.
# The NDK, fetched once into build/ and kept there.
#
# An Android target needs a Linux-host NDK, and a Windows SDK install has no
# linux-x86_64 prebuilt in it. Without this the three Android targets could only
# ever be checked by dispatching CI, which is the habit local-ci.sh exists to
# break. One download makes them local like every other target.
NDK_VERSION=r27c
NDK_HOME="build/ndk/android-ndk-$NDK_VERSION"
NDK_ENV=""

case "$TARGET" in
    android-*)
        if [ ! -d "$ROOT/$NDK_HOME" ]; then
            echo "== fetching android ndk $NDK_VERSION"
            mkdir -p "$ROOT/build/ndk"
            docker run --rm -v "$WINROOT":/mnt/work "$IMAGE" bash -lc \
                "apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq unzip >/dev/null 2>&1 \
                 && curl -fsSL -o /tmp/ndk.zip https://dl.google.com/android/repository/android-ndk-$NDK_VERSION-linux.zip \
                 && rm -rf /mnt/work/build/ndk/android-ndk-$NDK_VERSION \
                 && unzip -qo /tmp/ndk.zip -d /mnt/work/build/ndk"
        fi
        NDK_ENV="export NDK_BIN=/build/$NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin;"
        ;;
esac

docker run --rm \
    -v "$WINROOT":/mnt/work \
    "$IMAGE" \
    bash -lc "cp -r /mnt/work /build && cd /build && $NDK_ENV \
        scripts/fetch.sh && scripts/build-target.sh $TARGET \
        && mkdir -p /mnt/work/build/prefix \
        && cp -r /build/build/prefix/$TARGET /mnt/work/build/prefix/"
