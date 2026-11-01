#!/usr/bin/env python3
"""Check N random frames: the squares decoded from the picture equal the decoder's frame number.

Usage: verify-decode.py VIDEO [--side left|right] [--count 10] [--seed 1]
"""
import argparse
import random
import subprocess
import sys

from common import *

ap = argparse.ArgumentParser()
ap.add_argument('video')
ap.add_argument('--side', default='left')
ap.add_argument('--count', type=int, default=10)
ap.add_argument('--seed', type=int, default=1)
a = ap.parse_args()
x0 = LEFT_X if a.side == 'left' else RIGHT_X
random.seed(a.seed)
bad = 0
for n in sorted(random.sample(range(FRAMES), a.count)):
    vf = "select=eq(n\\,%d),crop=%d:%d:%d:%d,format=gray,scale=%d:1:flags=area" % (n, STRIP_W, SQ, x0, STRIP_Y, NBITS)
    r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-i', a.video, '-vf', vf, '-frames:v', '1',
                        '-f', 'rawvideo', '-'], capture_output=True)
    v = r.stdout
    got = None if len(v) != NBITS else sum((1 if b > 128 else 0) << (NBITS - 1 - k) for k, b in enumerate(v))
    ok = got == n
    bad += not ok
    print('decoder frame %5d -> squares %s %s' % (n, got, 'OK' if ok else 'MISMATCH'))
print('mismatches: %d of %d' % (bad, a.count))
sys.exit(1 if bad else 0)
