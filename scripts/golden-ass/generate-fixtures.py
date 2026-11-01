#!/usr/bin/env python3
# -----------------------------------------------------------------------------
#  Copyright (c) NoMercy Entertainment
#
#  Licensed under the Apache License, Version 2.0. See LICENSE for details.
#
#  SPDX-License-Identifier: Apache-2.0
# -----------------------------------------------------------------------------

"""Build the synthetic golden ASS fixtures.

Every fixture is made-up text in a 1280x720 script, lasts 10 s and uses only the
free fonts in testdata/golden-ass/fonts (Arimo, Cousine, Gelasio, DejaVu Sans).
The output is byte-identical on every run: no clock, a fixed random seed.

Usage:
  generate-fixtures.py [--out DIR]
"""

import argparse
import base64
import io
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', '..', 'testdata', 'golden-ass')
W, H = 1280, 720
DURATION_CS = 1000

HEADER = """[Script Info]
; Synthetic fixture for the NoMercy golden ASS set. All text is made up.
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1280
PlayResY: 720
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}
{fonts}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def style(name, font='Arimo', size=48, primary='&H00FFFFFF', secondary='&H000000FF',
          outline='&H00101010', back='&H80000000', bold=0, italic=0, border=1, outl=2.5,
          shadow=1.5, align=2, margin_v=40, spacing=0):
    return ('Style: %s,%s,%d,%s,%s,%s,%s,%d,%d,0,0,100,100,%s,0,%d,%s,%s,%d,60,60,%d,1'
            % (name, font, size, primary, secondary, outline, back, bold, italic, spacing,
               border, outl, shadow, align, margin_v))


def cs(t):
    """Centiseconds to an ASS timestamp."""
    h, rest = divmod(t, 360000)
    m, rest = divmod(rest, 6000)
    s, c = divmod(rest, 100)
    return '%d:%02d:%02d.%02d' % (h, m, s, c)


def ev(start, end, text, st='Default', layer=0, name='', mv=0, effect=''):
    return 'Dialogue: %d,%s,%s,%s,%s,0,0,%d,%s,%s' % (layer, cs(start), cs(end), st, name, mv, effect, text)


def doc(title, styles, events, fonts=''):
    return HEADER.format(title=title, styles='\n'.join(styles), fonts=fonts) + '\n'.join(events) + '\n'


def uuencode(data):
    """ASS font encoding: 3 bytes to 4 characters of (6 bits + 33), 80 characters a line."""
    out = []
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3]
        n = len(chunk)
        v = int.from_bytes(chunk + b'\0' * (3 - n), 'big')
        chars = [(v >> s) & 63 for s in (18, 12, 6, 0)][:n + 1]
        out.append(''.join(chr(c + 33) for c in chars))
    s = ''.join(out)
    return '\n'.join(s[i:i + 80] for i in range(0, len(s), 80))


def f_static():
    st = [style('Default'), style('Top', align=8, margin_v=50, primary='&H0000F0FF'),
          style('Serif', font='Gelasio', size=54, italic=1)]
    e = [
        ev(0, 300, 'A quiet harbor at dawn.'),
        ev(300, 600, 'Two lines of dialogue\\Nwith a forced break.'),
        ev(600, 1000, 'Top aligned note in yellow.', 'Top'),
        ev(100, 900, '{\\i1}Italic{\\i0} and {\\b1}bold{\\b0} and {\\u1}underline{\\u0} and {\\s1}strike{\\s0}.', 'Default', 1, mv=110),
        ev(400, 1000, 'Serif italic line from Gelasio.', 'Serif', 0, mv=40),
        ev(0, 1000, '{\\an7\\pos(20,20)\\fs24\\c&H00FFFF&}top-left corner tag', 'Default', 2),
    ]
    return doc('static dialogue', st, e)


def f_sign_pos_move():
    st = [style('Default'), style('Sign', font='DejaVu Sans', size=60, bold=1, primary='&H0000A0FF', outl=3)]
    e = [
        ev(0, 1000, '{\\an5\\pos(640,120)}HARBOR MASTER', 'Sign'),
        ev(0, 1000, '{\\an1\\move(40,680,1240,680)\\fs36}sliding sign left to right', 'Default'),
        ev(100, 900, '{\\an5\\move(200,200,1080,520,1000,6000)\\fs44}moves between 1.0 s and 6.0 s', 'Default', 1),
        ev(0, 1000, '{\\an3\\move(1240,40,1240,300)\\fs32\\bord4}falls on the right edge', 'Sign', 2),
        ev(200, 1000, '{\\an5\\pos(640,360)\\fs120\\alpha&H80&}ghost', 'Default', 3),
    ]
    return doc('sign pos and move', st, e)


def f_transform():
    st = [style('Default', size=56)]
    e = [
        ev(0, 1000, '{\\an5\\pos(640,120)\\c&HFFFFFF&\\t(0,5000,\\c&H0000FF&)\\t(5000,10000,\\c&H00FF00&)}color shift', 'Default'),
        ev(0, 1000, '{\\an5\\pos(640,240)\\fscx50\\fscy50\\t(0,10000,\\fscx150\\fscy150)}scale up', 'Default', 1),
        ev(0, 1000, '{\\an5\\pos(640,360)\\blur0\\bord1\\t(0,10000,\\blur8\\bord6)}blur and border', 'Default', 2),
        ev(0, 1000, '{\\an5\\pos(640,480)\\alpha&HFF&\\t(0,5000,\\alpha&H00&)\\t(5000,10000,\\alpha&HFF&)}alpha in and out', 'Default', 3),
        ev(0, 1000, '{\\an5\\pos(640,600)\\fad(1500,1500)\\fry0\\t(0,10000,\\fry360)}fade and fry rotation', 'Default', 4),
        ev(0, 1000, '{\\an5\\pos(1100,360)\\frz0\\t(0,10000,\\frz-720)\\fs40}spin', 'Default', 5),
    ]
    return doc('transform', st, e)


def f_paper():
    st = [style('Paper', font='Gelasio', size=84, bold=1, primary='&H00202020', outline='&H00FFFFFF', outl=3, shadow=0)]
    e = [
        ev(0, 1000, '{\\an5\\move(420,330,860,390)\\frz12\\clip(0,0,320,720)\\t(0,10000,\\clip(960,0,1280,720))}'
                    'PAPER SWEEP LINE ONE\\NPAPER SWEEP LINE TWO', 'Paper'),
        ev(0, 1000, '{\\an5\\pos(640,640)\\frz-4\\fs40\\clip(1280,0,1280,720)\\t(0,10000,\\clip(0,0,1280,720))}'
                    'a reveal wipe from the left edge', 'Paper', 1),
    ]
    return doc('rotated moving paper with moving clip', st, e)


def f_scroll():
    st = [style('Msg', font='Arimo', size=34, primary='&H00FFFFFF', outline='&H00402000', outl=2, shadow=0, align=4)]
    names = ['Ada', 'Ben', 'Cleo', 'Dev', 'Eli', 'Fay', 'Gus', 'Hana', 'Ivo', 'Jun', 'Kit', 'Lea']
    texts = ['are you there', 'the tide is in', 'bring the lamp', 'meet at pier nine', 'sending the map',
             'ok on my way', 'did you see that', 'later then', 'ping me back', 'nice one', 'on it', 'see you soon']
    e = []
    for i in range(12):
        y0 = 740 + i * 70
        e.append(ev(0, 1000, '{\\an4\\move(120,%d,120,%d)}%s: %s' % (y0, y0 - 1100, names[i], texts[i]), 'Msg', i % 3))
    return doc('scrolling message list', st, e)


def f_karaoke():
    st = [style('K', size=64, primary='&H0000FFFF', secondary='&H00FFFFFF', outline='&H00402000', outl=3)]
    e = [
        ev(0, 330, '{\\k40}Row{\\k40} row{\\k40} row{\\k40} your{\\k60} boat{\\k80} gent{\\k60}ly', 'K'),
        ev(330, 660, '{\\kf50}Down{\\kf50} the{\\kf90} stream{\\kf40} mer{\\kf40}ri{\\kf40}ly', 'K', 0, mv=0),
        ev(660, 1000, '{\\ko60}Life{\\ko60} is{\\ko80} but{\\ko100} a{\\ko100} dream', 'K'),
        ev(0, 1000, '{\\an8\\pos(640,60)\\fs28\\k100}top{\\k100} line{\\k100} that{\\k100} runs{\\k100} the{\\k100} whole{\\k100} clip', 'K', 1),
    ]
    return doc('karaoke', st, e)


def f_drawing():
    st = [style('D', size=40)]
    star = 'm 0 -60 l 18 -20 l 60 -18 l 28 10 l 38 54 l 0 30 l -38 54 l -28 10 l -60 -18 l -18 -20'
    rrect = 'm 0 0 l 200 0 b 220 0 220 0 220 20 l 220 100 b 220 120 220 120 200 120 l 20 120 b 0 120 0 120 0 100 l 0 20 b 0 0 0 0 20 0'
    e = [
        ev(0, 1000, '{\\an7\\pos(100,100)\\1c&H00A0FF&\\bord0\\shad0\\p1}%s{\\p0}' % rrect, 'D'),
        ev(0, 1000, '{\\an5\\move(400,200,1000,500)\\frz0\\t(0,10000,\\frz360)\\1c&H00FFFF&\\3c&H000000&\\bord3\\p1}%s{\\p0}' % star, 'D', 1),
        ev(0, 1000, '{\\an7\\pos(100,300)\\1c&HFF8000&\\t(0,10000,\\1c&H0000FF&)\\bord0\\shad0\\p2}%s{\\p0}' % rrect, 'D', 0),
        ev(0, 1000, '{\\an5\\pos(1100,600)\\pbo-20\\1c&H00FF00&\\p1}m 0 0 l 120 0 120 80 0 80{\\p0}', 'D', 2),
    ]
    return doc('drawing', st, e)


def f_styles_fallback():
    st = [style('Sans', font='Arimo'), style('Mono', font='Cousine', size=44, align=8, margin_v=50),
          style('Serif', font='Gelasio', size=52, align=5), style('Dej', font='DejaVu Sans', size=46, align=1, margin_v=60),
          style('Missing', font='No Such Face Anywhere', size=50, align=3, margin_v=60)]
    e = [
        ev(0, 1000, 'Arimo default style', 'Sans'),
        ev(0, 1000, 'Cousine mono 0123456789', 'Mono'),
        ev(0, 1000, 'Gelasio serif centered', 'Serif'),
        ev(0, 1000, 'DejaVu Sans bottom left', 'Dej'),
        ev(0, 1000, 'Missing family falls back', 'Missing'),
        ev(300, 800, '{\\fnCousine\\an4\\pos(60,420)}inline font override {\\fnGelasio}then another', 'Sans', 1),
        ev(500, 1000, '{\\an6\\pos(1220,300)}accents: éèüñ ß — “quotes”', 'Dej', 1),
    ]
    return doc('multiple styles and fallback font', st, e)


def f_embedded_font():
    from fontTools import subset
    from fontTools.ttLib import TTFont
    src = os.path.join(DATA, 'fonts', 'cousine_regular.ttf')
    opts = subset.Options()
    opts.name_IDs = ['*']
    opts.notdef_outline = True
    opts.layout_features = []
    font = TTFont(src, recalcTimestamp=False)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=list(range(0x20, 0x7f)))
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    fonts = '[Fonts]\nfontname: cousine_regular.ttf\n%s\n' % uuencode(buf.getvalue())
    st = [style('Emb', font='Cousine', size=64, align=5)]
    e = [
        ev(0, 1000, 'Embedded font text 0123456789', 'Emb'),
        ev(200, 1000, '{\\an2}the font ships inside the ASS file', 'Emb', 1),
    ]
    return doc('embedded font', st, e, fonts)


def f_many_events():
    rnd = random.Random(1001)
    words = ['tide', 'lamp', 'pier', 'salt', 'rope', 'mast', 'sail', 'wind', 'gull', 'keel', 'buoy', 'fog']
    st = [style('S', size=22, outl=1.2, shadow=0)]
    e = []
    for i in range(5000):
        start = rnd.randrange(0, 960)
        end = min(DURATION_CS, start + rnd.randrange(20, 60))
        x, y = rnd.randrange(40, 1180), rnd.randrange(30, 690)
        e.append(ev(start, end, '{\\an7\\pos(%d,%d)}%s %d' % (x, y, rnd.choice(words), i), 'S', i % 4))
    return doc('very large event count', st, e)


def f_layers():
    st = [style('L', size=60)]
    e = [
        ev(0, 1000, '{\\an7\\pos(300,150)\\1c&H0000FF&\\1a&H40&\\bord0\\shad0\\p1}m 0 0 l 220 0 220 160 0 160{\\p0}', 'L', 0),
        ev(0, 1000, '{\\an7\\pos(380,210)\\1c&H00FF00&\\1a&H40&\\bord0\\shad0\\p1}m 0 0 l 220 0 220 160 0 160{\\p0}', 'L', 1),
        ev(200, 1000, '{\\an7\\pos(460,270)\\1c&HFF0000&\\1a&H40&\\bord0\\shad0\\p1}m 0 0 l 220 0 220 160 0 160{\\p0}', 'L', 2),
        ev(0, 1000, '{\\an5\\pos(440,300)\\fs36}layer 3 text above', 'L', 3),
        ev(0, 1000, '{\\an5\\pos(460,320)\\fs36\\c&H00FFFF&}layer 3 second', 'L', 3),
        ev(400, 800, '{\\an5\\pos(440,420)\\fs36}overlap in time', 'L', 0),
        ev(500, 900, '{\\an5\\pos(440,430)\\fs36\\c&H00FF00&}overlap in time', 'L', 0),
        ev(0, 1000, '{\\an2\\move(300,690,980,690)\\fs36}collision test moving', 'L', 5),
        ev(0, 1000, '{\\an2\\fs36}collision test static bottom', 'L', 5),
    ]
    return doc('overlapping events and layers', st, e)


def f_track_full():
    lines = ['Good morning, captain.', 'The boat is ready at the pier.', 'We sail when the fog lifts.',
             'Check the ropes twice.', 'Did anyone bring the lamp?', 'It is in the cabin.',
             'Then we have everything.', 'Hold on tight, here we go.']
    e = []
    for i, t in enumerate(lines):
        s = i * 120
        e.append(ev(s, s + 110, t if i % 3 else t + '\\Nsecond line of the same cue'))
    return doc('track full', [style('Default')], e)


def f_track_sign():
    st = [style('Default'), style('Sign', font='DejaVu Sans', size=54, bold=1, primary='&H0000C0FF', outl=3)]
    e = [
        ev(0, 400, '{\\an8\\pos(640,100)}WELCOME TO PIER NINE', 'Sign'),
        ev(200, 700, '{\\an1\\pos(60,690)\\fs30}Open 6 to 9', 'Sign', 1),
        ev(500, 1000, '{\\an9\\pos(1220,50)\\fs36}Gate B', 'Sign'),
    ]
    return doc('track sign', st, e)


def f_track_sdh():
    st = [style('Default'), style('Sdh', font='Cousine', size=42, italic=1, primary='&H00D0FFD0')]
    e = [
        ev(0, 250, '[gentle waves]', 'Sdh'),
        ev(150, 500, 'CAPTAIN: Raise the sail.'),
        ev(300, 650, '[rope creaking]', 'Sdh', 1, mv=110),
        ev(550, 800, '♪ soft harbor music ♪', 'Sdh'),
        ev(750, 1000, 'MATE: [whispering] Quiet now.'),
    ]
    return doc('track sdh', st, e)


def f_track_alt():
    st = [style('Alt', font='Gelasio', size=46, align=8, margin_v=40, primary='&H0080FFFF', outline='&H00402000')]
    e = [
        ev(0, 300, 'Alternate track: the harbor wakes.', 'Alt'),
        ev(300, 650, 'Alternate track: lines sit at the top.\\Nand use a serif face.', 'Alt'),
        ev(650, 1000, 'Alternate track: the last cue.', 'Alt'),
    ]
    return doc('track alt', st, e)


def f_track_forced():
    st = [style('Forced', size=52, bold=1)]
    e = [
        ev(100, 350, 'Forced: the sign reads CLOSED.', 'Forced'),
        ev(500, 800, 'Forced: a foreign phrase.', 'Forced'),
    ]
    return doc('track forced', st, e)


# name, builder, background, font set, stills window (first frame, count); None = all 240
FIXTURES = [
    ('static-dialogue', f_static, 'black', 'free', None),
    ('sign-pos-move', f_sign_pos_move, 'black', 'free', (24, 20)),
    ('transform', f_transform, 'black', 'free', (100, 20)),
    ('paper-frz-clip', f_paper, 'black', 'free', (100, 20)),
    ('scroll-messages', f_scroll, 'black', 'free', (60, 20)),
    ('karaoke', f_karaoke, 'black', 'free', (40, 32)),
    ('drawing', f_drawing, 'black', 'free', (0, 48)),
    ('styles-fallback', f_styles_fallback, 'black', 'free', None),
    ('embedded-font', f_embedded_font, 'black', 'none', None),
    ('many-events', f_many_events, 'black', 'free', (120, 4)),
    ('layers-overlap', f_layers, 'gradient', 'free', (60, 16)),
    ('track-full', f_track_full, 'black', 'free', None),
    ('track-sign', f_track_sign, 'black', 'free', None),
    ('track-sdh', f_track_sdh, 'black', 'free', None),
    ('track-alt', f_track_alt, 'black', 'free', None),
    ('track-forced', f_track_forced, 'black', 'free', None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=DATA)
    a = ap.parse_args()
    for name, build, _bg, _fonts, _n in FIXTURES:
        d = os.path.join(a.out, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'fixture.ass'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(build())
        print('wrote', name)


if __name__ == '__main__':
    main()
