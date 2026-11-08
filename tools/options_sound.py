"""Options > Sound, what CCE95 adds to the page, appended to DAYTONA/OPT.DAT:
the ATTRACT : ORIGINAL / CCE row, and the BGM list with DUSA's '95 songs
(docs/music.md).

usage: options_sound.py <cce extracted dir> <out dir>
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

The BGM list: the page draws a course's choice (rows 12-16) and the BGM
test's (row 17) as a box from its name table, and the BGM test plays the
entry's track from its track table (SLCT.BIN 0603F860, 0603FCF8: 30
entries, the 9 choices then the jingles and the rest). Both live here now,
at fixed places (patches/bgm_menu.s points the page at them): the 13
choices of patches/bgm_tables.s first, then CCE's other entries, so a
choice is its own entry in both. The '95 songs are shown by their bare
names, the remixes' pictures cut before " (remix)": the cells up to the cut
are the remix's own, and the column the cut runs through gets chars of its
own. The originals keep CCE's "(original)" pictures. Left and right on a
course row step through the choices grouped by version ('95, the
originals, CCE's), from a table of the next and the previous.
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

# The BGM list (patches/bgm_menu.s points SLCT.BIN at these places)
SLCT_AT = 0x06028000
NAMES, NAMES_N = 0x0603F860, 30     # CCE's name table: cells, width word, 0x0018
TRACKS = 0x0603FCF8                 # CCE's track table, a byte an entry
NAME_TABLE_AT, NAME_CAP = 0x2AD470, 48     # ours: right after the code's two entry branches
TRACK_TABLE_AT, TRACK_CAP = 0x2AD5F0, 48
CODE_AT = 0x2AD620
# the 13 BGM choices (patches/bgm_tables.s): CCE's name entry, or the remix to cut to a bare name
CHOICES = [('cce', 0), ('cce', 1), ('cce', 2), ('cce', 3), ('cce', 4), ('cce', 5),
           ('bare', 0), ('bare', 1), ('bare', 2),            # The King of Speed, Let's Go Away, Sky High '95
           ('cce', 6), ('cce', 7), ('cce', 8),               # CCE's originals
           ('bare', 4)]                                       # Pounding Pavement '95
CHOICE_TRACKS = [2, 3, 4, 5, 6, 7, 34, 35, 36, 23, 24, 25, 37]
# CCE's other entries (the jingles, then its own music), with what they play now (docs/music.md):
# The American Dream and Crash & Burrn play what the replay and the staff roll play, 37
REST = list(range(9, 30))
REST_TRACKS = [8, 9, 10, 11, 12, 26, 27, 28, 13, 14, 15, 16, 17, 29, 30, 31, 18, 37, 20, 21, 37]
ORDER = [6, 7, 8, 12, 9, 10, 11, 0, 1, 2, 3, 4, 5]     # left/right on a course row: '95, originals, CCE's
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

; the name and track tables come between (NAME_TABLE_AT, TRACK_TABLE_AT)
.org {code_at:08X}

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
; flip the choice; on a course's BGM row they step through the choices'
; order; the rest goes on as before.
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
    bf     course
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
; rows 12-16: the next or previous choice, then the page stores the value
; in the row's place and redraws as for its own left and right (060319D2)
course:
    add    #-12,r0
    mov    #5,r2
    cmp/hs r2,r0
    bt     buttons
    mov.w  k_left,r2
    tst    r5,r2
    bf     course_prev
    mov.w  k_right,r2
    tst    r5,r2
    bt     buttons
    mova   bgm_next,r0
    bra    course_step
    nop
course_prev:
    mova   bgm_prev,r0
course_step:
    mov.b  @r13,r2
    mov.b  @(r0,r2),r2
    mov.b  r2,@r13
    mov.l  stored_at,r0
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
k_left:
    .word  0x4000
k_right:
    .word  0x8000
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
bgm_next:                   ; by choice, the next in ORDER
    .byte  {bgm_next}
.align 4
bgm_prev:
    .byte  {bgm_prev}
.align 4
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
stored_at:
    .long  0x060319D2
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


def name_entry(slct, i):
    """CCE's name table entry i: (cells address, width)."""
    at, w = struct.unpack_from('>IH', slct, NAMES - SLCT_AT + 8 * i)
    return at, w


def bare_name(opt, slct, i, chars):
    """The remix's picture (name entry i) cut before " (remix)": the gap of
    empty columns before the last word. Cells up to the cut are the remix's;
    the column the cut runs through gets chars of its own (added to chars)."""
    at, w = name_entry(slct, i)
    cells = np.array(struct.unpack_from(f'>{3 * w}H', opt, at - OPT_AT)).reshape(3, w)
    img = np.zeros((24, 8 * w), np.uint8)
    for r in range(3):
        for c in range(w):
            t = np.frombuffer(opt, np.uint8, 32, SOUND_CHARS + 32 * int(cells[r, c]))
            img[8 * r:8 * r + 8, 8 * c:8 * c + 8] = np.stack([t >> 4, t & 15], 1).reshape(8, 8)
    used = img.any(0)
    x = len(used) - 1
    while not used[x]:
        x -= 1                          # the plate's empty end
    while used[x]:
        x -= 1                          # "(remix)"
    while not used[x - 1]:
        x -= 1                          # the gap before it: the cut is its first column
    n = (x + 7) // 8
    out = cells[:, :n].copy()
    if x % 8:
        column = img[:, 8 * (n - 1):8 * n].copy()
        column[:, x % 8:] = 0
        out[:, n - 1] = to_cells(column, chars)[:, 0]
    return out


def build(opt, slct):
    chars = {}
    label = np.zeros((3, 16), np.uint16)
    attract = to_cells(word(opt, 'ATTRACT'), chars)
    label[:, :attract.shape[1]] = attract
    a, b = COLON_CELLS
    label[:, a:b] = cells_of(opt, 'SOUND MODE')[:, a:b]
    original = to_cells(word(opt, 'ORIGINAL'), chars)
    cce = to_cells(word(opt, 'CCE'), chars)
    bare = {i: bare_name(opt, slct, i, chars) for kind, i in CHOICES if kind == 'bare'}
    assert FIRST_FREE + len(chars) - 1 <= LAST_CHAR, f'{len(chars)} chars, room for {LAST_CHAR - FIRST_FREE + 1}'
    base = OPT_AT + len(opt) + (-len(opt) % 4)
    assert base + 8 == NAME_TABLE_AT, hex(base)
    nxt = {v: ORDER[(k + 1) % len(ORDER)] for k, v in enumerate(ORDER)}
    prv = {v: ORDER[k - 1] for k, v in enumerate(ORDER)}
    src = CODE.format(base=base, code_at=CODE_AT, n_longs=8 * len(chars), original_w=original.shape[1] << 8,
                      cce_x=0x11 + original.shape[1] + 1, cce_w=cce.shape[1] << 8,
                      bgm_next=', '.join(str(nxt[v]) for v in range(len(ORDER))),
                      bgm_prev=', '.join(str(prv[v]) for v in range(len(ORDER)))).splitlines()
    src += ['.align 4'] + words_of('label_cells', label.astype('>u2').tobytes())
    src += words_of('original_cells', original.astype('>u2').tobytes())
    src += words_of('cce_cells', cce.astype('>u2').tobytes())
    for i, cells in bare.items():
        src += words_of(f'bare_{i}', cells.astype('>u2').tobytes())
    src += ['.align 4'] + words_of('chars', b''.join(sorted(chars, key=chars.get)))
    # the BGM list: the 13 choices, then CCE's other entries
    entries = [('cce', i) if kind == 'cce' else ('bare', i) for kind, i in CHOICES] + [('cce', i) for i in REST]
    tracks = CHOICE_TRACKS + REST_TRACKS
    assert len(entries) == len(tracks) <= min(NAME_CAP, TRACK_CAP)
    src += [f'.org {NAME_TABLE_AT:08X}']
    for kind, i in entries:
        if kind == 'cce':
            at, w = name_entry(slct, i)
            src += [f'    .long  0x{at:08X}', f'    .word  {w}', '    .word  0x0018']
        else:
            src += [f'    .long  bare_{i}', f'    .word  {bare[i].shape[1]}', '    .word  0x0018']
    src += [f'.org {TRACK_TABLE_AT:08X}', '    .byte  ' + ', '.join(map(str, tracks))]
    sections = sh2asm.assemble(src)
    end = max(org + len(code) for org, code in sections)
    blob = bytearray(end - base)
    for org, code in sections:
        blob[org - base:org - base + len(code)] = code
    assert NAME_TABLE_AT + 8 * NAME_CAP <= TRACK_TABLE_AT and TRACK_TABLE_AT + TRACK_CAP <= CODE_AT
    return opt + bytes(base - OPT_AT - len(opt)) + bytes(blob), len(chars), len(entries)


def main():
    cce, dst = sys.argv[1], sys.argv[2]
    opt = open(os.path.join(cce, 'DAYTONA', 'OPT.DAT'), 'rb').read()
    slct = open(os.path.join(cce, 'DAYTONA', 'SLCT.BIN'), 'rb').read()
    out, n, entries = build(opt, slct)
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'OPT.DAT'), 'wb').write(out)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n_ for n_ in ['DAYTONA/OPT.DAT'] if n_ not in have]
    open(listing, 'w').write(''.join(n_ + '\n' for n_ in sorted(have)))
    print(f'options: ATTRACT : ORIGINAL / CCE, the BGM list ({entries} entries), {n} chars; '
          f'OPT.DAT {len(out)} bytes (the original {len(opt)})')


if __name__ == '__main__':
    main()
