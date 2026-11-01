#!/usr/bin/env python3
"""Read the video number and the overlay number from every frame of a recording.

Each crop frames the 16-square strip (one number per crop). The difference is
overlay minus video, in frames. Stdlib plus ffmpeg only.

Usage: read-offsets.py REC.mp4 --crop-left x,y,w,h --crop-right x,y,w,h
         [--scale S] [--offset dx,dy] [--quiet] [--pairs FILE]
"""
import argparse
import subprocess
import sys

NBITS = 16


def cells(path, crop, scale, off):
    x, y, w, h = [float(v) for v in crop.split(',')]
    x, y, w, h = [int(round(v * scale)) for v in (x, y, w, h)]
    x, y = x + off[0], y + off[1]
    vf = 'crop=%d:%d:%d:%d,format=gray,scale=%d:1:flags=area' % (w, h, x, y, NBITS)
    r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-i', path, '-vf', vf, '-fps_mode', 'passthrough',
                        '-f', 'rawvideo', '-'], capture_output=True)
    if r.returncode:
        sys.exit('ffmpeg failed: ' + r.stderr.decode()[-400:])
    d = r.stdout
    return [d[k:k + NBITS] for k in range(0, len(d) - NBITS + 1, NBITS)]


def decode(c):
    """Index from 16 cell values, or None when the cells are not clearly black or white."""
    if any(64 <= v <= 192 for v in c):
        return None
    n = 0
    for v in c:
        n = (n << 1) | (1 if v > 128 else 0)
    return n


def pts_times(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=pts_time',
                        '-of', 'csv=p=0', path], capture_output=True, text=True)
    return [float(t.strip(',')) for t in r.stdout.split() if t.strip(',')]


def pct(sorted_vals, p):
    return sorted_vals[min(len(sorted_vals) - 1, int(p / 100.0 * len(sorted_vals)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--crop-left', required=True)
    ap.add_argument('--crop-right', required=True)
    ap.add_argument('--scale', type=float, default=1.0, help='recording pixels per 1280x720 pixel')
    ap.add_argument('--offset', default='0,0', help='letterbox offset dx,dy in recording pixels')
    ap.add_argument('--quiet', action='store_true', help='summary only')
    ap.add_argument('--pairs', help='write one line per frame to this file')
    a = ap.parse_args()
    off = [int(v) for v in a.offset.split(',')]
    left = cells(a.video, a.crop_left, a.scale, off)
    right = cells(a.video, a.crop_right, a.scale, off)
    times = pts_times(a.video)
    n = min(len(left), len(right))
    rows = []
    for k in range(n):
        v, o = decode(left[k]), decode(right[k])
        rows.append((k, times[k] if k < len(times) else float('nan'), v, o, None if v is None or o is None else o - v))
    lines = ['rec_frame pts_s video overlay diff']
    for r in rows:
        lines.append('%d %.4f %s %s %s' % (r[0], r[1], *('-' if x is None else x for x in r[2:])))
    if a.pairs:
        with open(a.pairs, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    if not a.quiet:
        print('\n'.join(lines))
    first = next((r[0] for r in rows if r[2] is not None), None)
    diffs = [r[4] for r in rows if r[4] is not None]
    print('recorded frames: %d, with both numbers: %d, no video number: %d, no overlay number: %d' % (
        n, len(diffs), sum(1 for r in rows if r[2] is None), sum(1 for r in rows if r[3] is None)))
    if not diffs:
        print('no readable frames')
        return 1
    sd = sorted(diffs)
    run = best = 0
    for r in rows:
        run = run + 1 if r[4] not in (0,) else 0
        best = max(best, run)
    print('share at 0: %.2f%%' % (100.0 * diffs.count(0) / len(diffs)))
    print('diff p50/p90/p99: %d / %d / %d (frames, signed, overlay minus video)' % (pct(sd, 50), pct(sd, 90), pct(sd, 99)))
    print('min/max diff: %d / %d' % (sd[0], sd[-1]))
    print('longest run of non-zero (incl. unreadable): %d recorded frames' % best)
    first_rows = [r for r in rows if r[0] >= first][:120]
    f0 = [r[4] for r in first_rows if r[4] is not None]
    print('first video number at recorded frame %d; of the next %d: at 0 = %d, non-zero = %d, overlay missing = %d' % (
        first, len(first_rows), f0.count(0), len([d for d in f0 if d != 0]), sum(1 for r in first_rows if r[3] is None)))
    return 0


sys.exit(main())
