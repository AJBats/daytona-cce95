"""Options > Sound, what CCE95 adds to the page, appended to DAYTONA/OPT.DAT:
the ATTRACT : ORIGINAL / CCE row, and the BGM list with DUSA's '95 songs
(docs/music.md).

usage: options_sound.py <cce extracted dir> <out dir> [95|original]
  Writes <out dir>/DAYTONA/OPT.DAT and lists it in PATCHED.txt. The last
  word is the disc's version of The King of Speed, Let's Go Away and Sky
  High (Makefile MUSIC, docs/options.md), '95's unless it says original.

The Options screens' text is drawn from OPT.DAT (loaded at 0x250000 while
Options is up): each label or value is a box of cells, 3 rows high, of
4-bit 8x8 chars, the letters dark on a light plate. The Sound page copies
its chars to VRAM 0xA000 (OPT.DAT +0x1C8FA, 0x150E0 bytes) and the main
page its own (+0x14B04, 0x7660 bytes); a cell is a char number from
there. Neither page has the words, so they are put together from letters
of the labels both pages show (the same face): ATTRACT, ORIGINAL and CCE
cut from ARCADE, TIME ATTACK, EXIT, SOUND, GAME MODE and HANDLING, with
ARCADE's plate ends and the neighbors' pixels in a cut made plate; the
label's colon is SOUND MODE's own cells. Their chars go where the new
names' do (below).

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
choices of patches/bgm_tables.s first, so a choice is its own entry in
both, then the sound test's 21 others: the goal jingles and the endings,
CCE's and those of the disc's King of Speed, Let's Go Away and Sky High
(and Pounding Pavement '95's), then Sons of Angels, Lack of Speed and David
Goes To Victory Lane. The disc carries one version of those three songs,
'95's or CCE's arcade originals, in tracks 23-31: choices 6-8 are that
version, and 9-11 (beta 2's originals) the same again under the same
names, so a save from then plays what the disc has. '95's songs are shown
by their bare names, the remixes' pictures cut before " (remix)": the cells
up to the cut are the remix's own, and the column the cut runs through gets
chars of its own. The originals keep CCE's "(original)" pictures. DUSA's
jingles and Victory Lane get pictures in CCE's lettering
(tools/sound_names.py); Pounding Pavement (reprise) is CCE's Pounding
Pavement (remix) with its last word redrawn. Each version makes only the
pictures it lists, and frees the chars of CCE's names it doesn't (the
'95 disc's: the originals' songs, goals and endings).
Left and right on a course row step through the choices grouped by version
(the disc's, then CCE's), and on the BGM test through the entries, past
9-11, each from a table of the next and the previous.

The new chars: a picture's char that one of CCE's listed names or the
page's own boxes already has is that char. The others go first where the
chars of the names the list leaves out were (The American Dream, Sunset on
the DAYTONA Beach, Crash & Burrn, and the version's unlisted ones: no
listed box uses them), rewritten in OPT.DAT so the page's own copy puts
them in VRAM; then after the Sound page's chars (VRAM 0x1F0E0 to 0x20000,
as far as the map's 12-bit char numbers reach), copied there by the code
below on each draw. Nothing below the page's chars is free: the S.E.
test's names fill VRAM 0x1000-0x9F4B, each entry loading its own set.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import sh2asm  # noqa: E402
import sound_names  # noqa: E402
from sound_names import name_entry, bare_cut  # noqa: E402

OPT_AT = 0x250000
SOUND_CHARS, MAIN_CHARS = 0x1C8FA, 0x14B04
# new chars' places in VRAM, as cells (a char from VRAM 0xA000; the map takes 12 bits of cell + 0x500)
HIGH_AT, HIGH_N, HIGH_TO = 0xA87, 0x79, 0x25E1F0E0     # past the Sound page's chars, to VRAM 0x20000

# The BGM list (patches/bgm_menu.s points SLCT.BIN at these places)
SLCT_AT = 0x06028000
NAMES, NAMES_N = 0x0603F860, 30     # CCE's name table: cells, width word, 0x0018
TRACKS = 0x0603FCF8                 # CCE's track table, a byte an entry
PAGE_BOXES = range(0x0603FB2C, 0x0603FC7C, 12)  # the page's own boxes in its chars: cells, x, y, colour, width
NAME_TABLE_AT, NAME_CAP = 0x2AD470, 48     # ours: right after the code's two entry branches
TRACK_TABLE_AT, TRACK_CAP = 0x2AD5F0, 48
CODE_AT = 0x2AD620
NAME_X, SCREEN_CELLS = 54, 88       # the BGM test's name box starts at cell 54 of the 704-pixel screen
# The pictures made for the list, CCE's names cut or redrawn and new ones: a remix to cut to a
# bare name, a new name in CCE's lettering, or a CCE name with its last word redrawn. All are
# made, in this order, whichever version of the songs the disc has.
BARE = (0, 1, 2, 4)                 # The King of Speed, Let's Go Away, Sky High, Pounding Pavement
NEW = ('Breakdown', "Raggin'", 'Check It Out!', 'Sweat', 'Rolling Start', 'The Dream of Daytona',
       'Can You Fly?', (4, '(reprise)'), 'David Goes To Victory Lane')
# Tracks 23-31 of the disc, in either version (docs/music.md): the songs, goals and endings of
# The King of Speed, Let's Go Away and Sky High, each as a picture: ('bare', i), ('new', what)
# or CCE's name entry ('cce', i)
VERSIONS = {'95': {'songs': [('bare', 0), ('bare', 1), ('bare', 2)],
                   'goals': [('new', 'Breakdown'), ('new', "Raggin'"), ('new', 'Check It Out!')],
                   'endings': [('new', 'Rolling Start'), ('new', 'The Dream of Daytona'), ('new', 'Can You Fly?')]},
            'original': {'songs': [('cce', 6), ('cce', 7), ('cce', 8)],
                         'goals': [('cce', 14), ('cce', 15), ('cce', 16)],
                         'endings': [('cce', 22), ('cce', 23), ('cce', 24)]}}


def bgm_list(music):
    """[(picture, track)]: the 13 BGM choices (patches/bgm_tables.s), then the sound test's others."""
    v = VERSIONS[music]
    choices = [('cce', i) for i in range(6)] + v['songs'] * 2 + [('bare', 4)]
    tracks = [2, 3, 4, 5, 6, 7, 23, 24, 25, 23, 24, 25, 22]
    test = ([(('cce', 9 + k), 8 + k) for k in range(5)]                             # CCE's goals
            + list(zip(v['goals'], (26, 27, 28))) + [(('new', 'Sweat'), 19)]
            + [(('cce', 17 + k), 13 + k) for k in range(5)]                        # CCE's endings
            + list(zip(v['endings'], (29, 30, 31))) + [(('new', (4, '(reprise)')), 34)]
            + [(('cce', 25), 18), (('cce', 27), 20), (('new', 'David Goes To Victory Lane'), 21)])
    return list(zip(choices, tracks)) + test


TEST_ENTRIES = 34                   # patches/bgm_menu.s: the BGM test row's maximum is this less one
ALIASES = {9: 6, 10: 7, 11: 8}      # beta 2's originals: the disc's version, as 6-8
STEP_SPAN = 40                      # the BGM test's step tables reach beta 2's 40 entries
DROPPED = (26, 28, 29)              # The American Dream, Sunset on the DAYTONA Beach, Crash & Burrn
ORDER = [6, 7, 8, 12, 0, 1, 2, 3, 4, 5]     # left/right on a course row: the disc's version, then CCE's
TEST_ORDER = [e for e in range(TEST_ENTRIES) if e not in ALIASES]   # left/right on the BGM test
# label: (chars, OPT.DAT address of its cells, width in cells)
WORDS = {'ARCADE': (MAIN_CHARS, 0x26C1C8, 9), 'TIME ATTACK': (MAIN_CHARS, 0x26C75C, 15),
         'GAME MODE': (MAIN_CHARS, 0x26C354, 18), 'HANDLING': (MAIN_CHARS, 0x26C46E, 12),
         'SOUND': (MAIN_CHARS, 0x26C72C, 8), 'EXIT': (SOUND_CHARS, 0x282D60, 6),
         'SOUND MODE': (SOUND_CHARS, 0x282D84, 16)}
# letter: (word, first pixel column, end), cut where the letters meet
LETTERS = {'A': ('ARCADE', 2, 13), 'R': ('ARCADE', 13, 23), 'C': ('ARCADE', 23, 34), 'E': ('ARCADE', 55, 65),
           'T': ('TIME ATTACK', 2, 13), 'I': ('EXIT', 24, 33), 'O': ('SOUND', 12, 24),
           'G': ('GAME MODE', 2, 13), 'N': ('HANDLING', 23, 34), 'L': ('HANDLING', 44, 55)}
# letter: pixels in its cut that belong to its neighbors, made plate (rows, columns in the cut):
# the notch above the L's foot where HANDLING's I begins, and the light line under the C's top
# arm in ARCADE
CLEAN = {'L': (slice(1, 9), slice(7, 11)), 'C': (slice(10, 12), slice(6, 11))}
# the same for a letter cut from its word's left end, kept where it starts a word: ARCADE's
# slanted edge in the A's first column
WORD_START = {'A': (slice(1, 12), slice(0, 1))}
PLATE = 15
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
    cut = lambda w, a, b: words[w][:, a:b].copy()

    def letter(k, ch):
        img = cut(*LETTERS[ch])
        if ch in CLEAN:
            img[CLEAN[ch]] = PLATE
        if k > 0 and ch in WORD_START:
            img[WORD_START[ch]] = PLATE
        return img

    img = np.concatenate([cut(*PLATE_LEFT)] + [letter(k, ch) for k, ch in enumerate(text)]
                         + [cut(*PLATE_RIGHT)], 1)
    return np.pad(img, ((0, 0), (0, -img.shape[1] % 8)))


class Chars:
    """The page's chars, CCE's and new: a char's 32 bytes -> its cell."""

    def __init__(self, opt, slct, unlisted):
        self.opt = bytearray(opt)
        kept = set()
        for e in PAGE_BOXES:
            at = struct.unpack_from('>I', slct, e - SLCT_AT)[0]
            kept |= set(self.cells_at(at, slct[e - SLCT_AT + 10]).ravel())
        for i in range(NAMES_N):
            if i not in unlisted:
                kept |= set(self.cells_at(*name_entry(slct, i)).ravel())
        dropped = set()
        for i in unlisted:
            dropped |= set(self.cells_at(*name_entry(slct, i)).ravel())
        self.freed = sorted(dropped - kept - {0})
        self.cell = {}
        for c in sorted(kept):
            self.cell.setdefault(self.char(c), c)
        self.high, self.reused = [], 0

    def cells_at(self, at, w):
        return np.array(struct.unpack_from(f'>{3 * w}H', self.opt, at - OPT_AT)).reshape(3, w)

    def char(self, c):
        return bytes(self.opt[SOUND_CHARS + 32 * c:SOUND_CHARS + 32 * c + 32])

    def of(self, t):
        if t in self.cell:
            return self.cell[t]
        if self.reused < len(self.freed):
            c = self.freed[self.reused]
            self.opt[SOUND_CHARS + 32 * c:SOUND_CHARS + 32 * c + 32] = t
            self.reused += 1
        elif len(self.high) < HIGH_N:
            c = HIGH_AT + len(self.high)
            self.high.append(t)
        else:
            sys.exit('options_sound: no room left for the page\'s chars')
        self.cell[t] = c
        return c


def to_cells(img, chars, width=None):
    """Cells for an image, its new chars given places by `chars`."""
    w = width or img.shape[1] // 8
    out = np.zeros((3, w), np.uint16)
    for r in range(3):
        for c in range(img.shape[1] // 8):
            px = img[8 * r:8 * r + 8, 8 * c:8 * c + 8]
            if px.any():
                out[r, c] = chars.of(bytes((px[:, 0::2] << 4 | px[:, 1::2]).astype(np.uint8).ravel()))
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

; The page's own text is drawn: the new chars into VRAM (the run of
; copies), then ATTRACT's three boxes as 060312D0 draws its own (0602991C):
; the label in its highlight while the cursor is on it, the choice lit as
; the page lights a row's value.
draw_after:
    mov.l  r14,@-r15
    mov.l  r13,@-r15
    mova   copies,r0
    mov    r0,r14
    mov    #1,r13
next_copy:
    mov.l  @r14+,r1         ; from
    mov.l  @r14+,r2         ; to
    mov.l  @r14+,r3         ; longs
    tst    r3,r3
    bt     copied
copy:
    mov.l  @r1+,r0
    dt     r3
    mov.l  r0,@r2
    bf/s   copy
    add    #4,r2
copied:
    dt     r13
    bf     next_copy
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
; order, and on the BGM test through its entries; the rest goes on as
; before.
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
; rows 12-17: the next or previous choice or entry, then the page stores
; the value in the row's place and redraws as for its own left and right
; (060319D2)
course:
    add    #-12,r0
    mov    #6,r2
    cmp/hs r2,r0
    bt     buttons
    mov    r0,r3            ; 5: the BGM test
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
    mov    #5,r1
    cmp/eq r1,r3
    bf     course_value
    add    #{span},r0       ; the BGM test's table follows the courses'
course_value:
    mov.b  @r13,r2
    extu.b r2,r2
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
.align 4
copies:                     ; from, to, longs
    .long  chars_high
    .long  {high_to:#010x}
    .long  {high_longs}
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
bgm_next:                   ; by choice, the next in ORDER; then by entry, the next in TEST_ORDER
    .byte  {bgm_next}
.align 4
bgm_prev:
    .byte  {bgm_prev}
.align 4
after_at:
    .long  draw_after
rest_at:
    .long  0x060312DC
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


def bare_name(opt, slct, i, chars):
    """The remix's picture (name entry i) cut before " (remix)": the gap of
    empty columns before the last word. Cells up to the cut are the remix's;
    the column the cut runs through gets chars of its own."""
    cells = sound_names.cells_of(opt, *name_entry(slct, i))
    img = sound_names.render(opt, cells)
    x = bare_cut(img)
    n = (x + 7) // 8
    out = cells[:, :n].copy()
    if x % 8:
        column = img[:, 8 * (n - 1):8 * n].copy()
        column[:, x % 8:] = 0
        out[:, n - 1] = to_cells(column, chars)[:, 0]
    return out


def steps(order, n, aliases):
    """The next and the previous value in order, by value, for values below n: an alias steps as
    its value does, and any other value not in order steps to order's first."""
    nxt = {v: order[(k + 1) % len(order)] for k, v in enumerate(order)}
    prv = {v: order[k - 1] for k, v in enumerate(order)}
    for a, v in aliases.items():
        nxt[a], prv[a] = nxt[v], prv[v]
    return [nxt.get(v, order[0]) for v in range(n)], [prv.get(v, order[0]) for v in range(n)]


def build(opt, slct, music='95'):
    listed = bgm_list(music)
    shown = {what for what, _ in listed}
    cce_names = {i for v in VERSIONS.values() for pics in v.values() for kind, i in pics if kind == 'cce'}
    unlisted = set(DROPPED) | (cce_names - {i for kind, i in shown if kind == 'cce'})
    chars = Chars(opt, slct, unlisted)
    lettering = sound_names.Lettering(opt, slct)     # from the original chars, before any is rewritten
    label = np.zeros((3, 16), np.uint16)
    attract = to_cells(word(opt, 'ATTRACT'), chars)
    label[:, :attract.shape[1]] = attract
    a, b = COLON_CELLS
    label[:, a:b] = cells_of(opt, 'SOUND MODE')[:, a:b]
    original = to_cells(word(opt, 'ORIGINAL'), chars)
    cce = to_cells(word(opt, 'CCE'), chars)
    # the pictures the version lists; then the 13 choices and the sound test's others
    names = {}                                       # label -> cells
    picture = {}                                     # ('bare', i) or ('new', what) -> (label, width)
    for i in BARE:
        if ('bare', i) not in shown:
            continue
        names[f'bare_{i}'] = bare_name(opt, slct, i, chars)
        picture['bare', i] = (f'bare_{i}', names[f'bare_{i}'].shape[1])
    for k, what in enumerate(NEW):
        if ('new', what) not in shown:
            continue
        img = lettering.renamed(*what) if isinstance(what, tuple) else lettering.name(what)
        w = img.shape[1] // 8
        assert NAME_X + w <= SCREEN_CELLS, f'{what}: {w} cells run past the screen'
        names[f'name_{k}'] = to_cells(img, chars)
        picture['new', what] = (f'name_{k}', w)
    entries = [name_entry(slct, what) if kind == 'cce' else picture[kind, what] for (kind, what), _ in listed]
    tracks = [track for _, track in listed]
    assert len(entries) == len(tracks) == TEST_ENTRIES <= min(NAME_CAP, TRACK_CAP)

    base = OPT_AT + len(opt) + (-len(opt) % 4)
    assert base + 8 == NAME_TABLE_AT, hex(base)
    course_next, course_prev = steps(ORDER, 13, ALIASES)
    span = (13 + 3) & ~3
    test_next, test_prev = steps(TEST_ORDER, STEP_SPAN, ALIASES)
    bgm_next = course_next + [0] * (span - 13) + test_next
    bgm_prev = course_prev + [0] * (span - 13) + test_prev
    src = CODE.format(base=base, code_at=CODE_AT, original_w=original.shape[1] << 8,
                      cce_x=0x11 + original.shape[1] + 1, cce_w=cce.shape[1] << 8,
                      high_to=HIGH_TO, high_longs=8 * len(chars.high),
                      span=span, bgm_next=', '.join(map(str, bgm_next)),
                      bgm_prev=', '.join(map(str, bgm_prev))).splitlines()
    src += ['.align 4'] + words_of('label_cells', label.astype('>u2').tobytes())
    src += words_of('original_cells', original.astype('>u2').tobytes())
    src += words_of('cce_cells', cce.astype('>u2').tobytes())
    for name, cells in names.items():
        src += words_of(name, cells.astype('>u2').tobytes())
    src += ['.align 4'] + words_of('chars_high', b''.join(chars.high))
    src += [f'.org {NAME_TABLE_AT:08X}']
    for at, w in entries:
        at = f'0x{at:08X}' if isinstance(at, int) else at
        src += [f'    .long  {at}', f'    .word  {w}', '    .word  0x0018']
    src += [f'.org {TRACK_TABLE_AT:08X}', '    .byte  ' + ', '.join(map(str, tracks))]
    sections = sh2asm.assemble(src)
    end = max(org + len(code) for org, code in sections)
    blob = bytearray(end - base)
    for org, code in sections:
        blob[org - base:org - base + len(code)] = code
    assert NAME_TABLE_AT + 8 * NAME_CAP <= TRACK_TABLE_AT and TRACK_TABLE_AT + TRACK_CAP <= CODE_AT
    out = bytes(chars.opt) + bytes(base - OPT_AT - len(opt)) + bytes(blob)
    return out, (chars.reused, len(chars.freed), len(chars.high)), len(entries)


def main():
    cce, dst = sys.argv[1], sys.argv[2]
    music = sys.argv[3] if len(sys.argv) > 3 else '95'
    if music not in VERSIONS:
        sys.exit(f'options_sound: no version of the songs called {music!r}: {" or ".join(VERSIONS)}')
    opt = open(os.path.join(cce, 'DAYTONA', 'OPT.DAT'), 'rb').read()
    slct = open(os.path.join(cce, 'DAYTONA', 'SLCT.BIN'), 'rb').read()
    out, (reused, freed, high), entries = build(opt, slct, music)
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'OPT.DAT'), 'wb').write(out)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n_ for n_ in ['DAYTONA/OPT.DAT'] if n_ not in have]
    open(listing, 'w').write(''.join(n_ + '\n' for n_ in sorted(have)))
    print(f'options: ATTRACT : ORIGINAL / CCE, the BGM list ({entries} entries, songs {music}); new chars: {reused} of the '
          f'unlisted names\' {freed}, {high} of {HIGH_N} past the page\'s; '
          f'OPT.DAT {len(out)} bytes (the original {len(opt)})')


if __name__ == '__main__':
    main()
