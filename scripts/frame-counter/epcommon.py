import subprocess
import sys

# Geometry of the episode fixture: K13's 1280x720 layout scaled by 1.5 to 1920x1080.
SCALE = 1.5
W, H = 1920, 1080
SQ, NBITS = 48, 16
STRIP_W = SQ * NBITS
MARGIN, STRIP_Y = 30, 195
LEFT_X = MARGIN
RIGHT_X = W - MARGIN - STRIP_W
DIGIT_Y, FONT_SIZE = 18, 144
CROP_LEFT = '20,130,512,32'
CROP_RIGHT = '748,130,512,32'
OVERLAY_LAYER = 1000


def packet_pts(path):
    """Sorted video packet pts of a file or playlist, and its time base (num, den)."""
    def probe(entries):
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', entries,
                            '-of', 'csv=p=0', path], capture_output=True, text=True)
        if r.returncode:
            sys.exit('ffprobe failed: ' + r.stderr[-400:])
        return r.stdout.split()

    num, den = [int(v) for v in probe('stream=time_base')[0].split('/')]
    return sorted(int(v.strip(',')) for v in probe('packet=pts') if v.strip(',')), (num, den)


def frame_pts(path):
    """Sorted pts of the frames the decoder outputs (a packet may produce none), and the time base."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=pts', '-of', 'csv=p=0', path],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit('ffprobe failed: ' + r.stderr[-400:])
    return sorted(int(v.strip(',')) for v in r.stdout.split() if v.strip(','))


def start_cs(pts, tb):
    """Floor of (exact pts minus 1 ms) in centiseconds: ffmpeg reads 30.03 s as 30029 ms."""
    num, den = tb
    return max(0, (pts * num * 1000000 - 1000 * den) // (den * 10000))
