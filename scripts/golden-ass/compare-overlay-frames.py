#!/usr/bin/env python3
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------

"""Compare captured subtitle overlay frames with the ffmpeg reference stills.

The reference is subtitles-libass/testdata/moving-ass-s02e11 (manifest.json plus
PNG crops on a 1920x1080 black canvas). A capture is a folder of PNG crops with
the same manifest format, where pts_ms is the presented-frame time the player
claims for that overlay.

For each captured frame the script prints the pixel diff against the reference
frame at the same pts, and the offset in ms to the best matching reference frame
(searched within --search frames). Ties pick the smallest offset, and a frame
whose best match is not unique is flagged "ambiguous" (static content has no
timing signal).

Usage:
  compare-overlay-frames.py --capture DIR [--capture-manifest FILE] [--ref DIR]
                            [--search N] [--all] [--shift-frames K]
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REF = os.path.join(HERE, '..', 'subtitles-libass', 'testdata', 'moving-ass-s02e11')


class Set:
    def __init__(self, directory, manifest_path=None):
        self.dir = directory
        with open(manifest_path or os.path.join(directory, 'manifest.json')) as f:
            self.m = json.load(f)
        self.frames = self.m['frames']
        self.w, self.h = self.m['canvas']
        self._cache = {}

    def image(self, i):
        fr = self.frames[i]
        if fr['file'] is None:
            return None
        a = self._cache.get(fr['file'])
        if a is None:
            a = np.array(Image.open(os.path.join(self.dir, fr['file'])).convert('RGB')).astype(np.int16)
            self._cache[fr['file']] = a
        return a

    def box(self, i):
        c = self.frames[i]['crop']
        return None if c is None else (c[0], c[1], c[0] + c[2], c[1] + c[3])


_memo = {}


def diff(a, ia, b, ib):
    """Count of differing pixels between frame ia of Set a and frame ib of Set b."""
    ka = (a.dir, a.frames[ia]['file'], tuple(a.frames[ia]['crop'] or ()))
    kb = (b.dir, b.frames[ib]['file'], tuple(b.frames[ib]['crop'] or ()))
    if (ka, kb) not in _memo:
        _memo[(ka, kb)] = _diff(a, ia, b, ib)
    return _memo[(ka, kb)]


def _diff(a, ia, b, ib):
    ba, bb = a.box(ia), b.box(ib)
    if ba is None and bb is None:
        return 0
    boxes = [x for x in (ba, bb) if x]
    x0 = min(x[0] for x in boxes)
    y0 = min(x[1] for x in boxes)
    x1 = max(x[2] for x in boxes)
    y1 = max(x[3] for x in boxes)
    ca = np.zeros((y1 - y0, x1 - x0, 3), np.int16)
    cb = np.zeros_like(ca)
    for s, i, bx, c in ((a, ia, ba, ca), (b, ib, bb, cb)):
        if bx:
            c[bx[1] - y0:bx[3] - y0, bx[0] - x0:bx[2] - x0] = s.image(i)
    return int((np.abs(ca - cb).max(axis=2) > 0).sum())


def pct(v, p):
    return float(np.percentile(np.array(v, dtype=float), p)) if v else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--capture', required=True)
    ap.add_argument('--capture-manifest')
    ap.add_argument('--ref', default=DEFAULT_REF)
    ap.add_argument('--search', type=int, default=6)
    ap.add_argument('--all', action='store_true', help='print every frame, not only those with diff or offset')
    ap.add_argument('--shift-frames', type=int, default=0,
                    help='self-test: label the capture frames as if they were shown K frames late')
    a = ap.parse_args()

    ref = Set(a.ref)
    cap = Set(a.capture, a.capture_manifest)
    if a.shift_frames:
        # Keep each frame's pts and move the content K frames: the player showed frame i+K at time i.
        k = a.shift_frames
        n = len(cap.frames)
        moved = []
        for i in range(n):
            src = cap.frames[min(max(i + k, 0), n - 1)]
            moved.append(dict(src, index=i, pts_ms=cap.frames[i]['pts_ms']))
        cap.frames = moved

    ref_pts = [f['pts_ms'] for f in ref.frames]
    by_pts = {p: i for i, p in enumerate(ref_pts)}
    diffs, offs, rows, ambiguous, missing = [], [], [], 0, 0
    for ci, cf in enumerate(cap.frames):
        ri = by_pts.get(cf['pts_ms'])
        if ri is None:
            ri = int(np.argmin([abs(p - cf['pts_ms']) for p in ref_pts]))
            if abs(ref_pts[ri] - cf['pts_ms']) > 21:
                missing += 1
                continue
        d0 = diff(cap, ci, ref, ri)
        cands = []
        for rj in range(max(0, ri - a.search), min(len(ref.frames), ri + a.search + 1)):
            cands.append((diff(cap, ci, ref, rj), abs(rj - ri), rj))
        cands.sort()
        best = cands[0]
        tie = [c for c in cands if c[0] == best[0]]
        amb = len(tie) > 1 and any(c[1] != best[1] for c in tie) and best[1] != 0
        if len(tie) > 1 and best[0] == d0:
            best = min(tie, key=lambda c: c[1])
        off_frames = best[2] - ri
        off_ms = ref_pts[best[2]] - ref_pts[ri]
        if len(tie) > 1:
            ambiguous += 1
        diffs.append(d0)
        offs.append(abs(off_ms))
        if a.all or d0 or off_frames:
            rows.append((cf['index'], cf['pts_ms'], d0, off_frames, off_ms, 'ambiguous' if len(tie) > 1 else ''))

    print('frame  pts_ms  diff_px  offset_frames  offset_ms')
    for r in rows:
        print('%5d %7d %8d %8d %10d  %s' % r)
    n = len(diffs)
    print('frames=%d missing_pts=%d ambiguous=%d' % (n, missing, ambiguous))
    print('diff_px   max=%d p99=%.1f frames_with_diff=%d' % (max(diffs or [0]), pct(diffs, 99), sum(1 for d in diffs if d)))
    print('offset_ms max=%d p99=%.1f frames_with_offset=%d' % (max(offs or [0]), pct(offs, 99), sum(1 for o in offs if o)))
    nz = [o for o in offs if o]
    if nz:
        print('offset_ms median_of_nonzero=%d' % int(np.median(nz)))
    return 0 if not any(diffs) and not any(offs) else 1


if __name__ == '__main__':
    sys.exit(main())
