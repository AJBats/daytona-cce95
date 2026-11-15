"""Options > KEY CONFIG, what CCE95 adds: STEERING : AUTO / WHEEL / STICK under
each player's TYPE E (patches/steering_choice.s), appended to DAYTONA/OPT.DAT
after tools/options_sound.py's block.

usage: options_keys.py <cce extracted dir> <out dir>
  Rewrites <out dir>/DAYTONA/OPT.DAT (options_sound.py's), with this page's
  code and pictures at KEYS_AT.

The page (SLCT.BIN 06031AE8) has no cursor: each player's own pad steps
their TYPE with up and down (002FD72B + 3 x player + device), and A, B, C or
Start on the first pad leaves. Left and right now step the player's
STEERING (002FE7C0 + player, patches/save_ext.s), on the pad, the 3D pad or
the Arcade Racer, whose wheel sets left and right when turned.

Its text is two planes of boxes 3 cells high: PLAYER and the TYPE boxes on
one (map 25E60000, chars from VRAM 0xA000), the button labels on the other
(map 25E68000, chars from VRAM 0). Under TYPE E (y 27 for player 1, 48 for
player 2) each player has an empty row before the next block, empty in the
labels' column too for all three diagrams. The row is drawn on the labels'
plane, in their face: STEERING at x 20 (PLAYER's column) and the value at x
33 (the labels'). The words are put together from letters of the labels
(ACCEL, BRAKE, DOWN VIEW, NOT USED, SHIFT UP; label chars from OPT.DAT's
0x294E30, their pictures from 0x296D74, 3 x 10 cells each) and the G of the
main page's GAME MODE, the same face two rows higher. Their new chars go to
VRAM 0x6000 (cell 0x300 on), which nothing uses while the page is up; the
draw copies them in each time.

The code runs from KEYS_AT, where patches/steering_menu.s points SLCT.BIN:
OPT.DAT is loaded at 0x250000 while Options is up, and nothing reads or
writes work RAM from its end to 0x2E0000 then (checked through the three
pages). options_sound.py's block must end before KEYS_AT.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import sh2asm  # noqa: E402

OPT_AT = 0x250000
KEYS_AT = 0x2B1000                  # patches/steering_menu.s jumps here
LABEL_CHARS, LABEL_N = 0x294E30, 250
LABELS = {'ACCEL': 0, 'BRAKE': 1, 'DOWN VIEW': 2, 'NOT USED': 3, 'SHIFT UP': 5}
LABEL_PICS = 0x296D74               # 3 x 10 cells a label
MAIN_CHARS, GAME_MODE = 0x264B04, (0x26C354, 18)
NEW_CELL, NEW_END = 0x300, 0x500    # VRAM 0x6000 up to the TYPE chars at 0xA000
# letter: (word, first column, end), each from the dark column before it
LETTERS = {'S': ('SHIFT UP', 2, 11), 'H': ('SHIFT UP', 11, 21), 'I': ('SHIFT UP', 22, 30),
           'T': ('NOT USED', 21, 31), 'N': ('NOT USED', 1, 11), 'O': ('NOT USED', 11, 21),
           'U': ('NOT USED', 36, 47), 'E': ('BRAKE', 41, 51), 'R': ('BRAKE', 11, 21),
           'K': ('BRAKE', 31, 41), 'A': ('ACCEL', 2, 12), 'C': ('ACCEL', 12, 22),
           'L': ('ACCEL', 42, 52), 'W': ('DOWN VIEW', 68, 78), 'G': ('GAME MODE', 1, 12)}
G_DROP = 2                          # the main page's letters sit two rows higher
LEFT_END, RIGHT_END = ('ACCEL', 0, 2), ('ACCEL', 52, 56)    # the box's ends, the last letter's dark column
VALUES = ['AUTO', 'WHEEL', 'STICK']
LABEL_X, VALUE_X, ROW_Y, ROW_STEP = 20, 33, 30, 21


def render(opt, chars, at, w):
    cells = np.array(struct.unpack_from(f'>{3 * w}H', opt, at - OPT_AT)).reshape(3, w)
    img = np.zeros((24, 8 * w), np.uint8)
    for r in range(3):
        for c in range(w):
            t = np.frombuffer(opt, np.uint8, 32, chars - OPT_AT + 32 * int(cells[r, c]))
            img[8 * r:8 * r + 8, 8 * c:8 * c + 8] = np.stack([t >> 4, t & 15], 1).reshape(8, 8)
    return img


def word(words, text):
    def cut(w, a, b, drop=0):
        img = words[w][:, a:b]
        return np.concatenate([np.zeros((drop, img.shape[1]), np.uint8), img[:24 - drop]]) if drop else img
    parts = [cut(*LEFT_END)] + [cut(*LETTERS[ch], drop=G_DROP if ch == 'G' else 0) for ch in text]
    img = np.concatenate(parts + [cut(*RIGHT_END)], 1)
    return np.pad(img, ((0, 0), (0, -img.shape[1] % 8)))


class Chars:
    """The labels' chars: a char's 32 bytes -> its cell, new ones from NEW_CELL."""

    def __init__(self, opt):
        self.cell = {}
        for c in range(LABEL_N):
            self.cell.setdefault(bytes(opt[LABEL_CHARS - OPT_AT + 32 * c:LABEL_CHARS - OPT_AT + 32 * c + 32]), c)
        self.new = []

    def cells(self, img, w):
        out = np.zeros((3, w), np.uint16)
        for r in range(3):
            for c in range(img.shape[1] // 8):
                px = img[8 * r:8 * r + 8, 8 * c:8 * c + 8]
                t = bytes((px[:, 0::2] << 4 | px[:, 1::2]).astype(np.uint8).ravel())
                if t not in self.cell:
                    self.cell[t] = NEW_CELL + len(self.new)
                    self.new.append(t)
                out[r, c] = self.cell[t]
        assert NEW_CELL + len(self.new) <= NEW_END, 'options_keys: no room for the new chars'
        return out


CODE = '''
.org {keys_at:08X}
    bra    kc_tail
    nop
    bra    kc_sides
    nop

; patches/steering_menu.s: 06032378, which draws a player's TYPE boxes, ends
; here instead of its epilogue (r4 = the player, its stack as at 06032412):
; the epilogue, the player's STEERING row, then the button labels as before.
kc_tail:
    add    #8,r15
    lds.l  @r15+,macl
    lds.l  @r15+,pr
    mov.l  @r15+,r8
    mov.l  @r15+,r9
    mov.l  @r15+,r10
    mov.l  @r15+,r11
    mov.l  @r15+,r12
    mov.l  @r15+,r13
    mov.l  @r15+,r14
    sts.l  pr,@-r15
    mov.l  r4,@-r15
    bsr    draw_steering
    nop
    mov.l  @r15+,r4
    lds.l  @r15+,pr
    mov.l  labels_at,r0
    jmp    @r0
    nop

; patches/steering_menu.s: the page's input calls here before its loop over
; the players (06031C2C; its stack holds the buttons each port pressed this
; frame, longs at +8 and +12). Left and right step that player's STEERING,
; with the page's sound for a step, and redraw its row. Then what the
; replaced steps set: r12 = 002FD72B, r14 = r8, r0 = r9.
kc_sides:
    sts.l  pr,@-r15
    mov.l  r13,@-r15
    mov    r15,r13
    add    #16,r13          ; the buttons, port 1's
    mov    #0,r14
sides_next:
    mov.l  @r13+,r1
    mov.w  k_left,r2
    tst    r2,r1
    bf     step_left
    mov.w  k_right,r2
    tst    r2,r1
    bt     sides_done
    bra    step
    mov    #1,r3            ; the next
step_left:
    mov    #2,r3            ; the one before
step:
    mov.l  choice_at,r1
    add    r14,r1
    mov.b  @r1,r0
    mov    #2,r2
    cmp/hi r2,r0
    bf     in_range
    mov    #0,r0            ; not a choice: AUTO
in_range:
    add    r3,r0
    mov    #3,r2
    cmp/hs r2,r0
    bf     stepped
    add    #-3,r0
stepped:
    mov.b  r0,@r1
    mov    #1,r6
    mov    r6,r5
    mov.l  sound_at,r1
    jsr    @r1
    mov    #0,r4
    bsr    draw_steering
    mov    r14,r4
sides_done:
    add    #1,r14
    mov    r14,r0
    cmp/eq #2,r0
    bf     sides_next
    mov.l  @r15+,r13
    lds.l  @r15+,pr
    mov.l  types_at,r12
    mov    r8,r14
    rts
    mov    r9,r0

; r4 = the player: the new chars into VRAM, then STEERING and the choice.
draw_steering:
    sts.l  pr,@-r15
    mov.l  r14,@-r15
    mov.l  r13,@-r15
    mov    r4,r14
    mov.l  chars_from,r1
    mov.l  chars_to,r2
    mov.w  chars_longs,r3
copy:
    mov.l  @r1+,r0
    dt     r3
    mov.l  r0,@r2
    bf/s   copy
    add    #4,r2
    mov    #{row_step},r0
    mulu.w r0,r14
    sts    macl,r13
    add    #{row_y},r13     ; the row
    mov.l  label_at,r4
    mov    #{label_x},r6
    bsr    box
    mov    #{label_w},r0
    mov.l  choice_at,r1
    add    r14,r1
    mov.b  @r1,r0
    mov    #2,r2
    cmp/hi r2,r0
    bf     shown
    mov    #0,r0
shown:
    mov.w  value_bytes,r1
    mulu.w r1,r0
    sts    macl,r0
    mov.l  values_at,r4
    add    r0,r4
    mov    #{value_x},r6
    bsr    box
    mov    #{value_w},r0
    mov.l  @r15+,r13
    mov.l  @r15+,r14
    lds.l  @r15+,pr
    rts
    nop

; r4 the cells, r6 x, r13 y, r0 the width: a box on the labels' plane, lit,
; through the page's text routine (0602991C), as the page draws its own.
box:
    sts.l  pr,@-r15
    mov.w  k_lit,r1
    mov.l  r1,@-r15
    mov.l  char_base,r1
    mov.l  r1,@-r15
    mov    #3,r1
    mov.l  r1,@-r15
    mov.l  r0,@-r15
    mov.l  map_at,r5
    mov    r13,r7
    mov.l  text_at,r1
    jsr    @r1
    nop
    add    #16,r15
    lds.l  @r15+,pr
    rts
    nop
k_left:
    .word  0x4000
k_right:
    .word  0x8000
k_lit:
    .word  0x0090
chars_longs:
    .word  {chars_longs}
value_bytes:
    .word  {value_bytes}
.align 4
labels_at:
    .long  0x060325D4
types_at:
    .long  0x002FD72B
choice_at:
    .long  0x002FE7C0
sound_at:
    .long  0x0600795A
text_at:
    .long  0x0602991C
char_base:
    .long  0x25E00000
map_at:
    .long  0x25E68000
chars_to:
    .long  {chars_to:#010x}
chars_from:
    .long  new_chars
label_at:
    .long  label_cells
values_at:
    .long  value_cells
'''


def words_of(name, data, size='word'):
    n = 2 if size == 'word' else 4
    fmt = '>H' if n == 2 else '>I'
    return [f'{name}:'] + [f'    .{size}  0x{struct.unpack_from(fmt, data, i)[0]:0{2 * n}X}'
                           for i in range(0, len(data), n)]


def build(opt):
    words = {name: render(opt, LABEL_CHARS, LABEL_PICS + 60 * i, 10) for name, i in LABELS.items()}
    words['GAME MODE'] = render(opt, MAIN_CHARS, *GAME_MODE)
    chars = Chars(opt)
    label_img = word(words, 'STEERING')
    label_w = label_img.shape[1] // 8
    assert LABEL_X + label_w <= VALUE_X, f'STEERING runs into the labels\' column ({label_w} cells)'
    label = chars.cells(label_img, label_w)
    imgs = [word(words, v) for v in VALUES]
    value_w = max(img.shape[1] // 8 for img in imgs)
    values = [chars.cells(img, value_w) for img in imgs]   # the narrower ones end in blank cells

    src = CODE.format(keys_at=KEYS_AT, row_step=ROW_STEP, row_y=ROW_Y, label_x=LABEL_X, label_w=label_w,
                      value_x=VALUE_X, value_w=value_w, value_bytes=6 * value_w,
                      chars_longs=8 * len(chars.new), chars_to=0x25E00000 + 32 * NEW_CELL).splitlines()
    src += ['.align 4'] + words_of('label_cells', label.astype('>u2').tobytes())
    src += words_of('value_cells', b''.join(v.astype('>u2').tobytes() for v in values))
    src += ['.align 4'] + words_of('new_chars', b''.join(chars.new), 'long')
    (org, code), = sh2asm.assemble(src)
    end = OPT_AT + len(opt)
    assert end <= KEYS_AT, f'options_keys: OPT.DAT already runs to {end:08X}, past KEYS_AT'
    out = bytes(opt) + bytes(KEYS_AT - end) + code
    return out, label_w, value_w, len(chars.new), len(code)


def main():
    cce, dst = sys.argv[1], sys.argv[2]
    path = os.path.join(dst, 'DAYTONA', 'OPT.DAT')
    opt = open(path, 'rb').read()
    orig = open(os.path.join(cce, 'DAYTONA', 'OPT.DAT'), 'rb').read()
    assert len(opt) > len(orig), 'options_keys: run after options_sound.py'
    out, label_w, value_w, new, size = build(opt)
    open(path, 'wb').write(out)
    print(f'options: KEY CONFIG\'s STEERING row (label {label_w} cells, values {value_w}); {new} new chars at '
          f'VRAM {32 * NEW_CELL:#x}; {size} bytes at {KEYS_AT:08X}; OPT.DAT {len(out)} bytes')


if __name__ == '__main__':
    main()
