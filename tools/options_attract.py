"""Options > Sound > ATTRACT : ORIGINAL / CCE: the row's words and code,
appended to DAYTONA/OPT.DAT.

usage: options_attract.py <cce extracted dir> <out dir>
  Writes <out dir>/DAYTONA/OPT.DAT and lists it in PATCHED.txt.

The Options screens' text is drawn from OPT.DAT (loaded at 0x250000 while
Options is up): each label or value is a box of cells, 3 rows high, of
4-bit 8x8 chars, the letters dark on a light plate. The Sound page copies
its chars to VRAM 0xA000 (OPT.DAT +0x1C8FA, 0x150E0 bytes) and the main
page its own (+0x14B04, 0x7660 bytes); a cell is a char number from
there. Neither page has the words, so they are put together from letters
of the labels both pages show (the same face): ATTRACT, ORIGINAL and CCE
cut from ARCADE, TIME ATTACK, EXIT, SOUND, GAME MODE and HANDLING, with
ARCADE's plate ends; the label's colon is SOUND MODE's own cells. Their
chars go to VRAM after the Sound page's (0x1F0E0, 0x500 + 0xA87 on as a
char), free up to 0x20000 there.

The code (below) runs from the same block: OPT.DAT ends at 0x2AD468 and
nothing reads or writes work RAM past it while Options is up; the screens
after it load their own. patches/attract_menu.s points SLCT.BIN's Sound
page at it: the draw (060312D0) draws the row after its own, and the input
(0603182E) moves the cursor through it (rows 10-19 were SOUND MODE to
EXIT; ATTRACT is row 20, drawn between S.E. TEST and EXIT, which moves a
row down) and flips 002FC3AB (0 ORIGINAL, 1 CCE, patches/attract_load.s)
with left and right.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import sh2asm  # noqa: E402

OPT_AT = 0x250000
SOUND_CHARS, MAIN_CHARS = 0x1C8FA, 0x14B04
FIRST_FREE = 0xA87                  # chars past the Sound page's, from VRAM 0xA000
LAST_CHAR = 0xAFF                   # VRAM 0x20000
# label: (chars, OPT.DAT address of its cells, width in cells)
WORDS = {'ARCADE': (MAIN_CHARS, 0x26C1C8, 9), 'TIME ATTACK': (MAIN_CHARS, 0x26C75C, 15),
         'GAME MODE': (MAIN_CHARS, 0x26C354, 18), 'HANDLING': (MAIN_CHARS, 0x26C46E, 12),
         'SOUND': (MAIN_CHARS, 0x26C72C, 8), 'EXIT': (SOUND_CHARS, 0x282D60, 6),
         'SOUND MODE': (SOUND_CHARS, 0x282D84, 16)}
# letter: (word, first pixel column, end), cut where the letters meet
LETTERS = {'A': ('ARCADE', 2, 13), 'R': ('ARCADE', 13, 23), 'C': ('ARCADE', 23, 34), 'E': ('ARCADE', 55, 65),
           'T': ('TIME ATTACK', 2, 13), 'I': ('EXIT', 24, 33), 'O': ('SOUND', 12, 24),
           'G': ('GAME MODE', 2, 13), 'N': ('HANDLING', 23, 34), 'L': ('HANDLING', 44, 55)}
PLATE_LEFT, PLATE_RIGHT = ('ARCADE', 0, 2), ('ARCADE', 65, 70)
COLON_CELLS = (14, 16)              # SOUND MODE's colon, the label's last two columns


def cells_of(opt, name):
    _, at, w = WORDS[name]
    return np.array(struct.unpack_from(f'>{3 * w}H', opt, at - OPT_AT)).reshape(3, w)


def render(opt, name):
    chars = WORDS[name][0]
    cells = cells_of(opt, name)
    img = np.zeros((24, 8 * cells.shape[1]), np.uint8)
    for r in range(3):
        for c in range(cells.shape[1]):
            t = np.frombuffer(opt, np.uint8, 32, chars + 32 * int(cells[r, c]))
            img[8 * r:8 * r + 8, 8 * c:8 * c + 8] = np.stack([t >> 4, t & 15], 1).reshape(8, 8)
    return img


def word(opt, text):
    words = {n: render(opt, n) for n in WORDS}
    cut = lambda w, a, b: words[w][:, a:b]
    img = np.concatenate([cut(*PLATE_LEFT)] + [cut(*LETTERS[ch]) for ch in text] + [cut(*PLATE_RIGHT)], 1)
    return np.pad(img, ((0, 0), (0, -img.shape[1] % 8)))


def to_cells(img, chars, width=None):
    """Cells for an image, new chars added to `chars` (bytes -> char)."""
    w = width or img.shape[1] // 8
    out = np.zeros((3, w), np.uint16)
    for r in range(3):
        for c in range(img.shape[1] // 8):
            px = img[8 * r:8 * r + 8, 8 * c:8 * c + 8]
            if not px.any():
                continue
            t = bytes((px[:, 0::2] << 4 | px[:, 1::2]).astype(np.uint8).ravel())
            if t not in chars:
                chars[t] = FIRST_FREE + len(chars)
            out[r, c] = chars[t]
    return out


CODE = '''
.org {base:08X}
    bra    draw_row
    nop
    bra    row_input
    nop

; patches/attract_menu.s: 060312D0, the Sound page's draw (r4 the cursor's
; row), jumps here. It goes on with 060312D0 (its first steps, which the
; jump replaced) and has it come back to draw_after.
draw_row:
    sts.l  pr,@-r15
    mov.l  after_at,r0
    lds    r0,pr
    mov.l  r14,@-r15
    mov    #12,r5
    mov.w  k_80,r6
    mov.l  r13,@-r15
    mov.l  r12,@-r15
    mov.l  rest_at,r0
    jmp    @r0
    mov    #1,r12

; The page's own text is drawn: ATTRACT's chars into VRAM, then its three
; boxes as 060312D0 draws its own (0602991C): the label in its highlight
; while the cursor is on it, the choice lit as the page lights a row's value.
draw_after:
    mov.l  r14,@-r15
    mov.l  r13,@-r15
    mov.l  chars_at,r1
    mov.l  chars_to,r2
    mov.w  n_longs,r3
copy:
    mov.l  @r1+,r0
    dt     r3
    mov.l  r0,@r2
    bf/s   copy
    add    #4,r2
    mov.l  boxes_at,r14
    mov.l  row_at,r0
    mov.b  @r0,r0
    mov.w  k_90,r1          ; the label
    mov.w  k_90,r5          ; the chosen value
    cmp/eq #20,r0
    bf     label_colour
    mov.w  k_b0,r1
    mov.w  k_a0,r5
label_colour:
    mov    r14,r2
    add    #8,r2
    mov.w  r1,@r2
    mov    r5,r1
    mov.w  k_80,r3          ; the other
    mov.l  choice_at,r0
    mov.b  @r0,r0
    tst    r0,r0
    bt     colours
    mov    r1,r0
    mov    r3,r1
    mov    r0,r3
colours:
    add    #12,r2
    mov.w  r1,@r2           ; ORIGINAL
    add    #12,r2
    mov.w  r3,@r2           ; CCE
    mov    #3,r13
box:
    mov.w  @(8,r14),r0
    extu.w r0,r0
    mov.l  r0,@-r15         ; colour
    mov.l  char_base,r0
    mov.l  r0,@-r15
    mov    #3,r0
    mov.l  r0,@-r15
    mov.b  @(10,r14),r0
    extu.b r0,r0
    mov.l  r0,@-r15         ; width
    mov.w  @(4,r14),r0
    extu.w r0,r6
    add    #20,r6
    mov.w  @(6,r14),r0
    extu.w r0,r7
    add    #-4,r7
    mov.l  map_at,r5
    mov.l  text_at,r0
    jsr    @r0
    mov.l  @r14,r4
    add    #16,r15
    dt     r13
    bf/s   box
    add    #12,r14
    mov.l  @r15+,r13
    mov.l  @r15+,r14
    lds.l  @r15+,pr
    rts
    nop

; patches/attract_menu.s: the Sound page's input (0603182E, r5 the buttons
; pressed, r14 the cursor's row, r13 its value) jumps here. Up and down go
; through ATTRACT between S.E. TEST and EXIT; on ATTRACT left and right
; flip the choice; the rest goes on as before.
row_input:
    mov.l  values_at,r11
    mov.b  @r14,r1
    mov.w  k_up,r2
    tst    r5,r2
    bf     up
    mov.w  k_down,r2
    tst    r5,r2
    bf     down
    mov    r1,r0
    cmp/eq #20,r0
    bf     buttons
    mov.w  k_sides,r2
    tst    r5,r2
    bt     buttons          ; A, B and C on ATTRACT as on any row
    mov.l  choice_at,r2
    mov.b  @r2,r0
    xor    #1,r0
    mov.b  r0,@r2
    mov.l  redraw_at,r0
    jmp    @r0
    nop
up:
    mova   ups,r0
    bra    moved
    nop
down:
    mova   downs,r0
moved:
    add    #-10,r1
    mov.b  @(r0,r1),r1
    mov.b  r1,@r14
    mov.l  moved_at,r0
    jmp    @r0
    nop
buttons:
    mov.l  buttons_at,r0
    jmp    @r0
    nop
k_80:
    .word  0x0080
k_90:
    .word  0x0090
k_a0:
    .word  0x00A0
k_b0:
    .word  0x00B0
k_up:
    .word  0x1000
k_down:
    .word  0x2000
k_sides:
    .word  0xC000
n_longs:
    .word  {n_longs}
.align 4
ups:                        ; the row above, from row 10: SOUND MODE to EXIT, then ATTRACT
    .word  0x130A
    .word  0x0B0C
    .word  0x0D0E
    .word  0x0F10
    .word  0x1114
    .word  0x1200
downs:
    .word  0x0B0C
    .word  0x0D0E
    .word  0x0F10
    .word  0x1112
    .word  0x140A
    .word  0x1300
after_at:
    .long  draw_after
rest_at:
    .long  0x060312DC
chars_at:
    .long  chars
chars_to:
    .long  0x25E1F0E0
boxes_at:
    .long  boxes
row_at:
    .long  0x06053954
choice_at:
    .long  0x002FC3AB
char_base:
    .long  0x25E0A000
map_at:
    .long  0x25E60000
text_at:
    .long  0x0602991C
values_at:
    .long  0x060539A4
redraw_at:
    .long  0x060318E4
moved_at:
    .long  0x06031846
buttons_at:
    .long  0x060318F8
boxes:                      ; as the page's own: cells, x, y, colour, width
    .long  label_cells
    .word  0
    .word  0x34
    .word  0x0090
    .word  0x1000
    .long  original_cells
    .word  0x11
    .word  0x34
    .word  0x0080
    .word  {original_w:#06x}
    .long  cce_cells
    .word  {cce_x:#x}
    .word  0x34
    .word  0x0080
    .word  {cce_w:#06x}
'''


def words_of(name, data):
    lines = [f'{name}:']
    lines += [f'    .word  0x{v:04X}' for v in struct.unpack(f'>{len(data) // 2}H', data)]
    return lines


def build(opt):
    chars = {}
    label = np.zeros((3, 16), np.uint16)
    attract = to_cells(word(opt, 'ATTRACT'), chars)
    label[:, :attract.shape[1]] = attract
    a, b = COLON_CELLS
    label[:, a:b] = cells_of(opt, 'SOUND MODE')[:, a:b]
    original = to_cells(word(opt, 'ORIGINAL'), chars)
    cce = to_cells(word(opt, 'CCE'), chars)
    assert FIRST_FREE + len(chars) - 1 <= LAST_CHAR, f'{len(chars)} chars, room for {LAST_CHAR - FIRST_FREE + 1}'
    base = OPT_AT + len(opt) + (-len(opt) % 4)
    src = CODE.format(base=base, n_longs=8 * len(chars), original_w=original.shape[1] << 8,
                      cce_x=0x11 + original.shape[1] + 1, cce_w=cce.shape[1] << 8).splitlines()
    src += ['.align 4'] + words_of('label_cells', label.astype('>u2').tobytes())
    src += words_of('original_cells', original.astype('>u2').tobytes())
    src += words_of('cce_cells', cce.astype('>u2').tobytes())
    src += ['.align 4'] + words_of('chars', b''.join(sorted(chars, key=chars.get)))
    (org, code), = sh2asm.assemble(src)
    assert org == base
    return opt + bytes(base - OPT_AT - len(opt)) + code, len(chars)


def main():
    cce, dst = sys.argv[1], sys.argv[2]
    opt = open(os.path.join(cce, 'DAYTONA', 'OPT.DAT'), 'rb').read()
    out, n = build(opt)
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'OPT.DAT'), 'wb').write(out)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n_ for n_ in ['DAYTONA/OPT.DAT'] if n_ not in have]
    open(listing, 'w').write(''.join(n_ + '\n' for n_ in sorted(have)))
    print(f'options: ATTRACT : ORIGINAL / CCE, {n} chars; OPT.DAT {len(out)} bytes (the original {len(opt)})')


if __name__ == '__main__':
    main()
