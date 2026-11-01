#!/usr/bin/env bash
# Rebuild the frame-counter fixtures and prove them. Usage: recipe.sh OUT_DIR
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
OUT="$1"
FONT="$S/../../testdata/golden-ass/fonts/dejavu_sans.ttf"
mkdir -p "$OUT"
cd "$OUT"
python "$S/gen-ass.py" .
python "$S/gen-clip.py" "NM Frame Counter.mp4"
python "$S/verify-decode.py" "NM Frame Counter.mp4" --count 10
CROPS="--crop-left 20,130,512,32 --crop-right 748,130,512,32"
for v in counter counter-move planted-late1 planted-early1; do
  python "$S/render-reference.py" "NM Frame Counter.mp4" "$v.ass" "ref-$v.mp4" "$FONT" "ref-work-$v"
  python "$S/read-offsets.py" "ref-$v.mp4" $CROPS --quiet
done
