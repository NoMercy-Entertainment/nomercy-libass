#!/usr/bin/env python3
"""Write the frame-counter ASS files: plain and moving-sign variants.

Usage: gen-ass.py OUT_DIR   (writes counter.ass and counter-move.ass)
"""
import os
import sys

from common import *


def ts(cs):
    return '%d:%02d:%02d.%02d' % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)


def rect(x, y, w, h):
    return 'm %d %d l %d %d l %d %d l %d %d' % (x, y, x + w, y, x + w, y + h, x, y + h)


def header():
    return ('[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n'
            '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, '
            'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
            'Style: Num,%s,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n'
            'Style: Box,%s,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n'
            '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n') % (W, H, FONT, FONT)


def number_events(i, s, e, move):
    x0 = RIGHT_X
    y = DIGIT_Y - 8
    pos = ('\\move(%d,%d,%d,%d,0,10)' % (x0, y, x0, y)) if move else ('\\pos(%d,%d)' % (x0, y))
    panel = rect(x0, STRIP_Y, STRIP_W, SQ)
    white = ' '.join(rect(x0 + k * SQ, STRIP_Y, SQ, SQ) for k, b in enumerate(bits(i)) if b)
    ev = ['Dialogue: 1,%s,%s,Box,,0,0,0,,{\\an7\\pos(0,0)\\1c&H000000&\\p1}%s{\\p0}' % (ts(s), ts(e), panel)]
    if white:
        ev.append('Dialogue: 2,%s,%s,Box,,0,0,0,,{\\an7\\pos(0,0)\\1c&HFFFFFF&\\p1}%s{\\p0}' % (ts(s), ts(e), white))
    ev.append('Dialogue: 3,%s,%s,Num,,0,0,0,,{\\an7%s\\1c&HFFFFFF&\\bord0}%05d' % (ts(s), ts(e), pos, i))
    return ev


def build(move, shift=0):
    ev = []
    for i in range(FRAMES):
        s = start_cs(i + shift)
        e = start_cs(i + shift + 1) if i + 1 < FRAMES else s + 5
        ev += number_events(i, s, e, move)
    if move:
        end = start_cs(FRAMES)
        ev.append('Dialogue: 0,%s,%s,Box,,0,0,0,,{\\an5\\move(160,600,1120,600)\\1c&H00FFFF&\\bord0}SIGN' % (ts(0), ts(end)))
    return header() + '\n'.join(ev) + '\n'


out = sys.argv[1]
os.makedirs(out, exist_ok=True)
# planted defects for checking the reader: the overlay shown 1 frame late or early
variants = [('counter.ass', False, 0), ('counter-move.ass', True, 0),
            ('planted-late1.ass', False, 1), ('planted-early1.ass', False, -1)]
for name, mv, sh in variants:
    with open(os.path.join(out, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(build(mv, sh))
