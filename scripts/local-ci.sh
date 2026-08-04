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

docker run --rm \
    -v "$WINROOT":/work \
    -w /work \
    "$IMAGE" \
    bash -lc "scripts/fetch.sh && scripts/build-target.sh $TARGET"
