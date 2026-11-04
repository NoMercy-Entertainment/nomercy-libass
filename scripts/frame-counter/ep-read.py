#!/usr/bin/env python3
"""Run the offset reader on an episode burn-in and print the acceptance lines.

The reader (read-offsets.py) reads both numbers on every frame. A real sign can draw over the
baked video number, so the script also checks the file position: the clean fixture video must
read position == number on every frame, the overlay must read position + offset on every frame,
and each frame where the burned-in video number is wrong or unreadable must be a frame where the
real events alone change the strip (burn-in of the real ASS compared with the clean video).

Usage: ep-read.py BURNIN.mp4 PAIRS.txt --clean FIXTURE.mp4 [--orig BURNIN_REAL_ONLY.mp4] [--expect-offset N]
Exit 0 when every frame has overlay == position + N and every bad video number is explained.
"""
import argparse
import os
import subprocess
import sys

import numpy as np

from epcommon import *

ap = argparse.ArgumentParser()
ap.add_argument('video')
ap.add_argument('pairs')
ap.add_argument('--clean', required=True)
ap.add_argument('--orig')
ap.add_argument('--expect-offset', type=int, default=0)
a = ap.parse_args()
here = os.path.dirname(os.path.abspath(__file__))


def reader(video, left, right, pairs):
    r = subprocess.run([sys.executable, os.path.join(here, 'read-offsets.py'), video, '--crop-left', left,
                        '--crop-right', right, '--scale', str(SCALE), '--quiet', '--pairs', pairs],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit('reader failed: ' + r.stderr[-400:])
    return r.stdout.strip(), [l.split() for l in open(pairs).read().splitlines()[1:]]


def strips(path):
    vf = 'crop=%d:%d:%d:%d,format=gray' % (STRIP_W, SQ, LEFT_X, STRIP_Y)
    r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-i', path, '-vf', vf, '-fps_mode', 'passthrough',
                        '-f', 'rawvideo', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, SQ * STRIP_W)


out, rows = reader(a.video, CROP_LEFT, CROP_RIGHT, a.pairs)
print(out)
total = len(rows)
ov_ok = sum(1 for x in rows if x[3] != '-' and int(x[3]) == int(x[0]) + a.expect_offset)
vid_ok = [x[2] != '-' and int(x[2]) == int(x[0]) for x in rows]
diffs = [int(x[4]) for x in rows if x[4] != '-']
print('PROOF reader frames with diff %d: %d / %d, min/max diff %d / %d'
      % (a.expect_offset, sum(1 for d in diffs if d == a.expect_offset), total, min(diffs), max(diffs)))
print('PROOF overlay number == file position + %d: %d / %d' % (a.expect_offset, ov_ok, total))
cout, crows = reader(a.clean, CROP_LEFT, CROP_LEFT, a.pairs + '.clean')
c_ok = sum(1 for x in crows if x[2] != '-' and int(x[2]) == int(x[0]))
print('PROOF clean fixture video number == file position: %d / %d' % (c_ok, len(crows)))
bad = [k for k, ok in enumerate(vid_ok) if not ok]
print('burned-in video number wrong or unreadable on %d / %d frames' % (len(bad), total))
explained = None
if a.orig and bad:
    clean, orig = strips(a.clean), strips(a.orig)
    n = min(len(clean), len(orig))
    covered = {k for k in range(n) if int(np.abs(clean[k].astype(int) - orig[k].astype(int)).max()) > 40}
    explained = sum(1 for k in bad if k in covered)
    print('of those, frames where the real events alone change the strip: %d / %d (real events change the strip on %d frames)'
          % (explained, len(bad), len(covered)))
ok = ov_ok == total and c_ok == len(crows) and (not bad or explained == len(bad))
sys.exit(0 if ok else 1)
