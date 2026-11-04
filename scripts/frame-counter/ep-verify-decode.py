#!/usr/bin/env python3
"""Check N random frames of the fixture video: the squares decoded from the picture equal the decoder frame number.

Also writes one full-size PNG of the first sampled frame (PNG_OUT) to look at the digits.

Usage: ep-verify-decode.py VIDEO [--count 20] [--seed 1] [--png OUT.png]
"""
import argparse
import random
import subprocess
import sys

from epcommon import *

ap = argparse.ArgumentParser()
ap.add_argument('video')
ap.add_argument('--count', type=int, default=20)
ap.add_argument('--seed', type=int, default=1)
ap.add_argument('--png')
a = ap.parse_args()

pts, _ = packet_pts(a.video)
random.seed(a.seed)
picks = sorted(random.sample(range(len(pts)), a.count))
sel = '+'.join('eq(n\\,%d)' % n for n in picks)
vf = "select='%s',crop=%d:%d:%d:%d,format=gray,scale=%d:1:flags=area" % (sel, STRIP_W, SQ, LEFT_X, STRIP_Y, NBITS)
r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-i', a.video, '-vf', vf, '-fps_mode', 'passthrough',
                    '-f', 'rawvideo', '-'], capture_output=True)
d = r.stdout
bad = 0
for k, n in enumerate(picks):
    v = d[k * NBITS:(k + 1) * NBITS]
    got = None if len(v) != NBITS else sum((1 if b > 128 else 0) << (NBITS - 1 - j) for j, b in enumerate(v))
    ok = got == n
    bad += not ok
    print('decoder frame %5d -> squares %s %s' % (n, got, 'OK' if ok else 'MISMATCH'))
print('mismatches: %d of %d' % (bad, a.count))
if a.png:
    subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-i', a.video, '-vf', "select='eq(n\\,%d)'" % picks[0],
                    '-frames:v', '1', a.png])
sys.exit(1 if bad else 0)
