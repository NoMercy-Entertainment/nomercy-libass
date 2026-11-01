#!/usr/bin/env python3
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------

"""Render the golden ASS fixtures with ffmpeg's libass and write the stills.

Per fixture: one PNG crop of the non-background area per frame (identical
consecutive crops share a file) and a manifest.json in the format that
compare-overlay-frames.py reads. The fixture.ass files come from
generate-fixtures.py.

Usage:
  render-reference.py [--out DIR] [--only NAME] [--scratch DIR]
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'testdata', 'golden-ass')
W, H, FRAMES = 1280, 720, 240
FPS = '24000/1001'

SOURCES = {
    'black': 'color=c=black:s=%dx%d:r=%s:d=10' % (W, H, FPS),
    'gradient': ("color=c=black:s=%dx%d:r=%s:d=10,format=rgb24,"
                 "geq=r='20+60*X/W':g='30+50*Y/H':b='70+40*(X+Y)/(W+H)'" % (W, H, FPS)),
}


def load_fixtures():
    spec = importlib.util.spec_from_file_location('gen', os.path.join(HERE, 'generate-fixtures.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.FIXTURES


def pts_ms(i):
    return (i * 1001 * 1000 + 12000) // 24000


def ffmpeg(args, cwd, env):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error'] + args, cwd=cwd, env=env,
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit('ffmpeg failed: ' + r.stderr[-800:])


def libass_line():
    r = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'debug', '-f', 'lavfi', '-i',
                        'color=c=black:s=64x64:d=0.1', '-vf', 'subtitles=nonexist.ass', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = re.search(r'libass API version: (0x[0-9a-f]+)', r.stderr)
    s = '%08x' % int(m.group(1), 16)
    return '%d.%d.%d' % (int(s[0]), int(s[1:3]), int(s[3:5]))


def parse_cues(ass_path):
    cues = []
    with open(ass_path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('Dialogue:'):
                p = line.split(',', 9)
                cues.append((ts(p[1]), ts(p[2])))
    return cues


def ts(s):
    h, m, rest = s.strip().split(':')
    sec, c = rest.split('.')
    return ((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000 + int(c) * 10


def render(name, bg, fontmode, window, out_root, scratch, libass):
    first, count = window
    src = os.path.join(out_root, name)
    work = os.path.join(scratch, name)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(os.path.join(work, 'png'))
    os.makedirs(os.path.join(work, 'fonts'))
    if fontmode == 'free':
        for f in os.listdir(os.path.join(out_root, 'fonts')):
            shutil.copy(os.path.join(out_root, 'fonts', f), os.path.join(work, 'fonts', f))
    shutil.copy(os.path.join(src, 'fixture.ass'), os.path.join(work, 'fixture.ass'))
    conf = os.path.join(work, 'fonts.conf')
    with open(conf, 'w') as f:
        f.write('<?xml version="1.0"?><fontconfig><dir>%s</dir><cachedir>%s</cachedir></fontconfig>'
                % (os.path.join(work, 'fonts').replace('\\', '/'), os.path.join(work, 'cache').replace('\\', '/')))
    env = dict(os.environ, FONTCONFIG_FILE=conf)
    vf = 'subtitles=filename=fixture.ass:fontsdir=fonts'
    chain = SOURCES[bg] if 'format=rgb24' in SOURCES[bg] else SOURCES[bg] + ',format=rgb24'
    ffmpeg(['-f', 'lavfi', '-i', chain, '-vf', vf, '-copyts', '-fps_mode', 'passthrough',
            '-frames:v', str(first + count), '-start_number', '0', 'png/%04d.png'], work, env)
    ffmpeg(['-f', 'lavfi', '-i', chain, '-frames:v', '1', 'png/bg.png'], work, env)
    bgimg = np.array(Image.open(os.path.join(work, 'png', 'bg.png')).convert('RGB'))
    cues = parse_cues(os.path.join(src, 'fixture.ass'))
    frames, seen, files = [], {}, 0
    for i in range(first, first + count):
        t = pts_ms(i)
        active = [k for k, (s, e) in enumerate(cues) if s <= t < e]
        img = np.array(Image.open(os.path.join(work, 'png', '%04d.png' % i)).convert('RGB'))
        mask = (img != bgimg).any(axis=2)
        fr = {'index': i, 'pts_ms': t, 'cues': active, 'crop': None, 'file': None}
        if mask.any():
            ys, xs = np.where(mask)
            x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
            crop = img[y0:y1, x0:x1]
            key = hashlib.sha256(crop.tobytes() + bytes([x0 & 255, x0 >> 8, y0 & 255, y0 >> 8, crop.shape[1] & 255, crop.shape[1] >> 8])).hexdigest()
            if key not in seen:
                seen[key] = 'f%04d.png' % i
                Image.fromarray(crop).save(os.path.join(src, seen[key]), compress_level=9, optimize=True)
                files += 1
            fr['crop'] = [x0, y0, x1 - x0, y1 - y0]
            fr['file'] = seen[key]
        frames.append(fr)
    manifest = {
        'fixture': name,
        'canvas': [W, H],
        'window_ms': [pts_ms(first), pts_ms(first + count - 1)],
        'clip_frames': FRAMES,
        'fps': FPS,
        'background': bg,
        'fonts': 'free fonts in testdata/golden-ass/fonts' if fontmode == 'free' else 'none (embedded in the ASS file)',
        'renderer': 'ffmpeg libass subtitles filter (libass %s), FONTCONFIG_FILE limited to the fixture fonts' % libass,
        'cue_id': 'zero-based order of the Dialogue line in fixture.ass',
        'frames': frames,
    }
    with open(os.path.join(src, 'manifest.json'), 'w', newline='\n') as f:
        json.dump(manifest, f, separators=(',', ':'))
        f.write('\n')
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=DATA)
    ap.add_argument('--only')
    ap.add_argument('--scratch', required=True)
    a = ap.parse_args()
    libass = libass_line()
    print('libass', libass)
    for name, _b, bg, fontmode, n in load_fixtures():
        if a.only and name != a.only:
            continue
        src = os.path.join(a.out, name)
        for f in os.listdir(src):
            if f.endswith('.png'):
                os.remove(os.path.join(src, f))
        files = render(name, bg, fontmode, n or (0, FRAMES), a.out, a.scratch, libass)
        print('%-18s files=%d' % (name, files))


if __name__ == '__main__':
    main()
