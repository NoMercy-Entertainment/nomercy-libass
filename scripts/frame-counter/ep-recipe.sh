#!/usr/bin/env bash
# Rebuild and re-prove the episode fixture. Usage: ep-recipe.sh EPISODE_FOLDER OUT_DIR [SECONDS]
# SECONDS = 0 means the whole episode. The folder holds video_1920x1080_SDR, audio_eng_opus, fonts, subtitles, chapters.vtt.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
EP="$1"; OUT="$2"; SECS="${3:-300}"
mkdir -p "$OUT/src" && cd "$OUT"
for d in video_1920x1080_SDR audio_eng_opus fonts subtitles; do [ -d "src/$d" ] || cp -r "$EP/$d" src/; done
cp -n "$EP/chapters.vtt" src/
V=src/video_1920x1080_SDR/video_1920x1080_SDR.m3u8
ASS=$(ls src/subtitles/*.eng.full.ass | head -1)
python "$S/ep-encode.py" --src "$V" --audio src/audio_eng_opus/audio_eng_opus.m3u8 --chapters src/chapters.vtt --font src/fonts/arial.ttf --out fixture.mp4 --seconds "$SECS"
python "$S/ep-pts-compare.py" fixture.mp4 "$V"
python "$S/ep-verify-decode.py" fixture.mp4 --count 20 --png frame.png
python "$S/ep-ass.py" "$ASS" fixture.mp4 fixture.ass
python "$S/ep-ass.py" "$ASS" fixture.mp4 planted-late1.ass --shift 1
python "$S/ep-ass.py" "$ASS" fixture.mp4 planted-early1.ass --shift -1
python "$S/ep-rounding.py" fixture.mp4 fixture.ass
python "$S/ep-render.py" fixture.mp4 "$ASS" src/fonts burnin-orig.mp4 work-orig
python "$S/ep-render.py" fixture.mp4 fixture.ass src/fonts burnin-new.mp4 work-new
python "$S/ep-read.py" burnin-new.mp4 pairs-new.txt --clean fixture.mp4 --orig burnin-orig.mp4
python "$S/ep-render.py" fixture.mp4 planted-late1.ass src/fonts burnin-late1.mp4 work-late1
python "$S/ep-read.py" burnin-late1.mp4 pairs-late1.txt --clean fixture.mp4 --orig burnin-orig.mp4 --expect-offset 1
python "$S/ep-render.py" fixture.mp4 planted-early1.ass src/fonts burnin-early1.mp4 work-early1
python "$S/ep-read.py" burnin-early1.mp4 pairs-early1.txt --clean fixture.mp4 --orig burnin-orig.mp4 --expect-offset -1
python "$S/ep-pixel-diff.py" fixture.mp4 "$ASS" fixture.ass src/fonts work-pd
