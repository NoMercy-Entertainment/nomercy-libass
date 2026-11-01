#!/usr/bin/env python3
"""Compare the video pts of the new file with the source, frame by frame, in exact time.

Usage: ep-pts-compare.py NEW.mp4 SOURCE.m3u8
"""
import sys
from fractions import Fraction

from epcommon import *

new, tb_new = packet_pts(sys.argv[1])
src_packets, tb_src = packet_pts(sys.argv[2])
src = frame_pts(sys.argv[2])[:len(new)]
print('source packets in the file %d; the decoder outputs %d frames in the same window' % (len(src_packets), len(src)))
print('time base new %d/%d, source %d/%d' % (*tb_new, *tb_src))
print('frames new %d, source (same window) %d' % (len(new), len(src)))
if len(new) != len(src):
    sys.exit('frame count differs')
diff = [abs(Fraction(a * tb_new[0], tb_new[1]) - Fraction(b * tb_src[0], tb_src[1])) for a, b in zip(new, src)]
bad = sum(1 for d in diff if d)
print('frames with a different pts: %d of %d, max difference %.6f ms' % (bad, len(diff), float(max(diff)) * 1000))
print('first pts new %s source %s' % (Fraction(new[0] * tb_new[0], tb_new[1]), Fraction(src[0] * tb_src[0], tb_src[1])))
sys.exit(1 if bad else 0)
