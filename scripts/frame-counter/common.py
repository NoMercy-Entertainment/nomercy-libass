FPS_NUM, FPS_DEN = 24000, 1001
W, H, FRAMES = 1280, 720, 1439
SQ, NBITS = 32, 16
STRIP_W = SQ * NBITS
MARGIN, STRIP_Y = 20, 130
LEFT_X = MARGIN
RIGHT_X = W - MARGIN - STRIP_W
DIGIT_Y = 20
FONT = 'DejaVu Sans'


def bits(i):
    return [(i >> (NBITS - 1 - k)) & 1 for k in range(NBITS)]


def start_cs(i):
    # floor of (pts - 1 ms) in cs: ffmpeg truncates pts to ms, 30.03 s reads as 30029 ms
    return max(0, (i * FPS_DEN * 1000 - FPS_NUM) // (FPS_NUM * 10))
