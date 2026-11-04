#!/usr/bin/env python3
"""Find where the real ASS draws anything: share of frames that touch each 40x40 pixel cell.

Renders the file over black at the episode frame rate and counts, per cell, the frames with any
non-black pixel. A cell at 0 can hold a frame number that no real event covers.

Usage: ep-coverage.py REAL.ass FONTS_DIR WORKDIR [SECONDS]   (prints the grid and the best free boxes)
"""
import os
import shutil
import subprocess
import sys

import numpy as np

from epcommon import *

ass, fonts, work = [os.path.abspath(p) for p in sys.argv[1:4]]
secs = float(sys.argv[4]) if len(sys.argv) > 4 else 1422
os.makedirs(work, exist_ok=True)
shutil.copytree(fonts, os.path.join(work, 'fonts'), dirs_exist_ok=True)
shutil.copy(ass, os.path.join(work, 'sub.ass'))
conf = os.path.join(work, 'fonts.conf')
with open(conf, 'w') as f:
    f.write('<?xml version="1.0"?><fontconfig><dir>%s</dir><cachedir>%s</cachedir></fontconfig>'
            % (os.path.join(work, 'fonts').replace(chr(92), '/'), os.path.join(work, 'cache').replace(chr(92), '/')))
env = dict(os.environ, FONTCONFIG_FILE=conf)
CELL = 40
gw, gh = W // CELL, H // CELL
vf = 'subtitles=filename=sub.ass:fontsdir=fonts,scale=%d:%d:flags=area,format=gray' % (gw, gh)
p = subprocess.Popen(['ffmpeg', '-hide_banner', '-v', 'error', '-f', 'lavfi', '-i',
                      'color=c=black:s=%dx%d:r=24000/1001:d=%s' % (W, H, secs), '-vf', vf, '-f', 'rawvideo', '-'],
                     cwd=work, env=env, stdout=subprocess.PIPE, bufsize=gw * gh * 8)
hits = np.zeros((gh, gw), np.int64)
n = 0
while True:
    b = p.stdout.read(gw * gh)
    if len(b) < gw * gh:
        break
    hits += np.frombuffer(b, np.uint8).reshape(gh, gw) > 24
    n += 1
print('frames %d' % n)
np.save(os.path.join(work, 'hits.npy'), hits)
share = 100.0 * hits / n
for y in range(gh):
    print(''.join('.' if s == 0 else ('o' if s < 1 else ('+' if s < 10 else '#')) for s in share[y]))
need = (-(-STRIP_W // CELL), -(-(STRIP_Y + SQ - DIGIT_Y) // CELL))
print('legend: . never covered, o under 1 percent of frames, # more')
