"""Options > KEY CONFIG, what CCE95 adds, appended to DAYTONA/OPT.DAT after
tools/options_sound.py's block: STEERING : AUTO / WHEEL / STICK under each
player's types (patches/steering_choice.s), and EDIT in TYPE E's place, a
layout of the player's own (patches/edit_keys.s).

usage: options_keys.py <cce extracted dir> <out dir>
  Rewrites <out dir>/DAYTONA/OPT.DAT (options_sound.py's), with this page's
  code and pictures at KEYS_AT. Reads the key tables from <out dir>'s
  RACE.BIN.

The page (SLCT.BIN 06031AE8) has no cursor: each player's own pad steps
their TYPE with up and down (002FD72B + 3 x player + device, the device as
the page counts it: 0 pad, 1 Arcade Racer or Mission Stick, 2 3D pad), and
A, B, C or Start on the first pad leaves.

STEERING: left and right step it (002FE7C0 + player, patches/save_ext.s), on
the pad, the 3D pad or the Arcade Racer, whose wheel sets left and right
when turned. Its value blinks between arrows, as DUSA's TYPE on its own Key
Configuration (8 frames on, 8 off).

EDIT: the fifth type, TYPE E's layout until a button is given another job.
Start on the player's own pad, with EDIT their type, begins editing (EDIT
turns yellow): press a button to pick it (its label turns orange), left and
right step its job, Start ends. On the Arcade Racer turning the wheel gives
left and right, and the paddles are buttons like the rest. The jobs are the
labels' own: NOT USED, ACCEL, BRAKE, SHIFT UP, SHIFT DOWN, GEAR 1-4, UP VIEW,
DOWN VIEW, VIEW 1-4. A layout is kept per player and device in the save
(002FE7C2 + 5 x (3 x player + device), docs/backup.md): a job code a button,
4 bits, 0 meaning TYPE E's job. While a player edits, the page sees none of
their buttons, so A, B and C don't leave; on EDIT, Start edits instead of
leaving.

Its text is two planes of boxes 3 cells high: PLAYER and the TYPE boxes on
one (map 25E60000, chars from VRAM 0xA000), the button labels on the other
(map 25E68000, chars from VRAM 0). Under TYPE E (y 27 for player 1, 48 for
player 2) each player has an empty row before the next block, empty in the
labels' column too for all three diagrams. STEERING is on the labels'
plane, in their face: the label at x 20 (PLAYER's column) and the value at x
33 (the labels'). Its words are put together from letters of the labels
(ACCEL, BRAKE, DOWN VIEW, NOT USED, SHIFT UP; label chars from OPT.DAT's
0x294E30, their pictures from 0x296D74, 3 x 10 cells each) and the G of the
main page's GAME MODE, the same face two rows higher. EDIT is a TYPE box,
from TYPE A's E, TYPE D's D and T, and SHIFT's I. The labels' new chars go
to VRAM 0x6000 (cell 0x300 on) and EDIT's after the TYPE boxes' own (VRAM
0xBEA0, cell 0xF5 on); nothing else uses either while the page is up, and
the draw copies them in each time.

For EDIT the page's own label drawing (060325D4, one hand-written list per
device and type) gives way to ours: the button positions below, checked
against its TYPE E lists.

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
EDIT_AT = KEYS_AT + 0x10            # and points the TYPE E boxes here
CODE_AT = KEYS_AT + 0x40
LABEL_CHARS, LABEL_N = 0x294E30, 250
TYPE_CHARS, TYPE_N = 0x2970F8, 245
LABELS = {'ACCEL': 0, 'BRAKE': 1, 'DOWN VIEW': 2, 'NOT USED': 3, 'SHIFT UP': 5}
LABEL_PICS = 0x296D74               # 3 x 10 cells a label
TYPE_PICS = 0x299014                # TYPE A-E, 3 x 8 cells each
MAIN_CHARS, GAME_MODE = 0x264B04, (0x26C354, 18)
NEW_CELL, NEW_END = 0x300, 0x500    # the labels': VRAM 0x6000 up to the TYPE chars at 0xA000
TNEW_CELL, TNEW_END = TYPE_N, 0x200     # the TYPE boxes': VRAM 0xBEA0 on
# letter: (word, first column, end), each from the dark column before it
LETTERS = {'S': ('SHIFT UP', 2, 11), 'H': ('SHIFT UP', 11, 21), 'I': ('SHIFT UP', 22, 30),
           'T': ('NOT USED', 21, 31), 'N': ('NOT USED', 1, 11), 'O': ('NOT USED', 11, 21),
           'U': ('NOT USED', 36, 47), 'E': ('BRAKE', 41, 51), 'R': ('BRAKE', 11, 21),
           'K': ('BRAKE', 31, 41), 'A': ('ACCEL', 2, 12), 'C': ('ACCEL', 12, 22),
           'L': ('ACCEL', 42, 52), 'W': ('DOWN VIEW', 68, 78), 'G': ('GAME MODE', 1, 12)}
G_DROP = 2                          # the main page's letters sit two rows higher
LEFT_END, RIGHT_END = ('ACCEL', 0, 2), ('ACCEL', 52, 56)    # the box's ends, the last letter's dark column
# EDIT in the TYPE boxes' face: (picture, first column, end)
EDIT_PARTS = [('TYPE A', 0, 2), ('TYPE A', 31, 41), ('TYPE D', 46, 56), ('SHIFT UP', 22, 30),
              ('TYPE A', 2, 12), ('TYPE D', 56, 60)]
VALUES = ['AUTO', 'WHEEL', 'STICK']
LABEL_X, VALUE_X, VALUE_END = 20, 33, 44    # the value stays clear of the diagrams from x 44
BLINK = 8                           # frames on, frames off

# The buttons a layout covers, in its order, with their bits in the page's and the race's words
SLOTS = ['A', 'B', 'C', 'X', 'Y', 'Z', 'L', 'R', 'UP', 'DOWN']
MASKS = [0x0400, 0x0100, 0x0200, 0x0040, 0x0020, 0x0010, 0x0008, 0x0080, 0x1000, 0x2000]
# Where each device's diagram labels its buttons: (x, rows below the block's first); None: no such button.
# The Arcade Racer's paddles are its up (left) and down (right).
PAD_POS = [(75, 16), (75, 13), (75, 10), (75, 0), (75, 3), (75, 6), (33, 3), (33, 0), (33, 9), (33, 12)]
WHEEL_POS = [(75, 0), (75, 3), (75, 6), (33, 0), (33, 3), (33, 6), None, None, (33, 12), (75, 12)]
POSITIONS = [PAD_POS, WHEEL_POS, PAD_POS]
# Job codes (0 in a layout: TYPE E's), the label picture each shows (LABEL_PICS + 60 x n)
JOBS = ['', 'NOT USED', 'ACCEL', 'BRAKE', 'SHIFT UP', 'SHIFT DOWN', 'GEAR 1', 'GEAR 2', 'GEAR 3', 'GEAR 4',
        'UP VIEW', 'DOWN VIEW', 'VIEW 1', 'VIEW 2', 'VIEW 3', 'VIEW 4']
JOB_PIC = [3, 3, 0, 1, 5, 4, 7, 8, 9, 10, 6, 2, 11, 12, 13, 14]
# The race's tables (RACE.BIN): driving masks 0604F870 + type x 100 + preset x 20 (shift up,
# shift down, gas, brake, gears 1-4, steering); camera keys by device, preset x 8 (views 1-4,
# or 0, 0, up view, down view). The race's type for the page's devices: pad 0, wheel 1, 3D pad 2.
DRIVE_KEYS, CAMERA_KEYS = 0x0604F870, [0x0604F028, 0x0604F050, 0x0604F078]
DRIVE_JOBS = ['SHIFT UP', 'SHIFT DOWN', 'ACCEL', 'BRAKE', 'GEAR 1', 'GEAR 2', 'GEAR 3', 'GEAR 4']


def render(opt, chars, at, w):
    cells = np.array(struct.unpack_from(f'>{3 * w}H', opt, at - OPT_AT)).reshape(3, w)
    img = np.zeros((24, 8 * w), np.uint8)
    for r in range(3):
        for c in range(w):
            t = np.frombuffer(opt, np.uint8, 32, chars - OPT_AT + 32 * int(cells[r, c]))
            img[8 * r:8 * r + 8, 8 * c:8 * c + 8] = np.stack([t >> 4, t & 15], 1).reshape(8, 8)
    return img


def cut(words, w, a, b, drop=0):
    img = words[w][:, a:b]
    return np.concatenate([np.zeros((drop, img.shape[1]), np.uint8), img[:24 - drop]]) if drop else img


def word(words, text):
    parts = [cut(words, *LEFT_END)] + [cut(words, *LETTERS[ch], drop=G_DROP if ch == 'G' else 0) for ch in text]
    return np.concatenate(parts + [cut(words, *RIGHT_END)], 1)


def arrow(right):
    """A triangle in the labels' light green with their dark edge, 13 rows tall, centred on the letters."""
    img = np.zeros((24, 11), np.uint8)
    for r in range(13):
        d = abs(r - 6)
        row = img[5 + r]
        row[2 + d:9] = 1
        row[1 + d] = 15
        row[9] = 15
    img[4, 8:10] = img[18, 8:10] = 15
    return img[:, ::-1] if right else img


def pad8(img):
    return np.pad(img, ((0, 0), (0, -img.shape[1] % 8)))


class Chars:
    """A plane's chars: a char's 32 bytes -> its cell, new ones from `first`."""

    def __init__(self, opt, at, n, first, end):
        self.cell = {}
        for c in range(n):
            self.cell.setdefault(bytes(opt[at - OPT_AT + 32 * c:at - OPT_AT + 32 * c + 32]), c)
        self.first, self.end, self.new = first, end, []

    def cells(self, img, w):
        out = np.zeros((3, w), np.uint16)
        for r in range(3):
            for c in range(img.shape[1] // 8):
                px = img[8 * r:8 * r + 8, 8 * c:8 * c + 8]
                t = bytes((px[:, 0::2] << 4 | px[:, 1::2]).astype(np.uint8).ravel())
                if t not in self.cell:
                    self.cell[t] = self.first + len(self.new)
                    self.new.append(t)
                out[r, c] = self.cell[t]
        assert self.first + len(self.new) <= self.end, 'options_keys: no room for the new chars'
        return out


def type_e_jobs(race):
    """TYPE E's job for each device's buttons, as job codes, from the race's tables."""
    base = 0x06028000
    out = []
    for dev in range(3):
        drive = struct.unpack_from('>8H', race, DRIVE_KEYS + dev * 100 + 4 * 20 - base)
        cam = struct.unpack_from('>4H', race, CAMERA_KEYS[dev] + 4 * 8 - base)
        jobs = []
        for mask in MASKS:
            job = 'NOT USED'
            for name, m in zip(DRIVE_JOBS, drive):
                if m & mask:
                    job = name
            if cam[0]:
                for k in range(4):
                    if cam[k] & mask:
                        job = f'VIEW {k + 1}'
            else:
                if cam[2] & mask:
                    job = 'UP VIEW'
                if cam[3] & mask:
                    job = 'DOWN VIEW'
            jobs.append(JOBS.index(job))
        out.append(jobs)
    return out


CODE = '''
.org {keys_at:08X}
    bra    kc_tail
    nop
    bra    kc_sides
    nop
.org {code_at:08X}

; patches/steering_menu.s: 06032378, which draws a player's TYPE boxes, ends
; here instead of its epilogue (r4 = the player, its stack as at 06032412):
; the epilogue, the player's STEERING row and EDIT box, then the labels.
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
    mov.l  state_at_a,r0
    mov.b  @r0,r0
    tst    r0,r0
    bf     tail_draw
    mov.l  editing_at_a,r1    ; the page's first draw: nobody edits yet
    mov    #0,r0
    mov.b  r0,@r1
    mov.b  r0,@(1,r1)
tail_draw:
    bsr    draw_steering
    mov.l  @r15,r4
    bsr    edit_box
    mov.l  @r15,r4
    mov.l  @r15+,r4
    lds.l  @r15+,pr
    bra    kc_labels
    nop

; patches/steering_menu.s: the page's input calls here before its loop over
; the players (06031C2C; its stack holds the buttons each port pressed this
; frame, longs at +8 and +12). Then what the replaced steps set: r12 =
; 002FD72B, r14 = r8, r0 = r9.
kc_sides:
    sts.l  pr,@-r15
    mov.l  r13,@-r15
    mov.l  r12,@-r15
    mov.l  r11,@-r15
    mov.l  r10,@-r15
    mov.l  blink_at_a,r1      ; STEERING's arrows blink
    mov.b  @(1,r1),r0
    add    #1,r0
    mov.b  r0,@(1,r1)
    cmp/eq #{blink},r0
    bf     sides_input
    mov    #0,r0
    mov.b  r0,@(1,r1)
    mov.b  @r1,r0
    xor    #1,r0
    mov.b  r0,@r1
    bsr    draw_value
    mov    #0,r4
    bsr    draw_value
    mov    #1,r4
sides_input:
    mov    r15,r13
    add    #28,r13          ; the buttons, port 1's
    mov    #0,r14
sides_next:
    mov.l  @r13,r11
    mov.l  editing_at_a,r0
    add    r14,r0
    mov.b  @r0,r0
    tst    r0,r0
    bf     in_edit
    mov.l  kl_start_a,r2
    tst    r2,r11
    bt     not_start
    bsr    kc_type
    mov    r14,r4
    mov    #4,r2
    cmp/eq r2,r1
    bf     not_start
    mov.l  editing_at_a,r1    ; Start on EDIT: editing, no button picked yet
    add    r14,r1
    mov    #1,r0
    mov.b  r0,@r1
    mov.l  sel_at_a,r1
    add    r14,r1
    mov    #-1,r0
    mov.b  r0,@r1
    bsr    sound
    nop
    bsr    edit_box
    mov    r14,r4
    bra    consumed
    nop
in_edit:
    bsr    edit_input
    nop
consumed:
    mov    #0,r0            ; the page sees none of this player's buttons
    mov.l  r0,@r13
    tst    r14,r14
    bf     sides_done
    mov.l  ports_at_a,r1    ; nor port 1's in its own check (A, B, C or Start leaves)
    mov.w  r0,@(2,r1)
    mov.w  r0,@(4,r1)
    bra    sides_done
    nop
not_start:
    mov.l  kl_left_a,r2        ; left and right step STEERING
    tst    r2,r11
    bf     step_left
    mov.l  kl_right_a,r2
    tst    r2,r11
    bt     sides_done
    bra    step
    mov    #1,r3
step_left:
    mov    #2,r3
step:
    mov.l  choice_at_a,r1
    add    r14,r1
    mov.b  @r1,r0
    mov    #2,r2
    cmp/hi r2,r0
    bf     in_range
    mov    #0,r0
in_range:
    add    r3,r0
    mov    #3,r2
    cmp/hs r2,r0
    bf     stepped
    add    #-3,r0
stepped:
    mov.b  r0,@r1
    bsr    sound
    nop
    bsr    draw_value
    mov    r14,r4
sides_done:
    add    #4,r13
    add    #1,r14
    mov    r14,r0
    cmp/eq #2,r0
    bf     sides_next
    mov.l  @r15+,r10
    mov.l  @r15+,r11
    mov.l  @r15+,r12
    mov.l  @r15+,r13
    lds.l  @r15+,pr
    mov.l  types_at_a,r12
    mov    r8,r14
    rts
    mov    r9,r0

.align 4
state_at_a:
    .long  0x06042554
editing_at_a:
    .long  editing
blink_at_a:
    .long  blink
kl_start_a:
    .long  0x0800
sel_at_a:
    .long  selected
ports_at_a:
    .long  0x060072C4
kl_left_a:
    .long  0x4000
kl_right_a:
    .long  0x8000
choice_at_a:
    .long  0x002FE7C0
types_at_a:
    .long  0x002FD72B

; r14 = the player, r11 the buttons pressed, while editing: Start ends it, a
; button of the controller is picked, left and right step its job.
edit_input:
    sts.l  pr,@-r15
    bsr    kc_type
    mov    r14,r4
    mov    r0,r10           ; the device
    mov.l  kl_start,r2
    tst    r2,r11
    bt     ei_slot
    mov.l  editing_at,r1
    add    r14,r1
    mov    #0,r0
    mov.b  r0,@r1
    bsr    sound
    nop
    mov.l  kl_lit,r1
    bsr    edit_draw        ; EDIT lit, the chosen type
    mov    r14,r4
    bra    ei_labels
    nop
ei_slot:
    mov    #0,r12
ei_find:
    mov.l  masks_at,r0
    mov    r12,r1
    shll   r1
    mov.w  @(r0,r1),r2
    tst    r2,r11
    bt     ei_find_next
    bsr    pos_of
    nop
    mov.b  @r0,r0
    tst    r0,r0
    bf     ei_found
ei_find_next:
    add    #1,r12
    mov    #10,r0
    cmp/eq r0,r12
    bf     ei_find
    bra    ei_sides
    nop
ei_found:
    mov.l  sel_at,r1
    add    r14,r1
    mov.b  r12,@r1
    bsr    sound
    nop
    bra    ei_labels
    nop
ei_sides:
    mov.l  sel_at,r1
    add    r14,r1
    mov.b  @r1,r12
    mov    #10,r0
    cmp/hs r0,r12
    bt     ei_done          ; none picked
    mov.l  kl_left,r2
    tst    r2,r11
    bf     ei_left
    mov.l  kl_right,r2
    tst    r2,r11
    bt     ei_done
    bra    ei_step
    mov    #1,r6
ei_left:
    mov    #-1,r6
ei_step:
    mov.l  r6,@-r15
    mov    r14,r4
    mov    r10,r5
    bsr    job_of
    mov    r12,r1
    mov.l  @r15+,r6
    add    r0,r6            ; the next job, 1 to 15 round
    tst    r6,r6
    bf     ei_not0
    mov    #15,r6
ei_not0:
    mov    #16,r0
    cmp/eq r0,r6
    bf     ei_store
    mov    #1,r6
ei_store:
    mov    r14,r4
    mov    r10,r5
    bsr    set_job
    mov    r12,r1
    bsr    sound
    nop
ei_labels:
    bsr    kc_labels
    mov    r14,r4
ei_done:
    lds.l  @r15+,pr
    rts
    nop

; r10 = the device, r12 the slot -> r0 = its place in the positions (x, row)
pos_of:
    mov    r10,r0
    mov    #20,r1
    mulu.w r1,r0
    sts    macl,r0
    mov    r12,r1
    shll   r1
    add    r1,r0
    mov.l  pos_at,r1
    rts
    add    r1,r0

; r4 = the player -> r0 its device (0 pad, 1 wheel or Mission Stick, 2 3D
; pad, as the page counts), r1 its type (4: EDIT). r4 kept.
kc_type:
    sts.l  pr,@-r15
    mov.l  r4,@-r15
    mov.l  smpc_at,r0
    mov.b  @(r0,r4),r4
    mov.l  device_at,r1
    jsr    @r1
    nop
    mov    #2,r1
    cmp/hi r1,r0
    bf     kt_known
    mov    #0,r0
kt_known:
    mov.l  @r15+,r4
    mov    r4,r1
    shll   r1
    add    r4,r1
    add    r0,r1
    mov.l  types_at,r2
    add    r2,r1
    mov.b  @r1,r1
    lds.l  @r15+,pr
    rts
    nop

; r4 = the player, r5 its device, r1 the slot -> r0 its job (1-15). r4-r14 kept.
job_of:
    sts.l  pr,@-r15
    bsr    byte_of
    nop
    mov.b  @r0,r0
    mov    r1,r2
    shlr   r2               ; odd slots: the low nibble
    bt     jo_low
    shlr2  r0
    shlr2  r0
jo_low:
    and    #15,r0
    tst    r0,r0
    bf     jo_done
    mov    r5,r0            ; TYPE E's
    mov    #10,r2
    mulu.w r2,r0
    sts    macl,r0
    add    r1,r0
    mov.l  defaults_at,r2
    mov.b  @(r0,r2),r0
jo_done:
    lds.l  @r15+,pr
    rts
    nop

; r4 = the player, r5 its device, r1 the slot, r6 the job: kept in the layout.
set_job:
    sts.l  pr,@-r15
    bsr    byte_of
    nop
    mov.b  @r0,r2
    mov    r1,r3
    shlr   r3
    bt     sj_low
    mov    #15,r3
    and    r3,r2
    mov    r6,r3
    shll2  r3
    shll2  r3
    bra    sj_store
    or     r3,r2
sj_low:
    mov    #-16,r3
    and    r3,r2
    or     r6,r2
sj_store:
    mov.b  r2,@r0
    lds.l  @r15+,pr
    rts
    nop

; r4 = the player, r5 its device, r1 the slot -> r0 = the layout's byte for it
byte_of:
    mov    r4,r0
    shll   r0
    add    r4,r0
    add    r5,r0
    mov    r0,r2
    shll2  r0
    add    r2,r0
    mov.l  layouts_at,r2
    add    r2,r0
    mov    r1,r2
    shlr   r2
    rts
    add    r2,r0

; r4 = the player: the labels, ours for EDIT (the button being edited in
; orange), the page's (060325D4) for the other types.
kc_labels:
    sts.l  pr,@-r15
    bsr    kc_type
    nop
    mov    #4,r3
    cmp/eq r3,r1
    bt     own_labels
    lds.l  @r15+,pr
    mov.l  labels_at,r1
    jmp    @r1
    nop
own_labels:
    mov.l  r14,@-r15
    mov.l  r13,@-r15
    mov.l  r12,@-r15
    mov.l  r11,@-r15
    mov.l  r10,@-r15
    mov    r4,r14
    mov    r0,r10           ; the device
    mov    #12,r13          ; the block's first row
    tst    r14,r14
    bt     ol_clear
    mov    #33,r13
ol_clear:
    mov    #33,r4           ; the labels' two columns cleared, as the page does
    mov    r13,r5
    mov    #43,r6
    mov    r13,r7
    bsr    clear
    add    #15,r7
    mov    #75,r4
    mov    r13,r5
    mov    #85,r6
    mov    r13,r7
    bsr    clear
    add    #19,r7
    mov    #0,r12
ol_next:
    bsr    pos_of
    nop
    mov.b  @r0,r11          ; x
    tst    r11,r11
    bt     ol_skip          ; no such button on this controller
    mov.b  @(1,r0),r0
    add    r13,r0
    mov.l  r0,@-r15         ; the row
    mov    r14,r4
    mov    r10,r5
    bsr    job_of
    mov    r12,r1
    mov.l  pic_at,r1
    mov.b  @(r0,r1),r0
    mov    #60,r1
    mulu.w r1,r0
    sts    macl,r4
    mov.l  pics_at,r1
    add    r1,r4
    mov.l  kl_lit,r1
    mov.l  editing_at,r0
    add    r14,r0
    mov.b  @r0,r0
    tst    r0,r0
    bt     ol_colour
    mov.l  sel_at,r0
    add    r14,r0
    mov.b  @r0,r0
    cmp/eq r12,r0
    bf     ol_colour
    mov.l  kl_edit,r1
ol_colour:
    mov    r11,r6
    mov.l  @r15+,r7
    mov.l  lmap_at,r5
    mov.l  lchars_at,r2
    bsr    draw
    mov    #10,r0
ol_skip:
    add    #1,r12
    mov    #10,r0
    cmp/eq r0,r12
    bf     ol_next
    mov.l  @r15+,r10
    mov.l  @r15+,r11
    mov.l  @r15+,r12
    mov.l  @r15+,r13
    mov.l  @r15+,r14
    lds.l  @r15+,pr
    rts
    nop

; r4 x1, r5 y1, r6 x2, r7 y2: the labels' plane cleared there (06028B80)
clear:
    sts.l  pr,@-r15
    mov.l  kl_lit,r1
    mov.l  r1,@-r15
    mov.l  lmap_at,r1
    mov.l  r1,@-r15
    mov.l  clear_at,r1
    jsr    @r1
    nop
    add    #8,r15
    lds.l  @r15+,pr
    rts
    nop

; r4 = the player: EDIT in yellow while they edit; editing ends if EDIT is
; no longer their type (another controller).
edit_box:
    sts.l  pr,@-r15
    bsr    kc_type
    nop
    mov.l  editing_at,r2
    add    r4,r2
    mov.b  @r2,r0
    tst    r0,r0
    bt     eb_done
    mov    #4,r3
    cmp/eq r3,r1
    bt     eb_draw
    mov    #0,r0
    bra    eb_done
    mov.b  r0,@r2
eb_draw:
    mov.l  kl_hi,r1
    bsr    edit_draw
    nop
eb_done:
    lds.l  @r15+,pr
    rts
    nop

; r4 = the player, r1 the colour: their EDIT box (r4 not kept)
edit_draw:
    sts.l  pr,@-r15
    mov    #21,r0
    mulu.w r0,r4
    sts    macl,r7
    add    #27,r7
    mov    #23,r6
    mov.l  edit_cells_at,r4
    mov.l  tmap_at,r5
    mov.l  tchars_at,r2
    bsr    draw
    mov    #8,r0
    lds.l  @r15+,pr
    rts
    nop

; r4 = the player: the new chars into VRAM, then STEERING and its value.
draw_steering:
    sts.l  pr,@-r15
    mov.l  r14,@-r15
    mov    r4,r14
    mov.l  lnew_from,r1
    mov.l  lnew_to,r2
    mov.w  lnew_longs,r3
    bsr    copy
    nop
    mov.l  tnew_from,r1
    mov.l  tnew_to,r2
    mov.w  tnew_longs,r3
    bsr    copy
    nop
    mov    #21,r0
    mulu.w r0,r14
    sts    macl,r7
    add    #30,r7
    mov.l  label_cells_at,r4
    mov    #{label_x},r6
    mov.l  kl_lit,r1
    mov.l  lmap_at,r5
    mov.l  lchars_at,r2
    bsr    draw
    mov    #{label_w},r0
    bsr    draw_value
    mov    r14,r4
    mov.l  @r15+,r14
    lds.l  @r15+,pr
    rts
    nop

; r4 = the player: STEERING's value, with its arrows or without as the blink has it
draw_value:
    sts.l  pr,@-r15
    mov.l  choice_at,r1
    add    r4,r1
    mov    #21,r0
    mulu.w r0,r4
    sts    macl,r7
    add    #30,r7
    mov.b  @r1,r0
    mov    #2,r1
    cmp/hi r1,r0
    bf     dv_ok
    mov    #0,r0
dv_ok:
    shll   r0
    mov.l  blink_at,r1
    mov.b  @r1,r1
    add    r1,r0
    mov.w  value_bytes,r1
    mulu.w r1,r0
    sts    macl,r4
    mov.l  values_at,r1
    add    r1,r4
    mov    #{value_x},r6
    mov.l  kl_lit,r1
    mov.l  lmap_at,r5
    mov.l  lchars_at,r2
    bsr    draw
    mov    #{value_w},r0
    lds.l  @r15+,pr
    rts
    nop

; r1 from, r2 to, r3 longs
copy:
    mov.l  @r1+,r0
    dt     r3
    mov.l  r0,@r2
    bf/s   copy
    add    #4,r2
    rts
    nop

; the page's sound for a step (0600795A)
sound:
    mov.l  sound_at,r1
    mov    #1,r6
    mov    r6,r5
    jmp    @r1
    mov    #0,r4

; r4 cells, r5 map, r6 x, r7 y, r0 width, r1 colour, r2 char base: a box
; through the page's text routine (0602991C). r8-r14 kept.
draw:
    sts.l  pr,@-r15
    mov.l  r1,@-r15
    mov.l  r2,@-r15
    mov    #3,r1
    mov.l  r1,@-r15
    mov.l  r0,@-r15
    mov.l  text_at,r1
    jsr    @r1
    nop
    add    #16,r15
    lds.l  @r15+,pr
    rts
    nop
lnew_longs:
    .word  {lnew_longs}
tnew_longs:
    .word  {tnew_longs}
value_bytes:
    .word  {value_bytes}
.align 4
kl_lit:
    .long  0x0090
kl_edit:
    .long  0x00A0           ; orange: the button being edited
kl_hi:
    .long  0x00B0           ; yellow: EDIT while editing
kl_start:
    .long  0x0800
kl_left:
    .long  0x4000
kl_right:
    .long  0x8000
state_at:
    .long  0x06042554
ports_at:
    .long  0x060072C4
smpc_at:
    .long  0x060131C4
device_at:
    .long  0x06032F74
labels_at:
    .long  0x060325D4
types_at:
    .long  0x002FD72B
choice_at:
    .long  0x002FE7C0
layouts_at:
    .long  0x002FE7C2
sound_at:
    .long  0x0600795A
text_at:
    .long  0x0602991C
clear_at:
    .long  0x06028B80
lchars_at:
    .long  0x25E00000
lmap_at:
    .long  0x25E68000
tchars_at:
    .long  0x25E0A000
tmap_at:
    .long  0x25E60000
lnew_to:
    .long  {lnew_to:#010x}
tnew_to:
    .long  {tnew_to:#010x}
lnew_from:
    .long  lnew_chars
tnew_from:
    .long  tnew_chars
label_cells_at:
    .long  label_cells
values_at:
    .long  value_cells
edit_cells_at:
    .long  {edit_at:#010x}
pics_at:
    .long  {label_pics:#010x}
masks_at:
    .long  masks
pos_at:
    .long  positions
defaults_at:
    .long  defaults
pic_at:
    .long  job_pics
editing_at:
    .long  editing
sel_at:
    .long  selected
blink_at:
    .long  blink
'''


def words_of(name, data, size='word'):
    n = {'byte': 1, 'word': 2, 'long': 4}[size]
    fmt = {'byte': '>B', 'word': '>H', 'long': '>I'}[size]
    if size == 'byte':
        return [f'{name}:', '    .byte  ' + ', '.join(str(b) for b in data)]
    return [f'{name}:'] + [f'    .{size}  0x{struct.unpack_from(fmt, data, i)[0]:0{2 * n}X}'
                           for i in range(0, len(data), n)]


def build(opt, race):
    words = {name: render(opt, LABEL_CHARS, LABEL_PICS + 60 * i, 10) for name, i in LABELS.items()}
    words['GAME MODE'] = render(opt, MAIN_CHARS, *GAME_MODE)
    words['TYPE A'] = render(opt, TYPE_CHARS, TYPE_PICS, 8)
    words['TYPE D'] = render(opt, TYPE_CHARS, TYPE_PICS + 3 * 0x30, 8)
    lchars = Chars(opt, LABEL_CHARS, LABEL_N, NEW_CELL, NEW_END)
    tchars = Chars(opt, TYPE_CHARS, TYPE_N, TNEW_CELL, TNEW_END)

    label_img = pad8(word(words, 'STEERING'))
    label_w = label_img.shape[1] // 8
    assert LABEL_X + label_w <= VALUE_X, f'STEERING runs into the labels\' column ({label_w} cells)'
    label = lchars.cells(label_img, label_w)
    shown = [np.concatenate([arrow(False), word(words, v), arrow(True)], 1) for v in VALUES]
    value_w = max(pad8(img).shape[1] // 8 for img in shown)
    assert VALUE_X + value_w <= VALUE_END, f'the values run into the diagrams ({value_w} cells)'
    values = []
    for img in shown:
        on = pad8(img)
        off = on.copy()
        off[:, :11] = 0
        off[:, img.shape[1] - 11:img.shape[1]] = 0
        values += [lchars.cells(off, value_w), lchars.cells(on, value_w)]   # the narrower end in blank cells
    edit_img = np.concatenate([cut(words, *part) for part in EDIT_PARTS], 1)
    assert edit_img.shape[1] <= 64
    edit = tchars.cells(np.pad(edit_img, ((0, 0), (0, 64 - edit_img.shape[1]))), 8)

    defaults = type_e_jobs(race)
    positions = [b for dev in POSITIONS for p in dev for b in (p if p else (0, 0))]
    src = CODE.format(keys_at=KEYS_AT, code_at=CODE_AT, edit_at=EDIT_AT, blink=BLINK, label_x=LABEL_X,
                      label_w=label_w, value_x=VALUE_X, value_w=value_w, value_bytes=6 * value_w,
                      lnew_longs=8 * len(lchars.new), tnew_longs=8 * len(tchars.new),
                      lnew_to=0x25E00000 + 32 * NEW_CELL, tnew_to=0x25E0A000 + 32 * TNEW_CELL,
                      label_pics=LABEL_PICS).splitlines()
    src += ['.align 4'] + words_of('label_cells', label.astype('>u2').tobytes())
    src += words_of('value_cells', b''.join(v.astype('>u2').tobytes() for v in values))
    src += words_of('masks', struct.pack('>10H', *MASKS))
    src += words_of('positions', bytes(positions), 'byte')
    src += words_of('defaults', bytes(j for dev in defaults for j in dev), 'byte')
    src += words_of('job_pics', bytes(JOB_PIC), 'byte')
    src += ['editing:', '    .byte  0, 0', 'selected:', '    .byte  255, 255', 'blink:', '    .byte  0, 0']
    src += ['.align 4'] + words_of('lnew_chars', b''.join(lchars.new), 'long')
    src += words_of('tnew_chars', b''.join(tchars.new), 'long')
    src += [f'.org {EDIT_AT:08X}'] + words_of('edit_cells', edit.astype('>u2').tobytes())
    sections = sh2asm.assemble(src)
    end_at = OPT_AT + len(opt)
    assert end_at <= KEYS_AT, f'options_keys: OPT.DAT already runs to {end_at:08X}, past KEYS_AT'
    top = max(org + len(code) for org, code in sections)
    blob = bytearray(top - KEYS_AT)
    for org, code in sections:
        blob[org - KEYS_AT:org - KEYS_AT + len(code)] = code
    out = bytes(opt) + bytes(KEYS_AT - end_at) + bytes(blob)
    return out, label_w, value_w, len(lchars.new), len(tchars.new), len(blob), defaults


def main():
    cce, dst = sys.argv[1], sys.argv[2]
    path = os.path.join(dst, 'DAYTONA', 'OPT.DAT')
    opt = open(path, 'rb').read()
    orig = open(os.path.join(cce, 'DAYTONA', 'OPT.DAT'), 'rb').read()
    assert len(opt) > len(orig), 'options_keys: run after options_sound.py'
    race = open(os.path.join(dst, 'DAYTONA', 'RACE.BIN'), 'rb').read()
    out, label_w, value_w, lnew, tnew, size, defaults = build(opt, race)
    open(path, 'wb').write(out)
    e = ['/'.join(JOBS[j] for j in dev) for dev in defaults]
    print(f'options: KEY CONFIG\'s STEERING row (label {label_w} cells, values {value_w} with arrows) and EDIT; '
          f'{lnew} + {tnew} new chars; {size} bytes at {KEYS_AT:08X}; OPT.DAT {len(out)} bytes; '
          f'TYPE E (A B C X Y Z L R up down): pad {e[0]}; wheel {e[1]}; 3D pad {e[2]}')


if __name__ == '__main__':
    main()
