#!/usr/bin/env python3
"""Burn an ASS file into the episode fixture with ffmpeg libass, the way the K6 reference run did.

Usage: ep-render.py VIDEO.mp4 FILE.ass FONTS_DIR OUT.mp4 [WORKDIR]
The fonts come from FONTS_DIR only (FONTCONFIG_FILE limits the lookup to it).
"""
import os
import shutil
import subprocess
import sys

video, ass, fonts, out = [os.path.abspath(p) for p in sys.argv[1:5]]
work = os.path.abspath(sys.argv[5]) if len(sys.argv) > 5 else os.path.join(os.path.dirname(out), 'render-work')
os.makedirs(work, exist_ok=True)
shutil.copytree(fonts, os.path.join(work, 'fonts'), dirs_exist_ok=True)
shutil.copy(ass, os.path.join(work, 'sub.ass'))
conf = os.path.join(work, 'fonts.conf')
with open(conf, 'w') as f:
    f.write('<?xml version="1.0"?><fontconfig><dir>%s</dir><cachedir>%s</cachedir></fontconfig>'
            % (os.path.join(work, 'fonts').replace(chr(92), '/'), os.path.join(work, 'cache').replace(chr(92), '/')))
env = dict(os.environ, FONTCONFIG_FILE=conf)
r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'info', '-y', '-copyts', '-i', video,
                    '-vf', 'subtitles=filename=sub.ass:fontsdir=fonts,format=yuv420p',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-qp', '10', '-an', '-fps_mode', 'passthrough', out],
                   cwd=work, env=env, capture_output=True, text=True)
if r.returncode:
    sys.exit('ffmpeg failed: ' + r.stderr[-800:])
print('rendered', out)
