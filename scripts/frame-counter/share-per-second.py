#!/usr/bin/env python3
"""Share of recorded frames with offset 0, per second of video time (video number / 24000*1001).

Usage: share-per-second.py PAIRS.txt   (the --pairs file written by read-offsets.py)
"""
import sys
from collections import defaultdict

by_sec = defaultdict(list)
for line in open(sys.argv[1]).read().split('\n')[1:]:
    p = line.split()
    if len(p) == 5 and p[4] != '-':
        by_sec[int(int(p[2]) * 1001 / 24000)].append(int(p[4]))
for s in sorted(by_sec):
    d = by_sec[s]
    print('video second %3d: %3d recorded frames, at 0: %5.1f%%, at -1: %5.1f%%, other: %d' % (
        s, len(d), 100.0 * d.count(0) / len(d), 100.0 * d.count(-1) / len(d), len(d) - d.count(0) - d.count(-1)))
