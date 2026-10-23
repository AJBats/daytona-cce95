"""Side-by-side video: DUSA and patched CCE driven by the same input script.

Frames come from Mednafen -qtrecord movies (tools/record_replay.py),
extracted to PNG at 640x480. Each script line is `frame=<n> PRESS|RELEASE
<button>`; the bottom panel shows the inputs held at the current frame and a
scrolling timeline of the whole script.

Needs imageio-ffmpeg (pip install imageio-ffmpeg) for its bundled ffmpeg.

usage: sbs_video.py <out.mp4> [patched|camera|vanilla]   (right-hand game, default patched)
"""
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

DUSA_DIR, DUSA_SCRIPT, DUSA_LEAD = 'build/video/dusa_mov', 'build/slide_replay_L3.txt', 3
# right-hand game: frames, script, movie frames recorded before the state
# loaded, title, subtitle, timeline footnote
RIGHT = {
    'patched': ('build/video/cce_mov', 'build/slide_replay_cce3.txt', 3,
                'Daytona USA CCE  +  DUSA handling', 'patches 1–21, 30 Hz',
                'each lane: DUSA above, CCE below (CCE releases steering 1 frame sooner)'),
    'camera': ('build/video/cce_cam3_mov', 'build/slide_replay_cce3.txt', 3,
               'Daytona USA CCE  +  DUSA handling', 'patches 1–22: DUSA chase camera and lens',
               'each lane: DUSA above, CCE below (CCE releases steering 1 frame sooner)'),
    'vanilla': ('build/video/vanilla_mov', 'build/slide_replay_cce2.txt', 3,
                'Daytona USA CCE  (unmodified)', 'its own driving model, 30 Hz',
                'each lane: DUSA above, CCE below (identical timing)'),
}
DUSA_OFFSET = 20         # DUSA script frame = CCE script frame + 20 (brake press 128 vs 108)
BRAKE = 108              # CCE frame of the brake press
DUSA_ROWS, CCE_ROWS = (32, 432), (16, 464)   # picture rows; the rest is border
LANES = [('LEFT', 'LEFT', 'LEFT'), ('RIGHT', 'RIGHT', 'RIGHT'),
         ('GAS', 'C', 'B'), ('BRAKE', 'B', 'C')]   # label, DUSA button, CCE button
W, H = 1280, 720
VID_Y = 64
PANEL_Y = VID_Y + 480 + 4
BG, FG, DIM = (14, 16, 22), (235, 238, 245), (120, 126, 140)
ON = {'LEFT': (80, 170, 255), 'RIGHT': (80, 170, 255), 'GAS': (90, 210, 120), 'BRAKE': (240, 90, 80)}
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def held(script):
    """button -> list of (press, release) frame spans."""
    spans, down = {}, {}
    for line in open(script):
        if not line.startswith('frame='):
            continue
        f, kind, button = line.split()
        n = int(f.split('=')[1])
        if kind == 'PRESS':
            down[button] = n
        elif button in down:
            spans.setdefault(button, []).append((down.pop(button), n))
    for button, n in down.items():
        spans.setdefault(button, []).append((n, 10 ** 6))
    return spans


def is_down(spans, button, f):
    return any(a <= f < b for a, b in spans.get(button, []))


def main():
    out = sys.argv[1]
    cce_dir, cce_script, cce_lead, title, subtitle, footnote = RIGHT[sys.argv[2] if len(sys.argv) > 2 else 'patched']
    dusa, cce = held(DUSA_SCRIPT), held(cce_script)
    f_title, f_lab, f_small = ImageFont.truetype(BOLD, 22), ImageFont.truetype(BOLD, 18), ImageFont.truetype(FONT, 15)
    f_big = ImageFont.truetype(BOLD, 26)
    seq = [(f, 1) for f in range(40, 431)] + [(f, 2) for f in range(96, 340) for _ in (0, 1)]
    ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-f', 'rawvideo',
                           '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '59.94', '-i', '-',
                           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', out], stdin=subprocess.PIPE)
    for f, speed in seq:
        im = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(im)
        for x, path, (top, bottom) in ((0, f'{DUSA_DIR}/{f + DUSA_OFFSET + DUSA_LEAD:05d}.png', DUSA_ROWS),
                                       (640, f'{cce_dir}/{f + cce_lead:05d}.png', CCE_ROWS)):
            pic = Image.open(path).crop((0, top, 640, bottom))
            im.paste(pic, (x, VID_Y + (480 - (bottom - top)) // 2))
        d.text((16, 10), 'Daytona USA  (Saturn, 1995)', font=f_title, fill=FG)
        d.text((656, 10), title, font=f_title, fill=FG)
        d.text((16, 38), 'original driving model, 20 Hz', font=f_small, fill=DIM)
        d.text((656, 38), subtitle, font=f_small, fill=DIM)
        if speed == 2:
            d.text((W - 150, 36), '½ speed', font=f_lab, fill=(255, 200, 80))

        # current inputs
        x0, y0 = 24, PANEL_Y + 10
        d.text((x0, y0), 'SAME INPUTS', font=f_lab, fill=DIM)
        t = (f - BRAKE) / 59.94
        d.text((x0, y0 + 26), f't = {t:+.2f} s', font=f_big, fill=FG)
        d.text((x0, y0 + 60), 'from brake press', font=f_small, fill=DIM)
        bx = x0 + 190
        for i, (label, bd, bc) in enumerate(LANES):
            on = is_down(dusa, bd, f + DUSA_OFFSET) or is_down(cce, bc, f)
            box = (bx + i * 104, y0 + 22, bx + i * 104 + 96, y0 + 74)
            d.rounded_rectangle(box, 8, fill=ON[label] if on else (34, 38, 48),
                                outline=ON[label], width=2)
            text = {'LEFT': '◀', 'RIGHT': '▶'}.get(label, label)
            font = f_big if label in ('LEFT', 'RIGHT') else f_lab
            tw = d.textlength(text, font=font)
            d.text(((box[0] + box[2] - tw) / 2, y0 + 33), text, font=font,
                   fill=BG if on else ON[label])

        # timeline: 4 lanes, +-2 s around the playhead, one row per game
        tx, tw_, span = 720, 540, 240
        ty = PANEL_Y + 8
        d.text((tx, ty), 'input timeline', font=f_small, fill=DIM)
        for i, (label, bd, bc) in enumerate(LANES):
            for j, (spans, button, off) in enumerate(((dusa, bd, DUSA_OFFSET), (cce, bc, 0))):
                y = ty + 22 + i * 28 + j * 12
                d.rectangle((tx, y, tx + tw_, y + 10), fill=(28, 31, 40))
                for a, b in spans.get(button, []):
                    a, b = a - off, b - off
                    xa = tx + (a - f + span / 2) * tw_ / span
                    xb = tx + (b - f + span / 2) * tw_ / span
                    xa, xb = max(xa, tx), min(xb, tx + tw_)
                    if xb > xa:
                        d.rectangle((xa, y, xb, y + 10), fill=ON[label])
            d.text((tx - 64, ty + 21 + i * 28), label, font=f_small, fill=ON[label])
        px = tx + tw_ / 2
        d.line((px, ty + 18, px, ty + 22 + 4 * 28), fill=FG, width=2)
        d.text((tx - 64, ty + 22 + 4 * 28 + 4), footnote, font=f_small, fill=DIM)
        ff.stdin.write(im.tobytes())
    ff.stdin.close()
    ff.wait()
    print(out)


if __name__ == '__main__':
    main()
