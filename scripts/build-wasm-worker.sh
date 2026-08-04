#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------
#
# Link our libass into the worker the web player loads.
#
# build-target.sh wasm produces a static library; a browser cannot load that.
# SubtitlesOctopus shipped a prebuilt worker instead, which is the last third
# party in the subtitle path — a JavaScript port of libass whose version nobody
# here chose and whose fixes arrive when someone else makes them.
#
# The NoMercy wrapper in packages/nomercy-subtitle-octopus stays: it owns the
# API the video player calls. Only the worker underneath it changes, so the swap
# is three files rather than a rewrite.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="$ROOT/build/prefix/wasm"
DIST="$ROOT/build/dist/wasm"
# shellcheck source=../versions.env
. "$ROOT/versions.env"

[ -d "$PREFIX/lib" ] || { echo "run scripts/build-target.sh wasm first" >&2; exit 2; }
command -v emcc >/dev/null 2>&1 || { echo "emcc not on PATH" >&2; exit 2; }

mkdir -p "$DIST"

# The C entry points the wrapper's worker bridge calls. Exported by name because
# emscripten drops anything it cannot prove is reachable, and a library linked
# with its API stripped fails at the first call with no symbol and no clue.
EXPORTS='["_ass_library_init","_ass_library_done","_ass_renderer_init","_ass_renderer_done","_ass_set_frame_size","_ass_set_storage_size","_ass_set_fonts","_ass_set_cache_limits","_ass_add_font","_ass_clear_fonts","_ass_read_memory","_ass_free_track","_ass_render_frame","_malloc","_free"]'

emcc \
    "$PREFIX/lib/libass.a" \
    "$PREFIX/lib/libharfbuzz.a" \
    "$PREFIX/lib/libfribidi.a" \
    "$PREFIX/lib/libfreetype.a" \
    -O3 \
    -s WASM=1 \
    -s MODULARIZE=1 \
    -s EXPORT_NAME=NoMercyLibass \
    -s ENVIRONMENT=worker \
    -s ALLOW_MEMORY_GROWTH=1 \
    -s EXPORTED_FUNCTIONS="$EXPORTS" \
    -s EXPORTED_RUNTIME_METHODS='["ccall","cwrap","HEAPU8","FS"]' \
    --preload-file "$ROOT/fonts@/fonts" \
    -o "$DIST/nomercy-libass-worker.js"

echo "== wasm worker $LIBASS_VERSION"
ls -la "$DIST" | sed 's/^/   /'
