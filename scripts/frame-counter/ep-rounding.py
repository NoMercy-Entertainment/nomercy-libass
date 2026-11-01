#!/usr/bin/env python3
"""Rounding error of the appended overlay events: exact frame pts minus the event start, in ms.

Usage: ep-rounding.py VIDEO.mp4 FILE.ass
"""
import re
import sys
from fractions import Fraction

from epcommon import *

pts, tb = packet_pts(sys.argv[1])
starts = []
for line in open(sys.argv[2], encoding='utf-8'):
    m = re.match(r'Dialogue: %d,(\d+):(\d\d):(\d\d)\.(\d\d),' % (OVERLAY_LAYER + 3), line)
    if m:
        h, mi, s, cs = [int(v) for v in m.groups()]
        starts.append(((h * 60 + mi) * 60 + s) * 100 + cs)
if len(starts) != len(pts):
    sys.exit('events %d, frames %d' % (len(starts), len(pts)))
err = [float(Fraction(p * tb[0] * 1000, tb[1]) - 10 * c) for p, c in zip(pts, starts)]
print('frames %d: pts minus event start, ms: min %.3f, max %.3f, mean %.3f' % (len(err), min(err), max(err), sum(err) / len(err)))
print('late events (start after pts): %d; events 0 to 11 ms early: %d' % (sum(1 for e in err if e < 0), sum(1 for e in err if 0 <= e < 11)))
