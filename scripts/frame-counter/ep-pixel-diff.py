#!/usr/bin/env python3
"""Compare the libass render of the real ASS with the render of the real ASS plus the numbers.

Both renders run on the same decoded frames and go straight to luma bytes (no lossy re-encode,
which would spread differences). Pixels inside the two number boxes are left out.

Usage: ep-pixel-diff.py VIDEO.mp4 REAL.ass NEW.ass FONTS_DIR WORKDIR
"""
import os
import shutil
import subprocess
import sys

import numpy as np

from epcommon import *

LEFT = (0, 0, LEFT_X + STRIP_W + 40, STRIP_Y + SQ + 40)
RIGHT = (RIGHT_X - 40, 0, W, STRIP_Y + SQ + 40)
video, real, new, fonts, work = [os.path.abspath(p) for p in sys.argv[1:6]]
os.makedirs(work, exist_ok=True)
shutil.copytree(fonts, os.path.join(work, 'fonts'), dirs_exist_ok=True)
shutil.copy(real, os.path.join(work, 'real.ass'))
shutil.copy(new, os.path.join(work, 'new.ass'))
conf = os.path.join(work, 'fonts.conf')
with open(conf, 'w') as f:
    f.write('<?xml version="1.0"?><fontconfig><dir>%s</dir><cachedir>%s</cachedir></fontconfig>'
            % (os.path.join(work, 'fonts').replace(chr(92), '/'), os.path.join(work, 'cache').replace(chr(92), '/')))
env = dict(os.environ, FONTCONFIG_FILE=conf)


def frames(name):
    p = subprocess.Popen(['ffmpeg', '-hide_banner', '-v', 'error', '-copyts', '-i', video, '-vf',
                          'subtitles=filename=%s:fontsdir=fonts,format=gray' % name, '-fps_mode', 'passthrough',
                          '-f', 'rawvideo', '-'], cwd=work, env=env, stdout=subprocess.PIPE, bufsize=W * H * 4)
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H:
            return
        yield np.frombuffer(b, np.uint8).reshape(H, W)


mask = np.ones((H, W), bool)
for x0, y0, x1, y1 in (LEFT, RIGHT):
    mask[y0:y1, x0:x1] = False
counts, inside = [], []
for fa, fb in zip(frames('real.ass'), frames('new.ass')):
    d = fa != fb
    counts.append(int((d & mask).sum()))
    inside.append(int((d & ~mask).sum()))
c = np.array(counts)
print('frames compared %d, outside the boxes: frames with a difference %d' % (len(c), int((c > 0).sum())))
print('differing pixels per frame outside the boxes p50/p99/max: %d / %d / %d (of %d pixels)'
      % (np.percentile(c, 50), np.percentile(c, 99), c.max(), int(mask.sum())))
print('inside the boxes (expected to differ) frames with a difference %d of %d' % (int((np.array(inside) > 0).sum()), len(c)))
