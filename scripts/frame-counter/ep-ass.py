#!/usr/bin/env python3
"""Append the frame-number overlay to the episode's real ASS file.

The original file is kept byte for byte: the new events go in after its last Dialogue line.
Per frame: a black panel, the white squares and the digits on layer 1001 to 1003 (the file's
own layers stop at 100), drawn top-right with the style pSigns that the file already has.
Start = floor of (exact pts minus 1 ms) in centiseconds; each event ends where the next starts.

Usage: ep-ass.py REAL.ass VIDEO.mp4 OUT.ass [--shift N]   (shift N frames = planted defect)
"""
import argparse
import sys

from epcommon import *

STYLE = 'pSigns'


def ts(cs):
    return '%d:%02d:%02d.%02d' % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)


def rect(x, y, w, h):
    return 'm %d %d l %d %d l %d %d l %d %d' % (x, y, x + w, y, x + w, y + h, x, y + h)


def bits(i):
    return [(i >> (NBITS - 1 - k)) & 1 for k in range(NBITS)]


def events(i, s, e):
    t = '%s,%s,%s,,0,0,0,,' % (ts(s), ts(e), STYLE)
    panel = rect(RIGHT_X, STRIP_Y, STRIP_W, SQ)
    white = ' '.join(rect(RIGHT_X + k * SQ, STRIP_Y, SQ, SQ) for k, b in enumerate(bits(i)) if b)
    ev = ['Dialogue: %d,%s{\\an7\\pos(0,0)\\1c&H000000&\\bord0\\shad0\\p1}%s{\\p0}' % (OVERLAY_LAYER + 1, t, panel)]
    if white:
        ev.append('Dialogue: %d,%s{\\an7\\pos(0,0)\\1c&HFFFFFF&\\bord0\\shad0\\p1}%s{\\p0}' % (OVERLAY_LAYER + 2, t, white))
    ev.append('Dialogue: %d,%s{\\an7\\pos(%d,%d)\\fnArial\\fs%d\\1c&HFFFFFF&\\bord0\\shad0}%05d'
              % (OVERLAY_LAYER + 3, t, RIGHT_X, DIGIT_Y, FONT_SIZE, i))
    return ev


ap = argparse.ArgumentParser()
ap.add_argument('real')
ap.add_argument('video')
ap.add_argument('out')
ap.add_argument('--shift', type=int, default=0)
a = ap.parse_args()

pts, tb = packet_pts(a.video)
raw = open(a.real, 'rb').read()
text = raw.decode('utf-8')
if '\r' in text:
    sys.exit('the real ASS has CR characters; this script writes LF only')
cut = text.rindex('\nDialogue:')
cut = text.index('\n', cut + 1) + 1
n = len(pts)
new = []
for i in range(n):
    j = i + a.shift
    s = start_cs(pts[i], tb)
    e = start_cs(pts[i + 1], tb) if i + 1 < n else s + 4
    new += events(max(0, j), s, e)
body = text[:cut] + '\n'.join(new) + '\n' + text[cut:]
with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
    f.write(body)
print('frames %d, events appended %d, original events kept %d' % (n, len(new), text[:cut].count('\nDialogue:')))
