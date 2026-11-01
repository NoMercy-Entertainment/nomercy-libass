#!/usr/bin/env python3
"""Burn the frame-counter ASS into the clip with ffmpeg libass (the reference).

Usage: render-reference.py CLIP.mp4 COUNTER.ass OUT.mp4 FONT.ttf [WORKDIR]
"""
import os
import shutil
import subprocess
import sys

clip, ass, out, font = [os.path.abspath(p) for p in sys.argv[1:5]]
work = os.path.abspath(sys.argv[5]) if len(sys.argv) > 5 else os.path.join(os.path.dirname(out), 'ref-work')
os.makedirs(os.path.join(work, 'fonts'), exist_ok=True)
shutil.copy(font, os.path.join(work, 'fonts'))
shutil.copy(ass, os.path.join(work, 'counter.ass'))
conf = os.path.join(work, 'fonts.conf')
with open(conf, 'w') as f:
    f.write('<?xml version="1.0"?><fontconfig><dir>%s</dir><cachedir>%s</cachedir></fontconfig>'
            % (os.path.join(work, 'fonts').replace(chr(92), '/'), os.path.join(work, 'cache').replace(chr(92), '/')))
env = dict(os.environ, FONTCONFIG_FILE=conf)
r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', '-i', clip,
                    '-vf', 'subtitles=filename=counter.ass:fontsdir=fonts,format=yuv420p',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '12', '-an', '-fps_mode', 'passthrough', out],
                   cwd=work, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit('ffmpeg failed: ' + r.stderr[-800:])
