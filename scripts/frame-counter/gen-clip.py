#!/usr/bin/env python3
"""Build the frame-number clip: index digits and 16 binary squares at top-left.

Usage: gen-clip.py OUT.mp4
"""
import subprocess
import sys

import numpy as np

from common import *

SEG = {0: 'abcdef', 1: 'bc', 2: 'abdeg', 3: 'abcdg', 4: 'bcfg', 5: 'acdfg', 6: 'acdefg', 7: 'abc', 8: 'abcdefg', 9: 'abcdfg'}
DW, DH, T, GAP = 56, 92, 10, 12


def seg_rects(seg):
    h = DH // 2
    return {'a': (0, 0, DW, T), 'd': (0, DH - T, DW, T), 'g': (0, h - T // 2, DW, T),
            'b': (DW - T, 0, T, h), 'c': (DW - T, h, T, h), 'f': (0, 0, T, h), 'e': (0, h, T, h)}[seg]


def draw_index(img, i, x0):
    img[DIGIT_Y - 6:DIGIT_Y + DH + 6, x0 - 6:x0 + 5 * (DW + GAP) + 2] = 0
    for n, ch in enumerate('%05d' % i):
        for s in SEG[int(ch)]:
            x, y, w, h = seg_rects(s)
            xx = x0 + n * (DW + GAP) + x
            img[DIGIT_Y + y:DIGIT_Y + y + h, xx:xx + w] = 255
    img[STRIP_Y:STRIP_Y + SQ, x0:x0 + STRIP_W] = 0
    for k, b in enumerate(bits(i)):
        if b:
            img[STRIP_Y:STRIP_Y + SQ, x0 + k * SQ:x0 + (k + 1) * SQ] = 255


def main():
    out = sys.argv[1]
    yy, xx = np.mgrid[0:H, 0:W]
    base = (xx * 0.6 + yy * 0.4).astype(np.float32)
    cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-framerate', '%d/%d' % (FPS_NUM, FPS_DEN), '-i', '-',
           '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
           '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
           '-frames:v', str(FRAMES), '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-g', '48',
           '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
           '-fps_mode', 'cfr', '-r', '%d/%d' % (FPS_NUM, FPS_DEN),
           '-c:a', 'aac', '-b:a', '64k', '-shortest', '-movflags', '+faststart', out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(FRAMES):
        g = 25 + 35 * (0.5 + 0.5 * np.sin((base + i * 3.0) / 140.0))
        img = np.empty((H, W, 3), np.uint8)
        img[..., 0] = g * 0.9
        img[..., 1] = g
        img[..., 2] = g * 1.2
        draw_index(img, i, LEFT_X)
        p.stdin.write(img.tobytes())
    p.stdin.close()
    sys.exit(p.wait())


main()
