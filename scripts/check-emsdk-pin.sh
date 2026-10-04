#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Refuse an emscripten that is not the one versions.env pins.
#
# The worker glue passes the frame time to ass_render_frame as a BigInt,
# because emscripten hands a 64-bit argument across the wasm boundary that way
# since 4.0.0 ("The WASM_BIGINT feature is enabled by default", ChangeLog
# 4.0.0). Before that it split the value into two Numbers, and the first
# render threw "Cannot convert ... to a BigInt" with a blank overlay. The
# image and the workflow both installed "latest", so every rebuild could take
# a compiler nobody had tested the worker against, and the two could disagree
# with each other.
#
#   scripts/check-emsdk-pin.sh
#
# Checks that versions.env pins one exact EMSCRIPTEN_VERSION, that it is at
# least 4.0.0, that scripts/Dockerfile.build and the release workflow both
# take the version from there and nowhere else, and, when emcc is on PATH,
# that the installed compiler is that version.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKERFILE="$ROOT/scripts/Dockerfile.build"
WORKFLOW="$ROOT/.github/workflows/release.yml"

failed=0
fail() { echo "FAIL $*" >&2; failed=$((failed + 1)); }
ok() { echo "ok   $*"; }

# shellcheck source=../versions.env
. "$ROOT/versions.env"

pin="${EMSCRIPTEN_VERSION:-}"
if [[ "$pin" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    ok "versions.env pins emscripten $pin"
else
    fail "versions.env has no exact EMSCRIPTEN_VERSION (got '${pin:-<empty>}'; 'latest' is not a pin)"
fi

if [ -n "$pin" ] && [ "${pin%%.*}" -ge 4 ] 2>/dev/null; then
    ok "emscripten $pin passes 64-bit arguments as BigInt (default since 4.0.0)"
elif [ -n "$pin" ]; then
    fail "emscripten $pin is older than 4.0.0, which the BigInt call in src/worker-glue.js needs"
fi

# Dockerfile.build: every emsdk install/activate names the variable, never an
# alias or a literal, so the image cannot drift from the file.
installs="$(grep -E 'emsdk (install|activate) ' "$DOCKERFILE" || true)"
if [ -z "$installs" ]; then
    fail "$DOCKERFILE installs no emsdk"
fi
while IFS= read -r line; do
    [ -n "$line" ] || continue
    if printf '%s\n' "$line" | grep -qE 'emsdk (install|activate) +"?\$\{?EMSCRIPTEN_VERSION\}?"?'; then
        ok "Dockerfile.build: ${line#*&& }"
    else
        fail "Dockerfile.build does not take the version from versions.env: ${line#*&& }"
    fi
done <<< "$installs"

# release.yml: the setup-emsdk step reads the same variable from the
# environment the workflow fills from versions.env.
if ! grep -qE 'uses: mymindstorm/setup-emsdk@' "$WORKFLOW"; then
    fail "$WORKFLOW has no setup-emsdk step"
else
    version="$(awk '/uses: mymindstorm\/setup-emsdk@/ { hit = NR } hit && NR > hit && NR <= hit + 3 && /^[[:space:]]*version:/ { sub(/^[[:space:]]*version:[[:space:]]*/, ""); print; exit }' "$WORKFLOW")"
    if [ "$version" = '${{ env.EMSCRIPTEN_VERSION }}' ]; then
        ok "release.yml: setup-emsdk version comes from EMSCRIPTEN_VERSION"
    else
        fail "release.yml: setup-emsdk installs '${version:-latest (no version input)}', not versions.env's EMSCRIPTEN_VERSION"
    fi
    if ! grep -qE 'EMSCRIPTEN_VERSION=.*versions\.env|versions\.env.*EMSCRIPTEN_VERSION' "$WORKFLOW"; then
        fail "release.yml never reads EMSCRIPTEN_VERSION out of versions.env"
    fi
fi

# The compiler that will actually link, when there is one here.
if command -v emcc >/dev/null 2>&1; then
    installed="$(emcc --version 2>/dev/null | head -n 1)"
    if [ -n "$pin" ] && printf '%s\n' "$installed" | grep -qF " $pin "; then
        ok "installed emcc is $pin"
    else
        fail "installed emcc is not the pinned $pin: $installed"
    fi
fi

[ "$failed" -eq 0 ] || { echo "$failed emsdk pin check(s) failed" >&2; exit 1; }
echo "emsdk pin: $pin in versions.env, Dockerfile.build and release.yml agree"
