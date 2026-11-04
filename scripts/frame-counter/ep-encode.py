#!/usr/bin/env python3
"""Re-encode the episode with the frame index burned into the top-left corner.

The index is the decoder frame number: 16 binary squares (what the reader decodes) and 5 digits.
Pts, frame count and audio stay as in the source; audio is copied, chapters come from a .vtt file.

Usage: ep-encode.py --src VIDEO.m3u8 --audio AUDIO.m3u8 --chapters chapters.vtt --font arial.ttf
         --out OUT.mp4 [--seconds N] [--bitrate 2200k]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

from epcommon import *

ap = argparse.ArgumentParser()
ap.add_argument('--src', required=True)
ap.add_argument('--audio', required=True)
ap.add_argument('--chapters', required=True)
ap.add_argument('--font', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--seconds', type=float, default=0)
ap.add_argument('--bitrate', default='2200k')
a = ap.parse_args()

out = os.path.abspath(a.out)
work = os.path.dirname(out)
shutil.copy(a.font, os.path.join(work, 'font.ttf'))


def vtt_seconds(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


meta = [';FFMETADATA1']
for m in re.finditer(r'(\d+:\d+:[\d.]+) --> (\d+:\d+:[\d.]+)\n(.+)', open(a.chapters, encoding='utf-8').read()):
    meta += ['[CHAPTER]', 'TIMEBASE=1/1000', 'START=%d' % round(vtt_seconds(m.group(1)) * 1000),
             'END=%d' % round(vtt_seconds(m.group(2)) * 1000), 'title=' + m.group(3).strip()]
with open(os.path.join(work, 'chapters.ffmeta'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(meta) + '\n')

parts = ['drawbox=x=%d:y=%d:w=%d:h=%d:color=black:t=fill' % (LEFT_X, STRIP_Y, STRIP_W, SQ)]
for k in range(NBITS):
    parts.append("drawbox=x=%d:y=%d:w=%d:h=%d:color=white:t=fill:enable='bitand(n,%d)'"
                 % (LEFT_X + k * SQ, STRIP_Y, SQ, SQ, 1 << (NBITS - 1 - k)))
parts.append("drawtext=fontfile=font.ttf:text='%%{eif\\:n\\:d\\:5}':x=%d:y=%d:fontsize=%d:fontcolor=white:box=1:boxcolor=black:boxborderw=6"
             % (LEFT_X, DIGIT_Y, FONT_SIZE))
with open(os.path.join(work, 'index.vf'), 'w', newline='\n') as f:
    f.write(',\n'.join(parts) + '\n')

cmd = ['ffmpeg', '-hide_banner', '-y', '-copyts', '-i', os.path.abspath(a.src), '-i', os.path.abspath(a.audio),
       '-i', 'chapters.ffmeta', '-filter_script:v', 'index.vf', '-map', '0:v:0', '-map', '1:a:0', '-map_chapters', '2',
       '-c:v', 'libx265', '-b:v', a.bitrate, '-preset', 'medium', '-pix_fmt', 'yuv420p10le', '-tag:v', 'hvc1',
       '-x265-params', 'open-gop=0', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
       '-color_range', 'tv', '-c:a', 'copy', '-fps_mode', 'passthrough', '-enc_time_base', '1/16000',
       '-video_track_timescale', '16000']
if a.seconds:
    cmd += ['-t', str(a.seconds)]
cmd += [out]
sys.exit(subprocess.run(cmd, cwd=work).returncode)
