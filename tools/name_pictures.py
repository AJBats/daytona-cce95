"""The pictures of the cars on DUSA's body after a race, rendered from its
model in both liveries as car select's are (tools/car_pictures.py): DUSA's
car (the Hornet on DUSA's body and the secret car) and each '95 car, on
the name entry and the two-player result (docs/car_select.md, "The name
entry's pictures").

usage: name_pictures.py <dusa extracted dir> <cce extracted dir> <out dir>
  Writes DAYTONA/NAMED.BIN and DAYTONA/RESULT2P.BIN (CCE's, with code in
  their tails) and the pictures, NAME95.BIN, under <out dir>/DAYTONA, and
  lists them in PATCHED.txt. Run after tools/apply_patches.py: it checks
  the patched NAME.BIN and RESULT2P.BIN call the code.

The name entry (NAME.BIN) reads NAMED.BIN whole to 0x220000 and draws the
player's car on NBG1 at (160, 336) of its 704 x 448 screen, below the
letters; the two-player result (RESULT2P.BIN, one file at 06028000) draws
both players' cars on NBG0, the winner and the loser, at (80, 344) and
(368, 344). Both use CCE's same eleven pictures (its eight cars, the secret
car, the horses): 32 x 12 cells of 256-colour chars over one palette, the
car nose left on a blue marble with its shadow, the marble drawn in.

Ours are car select's picture turned a quarter left, as long as CCE's
cars are here or a little taller than they are (DUSA's body is wider for
its length), the shadow darkening the screen's own marble at the
picture's place, and everything else colour 0, transparent, so the marble
is the screen's and the edges don't show. On the name entry, one picture
of the car with 255 colours of its own for each livery, which the code
puts in CRAM. On the result both cars share CCE's palette, so each player's
place and gearbox has its own picture in CCE's colours.

NAME95.BIN holds them all, PICTURE_SECTORS apart: picture n of kind k at
(8k + n) x PICTURE_SECTORS, n the car from 0 (0 DUSA's car), kind 0 the
name entry's, 1 and 2 the winner's place (player 1) automatic and manual,
3 and 4 the loser's (player 2). The code reads only the ones it shows
(GFS_Seek and GFS_Fread, as patches/attract_load.s does): all of them
would add 1 MB to a load, and the disc's DAYTONA directory had room for one
more file, not eight.

patches/name_pictures.s points the name entry's picture switch at the
code in NAMED.BIN's tail (CODE_AT): a car on DUSA's body (patches/
car_choice.s: the secret car always, the others with DUSA's body chosen,
002FC3A9 + player) has its picture read to FILE_AT and drawn with the
gearbox's colours (002FC3A7 + player); any other car, or a picture that
didn't arrive, goes to its own case. patches/result2p_pictures.s has the
result's setup call the code in RESULT2P.BIN's tail (R2P_CODE_AT) first,
which reads each such player's picture to R2P_BUFFERS and gives that player
an entry of its own (11 or 12) in a copy of the pictures' table, through
copies of the car bytes the setup reads.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
import car_pictures as cp  # noqa: E402
import liveries  # noqa: E402
import sh2asm  # noqa: E402

LOAD = 0x00220000                       # NAMED.BIN's place
CODE_AT = 0x00278780                    # after CCE's NAMED.BIN (to 0x278770)
FILE_AT = 0x00279000                    # a picture's place, free in the name entry
PICTURE_SECTORS = 16                    # each picture's sectors in NAME95.BIN
KINDS = 5                               # the name entry's; the winner's and the loser's, each gearbox
TAG = 0x4E393550                        # 'N95P'
SWITCH_LITERAL = 0x06029C30             # patches/name_pictures.s
COLS, ROWS = 32, 12
W, H = 8 * COLS, 8 * ROWS
CAR_COLS, CAR_MID = (9, 247), 48        # where CCE's pictures put the car: its columns, its middle row
CAR_WIDTH = 80                          # at most this tall: DUSA's body is wider for its length than CCE's drawings
SHADOW, SHADOW_BLUR = (2, 2), 7         # the shadow's offset (down, right) and blur
MAX_CHARS = 378                         # as much as CCE's biggest picture takes
COLOURS = 255                           # palette entries 1-255; 0 is transparent
CCE_PALETTE = 0x25F5EC                  # CCE's pictures' palette in NAMED.BIN (the same in RESULT2P.BIN)

# the name entry's screen: the marble under the picture is its NBG0, 88 x 56 cells
NAME_AT = (160, 336)
NAME_BG = dict(base=LOAD, chars=0x26A4AC, map=0x275EF0, palette=0x278570)

# the two-player result: its marble is its NBG3
R2P_BASE, R2P_END = 0x06028000, 0x06099E20     # RESULT2P.BIN's place and its end
R2P_CODE_AT, R2P_TABLE_AT = 0x0609B000, 0x0609B200     # past its work RAM (to 0609A700); patches/result2p_pictures.s
R2P_TABLE = 0x0608C344                  # CCE's pictures' table: chars, map, 32 x 12, the chars' size
R2P_HOOKS = {0x06029138: 'r2p_setup', 0x06029170: 'table', 0x06029174: 'cars',
             0x060292CC: 'cars + 1', 0x06029330: 'cars'}
R2P_SCROLL = 0x06029DE4                 # the call the setup's hook replaces
R2P_AT = ((80, 344), (368, 344))        # the winner's (player 1's) and the loser's places
R2P_BG = dict(base=R2P_BASE, chars=0x0603EC30, map=0x06033C20, palette=0x06049CB4)
R2P_BUFFERS = (0x00279000, 0x00281000)  # work RAM low, free in the result

# a picture: the tag, the chars' size, the map, the automatic and manual
# colours (the name entry's only), the chars
MAP_OFF = 8
AT_OFF = MAP_OFF + 2 * COLS * ROWS
MT_OFF = AT_OFF + 2 * 256
CHARS_OFF = MT_OFF + 2 * 256

# r4 the car, r5 the player -> r0 its picture number on DUSA's body, or -1;
# then: r4 the first sector, r5 where -> T the picture read. Uses r0-r7.
COMMON = '''
body:
    mov    r4,r0
    cmp/eq #8,r0
    bt     body_dusa            ; the secret car: DUSA's car always
    mov    #7,r1
    cmp/hi r1,r4
    bt     body_cce             ; the horses
    mov.l  choice_at,r1
    add    r5,r1
    mov.b  @r1,r1
    tst    r1,r1
    bt     body_done            ; DUSA's body chosen: the car's own number
body_cce:
    rts
    mov    #-1,r0
body_dusa:
    mov    #0,r0
body_done:
    rts
    nop

read:
    sts.l  pr,@-r15
    mov.l  r8,@-r15
    mov.l  r9,@-r15
    mov.l  r10,@-r15
    mov    r4,r9                ; the sector
    mov    r5,r10               ; where
    mov.l  busy_at,r1
    mov    #0,r0
    mov.b  r0,@r1               ; reading, as 060058B4
    mov.l  r0,@r10              ; no tag until the picture is read
    mov.l  name_at,r4
    mov.l  gfs_id,r0
    jsr    @r0
    nop
    mov.l  gfs_open,r1
    jsr    @r1
    mov    r0,r4
    mov    r0,r8                ; the file
    mov    r0,r4
    mov    r9,r5
    mov.l  gfs_seek,r0
    jsr    @r0
    mov    #0,r6
    mov    r8,r4
    mov    #{sectors},r5
    mov    r10,r6
    mov    #14,r7
    mov.l  gfs_read,r0
    jsr    @r0
    shll16 r7                   ; at most 0xE0000 bytes, as 060058B4
    mov.l  gfs_close,r0
    jsr    @r0
    mov    r8,r4
    mov.l  busy_at,r1
    mov    #1,r0
    mov.b  r0,@r1
    mov.l  @r10,r1
    mov.l  tag,r2
    cmp/eq r1,r2
    mov.l  @r15+,r10
    mov.l  @r15+,r9
    mov.l  @r15+,r8
    lds.l  @r15+,pr
    rts
    nop

.align 4
car_at:
    .long  0x002FC230           ; each player's car, from 0
choice_at:
    .long  0x002FC3A9           ; each player's body: 0 DUSA's
gear_at:
    .long  0x002FC3A7           ; each player's gearbox: 0 automatic
busy_at:
    .long  0x06011FB8           ; 0 while the disc is read
gfs_id:
    .long  0x0600A3E4           ; GFS_NameToId (name) -> id
gfs_open:
    .long  0x0600A582           ; GFS_Open (id) -> file
gfs_seek:
    .long  0x0600A64A           ; GFS_Seek (file, sector, 0)
gfs_read:
    .long  0x0600A95C           ; GFS_Fread (file, sectors, address, most bytes)
gfs_close:
    .long  0x0600A62C           ; GFS_Close (file)
tag:
    .long  {tag:#x}
name_at:
    .long  {name_at:#x}
'''

NAME_CODE = '''
.org {code_at:#x}
; NAME 06029C04, the name entry's picture switch, calls here for the car
; (r9-r14 as the switch's cases use them). -> r0 the car for its own
; case, or 11 (none) once ours is drawn; r1 11.
name_picture:
    sts.l  pr,@-r15
    mov.l  r8,@-r15
    mov.l  car_at,r0
    mov.b  @r0,r8               ; the car
    mov    r8,r4
    bsr    body
    mov    #0,r5                ; player 1
    cmp/pz r0
    bf     own_case             ; CCE's car
    shll2  r0
    shll2  r0
    mov    r0,r4                ; its picture's first sector (kind 0)
    mov.l  file_at,r5
    bsr    read
    nop
    bf     own_case             ; not read
    mov.l  gear_at,r1           ; the gearbox's colours into CRAM 0x600
    mov.b  @r1,r0
    mov.w  at_off,r4
    tst    r0,r0
    bt     colours
    mov.w  mt_off,r4
colours:
    mov.l  file_at,r1
    add    r1,r4
    mov.w  k_300,r5
    mov.w  k_100,r6
    mov.l  set_colours,r0
    jsr    @r0
    nop
    mov.l  file_at,r1           ; the chars, as the cases copy theirs
    mov.l  @(4,r1),r6
    mov.w  chars_off,r4
    add    r1,r4
    jsr    @r11
    mov    r14,r5
    mov.l  r12,@-r15            ; the map, as the cases draw theirs
    mov.l  r14,@-r15
    mov.l  r9,@-r15
    mov    #32,r2
    mov.l  r2,@-r15
    mov.l  file_at,r4
    add    #{map_off},r4
    mov    r13,r5
    mov    #20,r6
    jsr    @r10
    mov    #42,r7
    add    #16,r15
    mov    #11,r8               ; drawn: no case
own_case:
    mov    r8,r0
    mov    #11,r1
    mov.l  @r15+,r8
    lds.l  @r15+,pr
    rts
    nop

at_off:
    .word  {at_off}
mt_off:
    .word  {mt_off}
chars_off:
    .word  {chars_off}
k_300:
    .word  0x300                ; the pictures' colours, CRAM 0x600
k_100:
    .word  0x100
.align 4
set_colours:
    .long  0x0602CD64           ; NAME's colour copy (colours, CRAM entry, count)
file_at:
    .long  {file_at:#x}
'''

R2P_CODE = '''
.org {code_at:#x}
; RESULT2P 06029064, the result's setup, calls here in 06029DE4's place
; (r4, r5 its arguments) before it reads the cars: each player's car into
; cars, or for a car on DUSA's body its picture read and 11 + player,
; that player's entry in table.
r2p_setup:
    sts.l  pr,@-r15
    mov.l  r4,@-r15
    mov.l  r5,@-r15
    mov.l  r8,@-r15
    mov.l  r9,@-r15
    mov    #0,r8                ; the player
player:
    mov.l  car_at,r1
    add    r8,r1
    mov.b  @r1,r4               ; the car
    mova   cars,r0
    add    r8,r0
    mov.b  r4,@r0               ; its own picture unless ours arrives
    bsr    body
    mov    r8,r5
    cmp/pz r0
    bf     next                 ; CCE's car
    mov    r0,r9                ; its picture number
    mov.l  gear_at,r1
    add    r8,r1
    mov.b  @r1,r0
    add    r8,r0
    add    r8,r0
    add    #1,r0                ; kind: 1 + 2 x player + gearbox
    shll2  r0
    shll   r0
    add    r9,r0
    shll2  r0
    shll2  r0
    mov    r0,r4                ; its first sector
    mov.l  buffer_0,r5
    tst    r8,r8
    bt     read_it
    mov.l  buffer_1,r5
read_it:
    bsr    read
    mov    r5,r9                ; where
    bf     next                 ; not read
    mova   entries,r0           ; the player's entry: chars, map, 32 x 12, the chars' size
    mov    r8,r1
    shll2  r1
    shll2  r1
    add    r1,r0
    mov.w  chars_off2,r1
    add    r9,r1
    mov.l  r1,@r0
    mov    r9,r1
    add    #{map_off},r1
    mov.l  r1,@(4,r0)
    mov.l  size,r1
    mov.l  r1,@(8,r0)
    mov.l  @(4,r9),r1
    mov.l  r1,@(12,r0)
    mova   cars,r0
    add    r8,r0
    mov    #11,r1
    add    r8,r1
    mov.b  r1,@r0
next:
    add    #1,r8
    mov    r8,r0
    cmp/eq #2,r0
    bf     player
    mov.l  @r15+,r9
    mov.l  @r15+,r8
    mov.l  @r15+,r5
    mov.l  @r15+,r4
    lds.l  @r15+,pr
    mov.l  scroll,r0            ; the call it replaced
    jmp    @r0
    nop

chars_off2:
    .word  {chars_off}
.align 4
buffer_0:
    .long  {buffer_0:#x}
buffer_1:
    .long  {buffer_1:#x}
size:
    .long  0x0020000C           ; 32 x 12 cells
scroll:
    .long  {scroll:#x}
'''

R2P_DATA = '''
.org {table_at:#x}
table:
{table}entries:
    .long  0
    .long  0
    .long  0
    .long  0
    .long  0
    .long  0
    .long  0
    .long  0
cars:
    .long  0
'''


def background(data, at, bg):
    """A screen's marble under a picture at (x, y): its 88 x 56 cell layer
    (bg: where data is loaded, its chars, map and palette), (H, W, 3)."""
    base = bg['base']
    pal = np.array([cp.rgb(c) for c in struct.unpack_from('>256H', data, bg['palette'] - base)])
    cells = struct.unpack_from(f'>{88 * 56}H', data, bg['map'] - base)
    idx = np.zeros((H, W), int)
    x, y = at
    for r in range(ROWS):
        for c in range(COLS):
            n = cells[(y // 8 + r) * 88 + x // 8 + c] & 0xFFF
            at_ = bg['chars'] - base + 32 * n
            idx[8 * r:8 * r + 8, 8 * c:8 * c + 8] = np.frombuffer(data, np.uint8, 64, at_).reshape(8, 8)
    return pal[idx]


def view(poly, tex):
    """The car nose left, as long as CCE's are here or as tall as CAR_WIDTH:
    (colour, coverage) at the picture's size."""
    img, cover = cp.render(poly, tex, size=(H, W), rows=CAR_COLS, mid=H - CAR_MID, width=CAR_WIDTH)
    img, cover = np.rot90(img), np.rot90(cover)
    s = cp.SS
    return img.reshape(H, s, W, s, 3).mean(axis=(1, 3)), cover.reshape(H, s, W, s).mean(axis=(1, 3))


def shadow(cover):
    """How dark the shadow makes the marble, 0-1: the car's coverage moved
    down and right, blurred, as CCE's pictures have it."""
    dy, dx = SHADOW
    s = np.zeros_like(cover)
    s[dy:, dx:] = cover[:H - dy, :W - dx]
    blur = Image.fromarray((s * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
    return np.clip(np.asarray(blur, float) / 255 * 2.2, 0, 1)


def record(idx, at_pal, mt_pal, colours=True):
    """A picture as NAME95.BIN keeps it (the colours only if colours)."""
    chars, cells = cp.pack(idx, at_pal, mt_pal, MAX_CHARS)
    words = [struct.pack('>256H', *(cp.colour_word(v) for v in p)) if colours else bytes(512) for p in (at_pal, mt_pal)]
    out = struct.pack('>II', TAG, len(chars)) + cells + words[0] + words[1] + chars
    assert len(cells) == AT_OFF - MAP_OFF and out[CHARS_OFF:] == chars
    assert len(out) <= PICTURE_SECTORS * 2048
    return out, len(chars) // 64


class Car:
    """A car's renders in both liveries, and its pictures over a marble."""
    def __init__(self, poly, at_tex, mt_tex):
        self.at, self.cover = view(poly, at_tex)
        self.mt, _ = view(poly, mt_tex)
        self.dark = shadow(self.cover)
        self.shown = (self.cover > 0.02) | (self.dark > 0.03)

    def over(self, img, marble):
        return img + marble * (1 - self.dark[..., None]) * (1 - self.cover[..., None])

    def own(self, marble):
        """The name entry's: one index picture, colours of its own for each livery."""
        at, mt = self.over(self.at, marble), self.over(self.mt, marble)
        c = cp.own_colours(at, mt, self.shown, n=COLOURS)
        at_pal, mt_pal = np.zeros((256, 3)), np.zeros((256, 3))
        at_pal[1:1 + len(c)], mt_pal[1:1 + len(c)] = c[:, :3], c[:, 3:]
        idx = cp.diffuse(at, mt, self.shown, np.zeros((H, W), int), at_pal, mt_pal, np.arange(1, 1 + len(c)))
        return record(idx, at_pal, mt_pal)

    def in_colours(self, marble, manual, pal):
        """A livery's picture in the palette pal (CCE's)."""
        img = self.over(self.mt if manual else self.at, marble)
        idx = cp.diffuse(img, img, self.shown, np.zeros((H, W), int), pal, pal, np.arange(1, 256))
        return record(idx, pal, pal, colours=False)


def assemble(text, **fields):
    """Code at its .orgs -> {address: bytes}."""
    return dict(sh2asm.assemble(text.format(**fields).splitlines()))


def place(blocks, start, end):
    """Assembled blocks laid out from start to end (zeros between)."""
    out = bytearray(end - start)
    for at, code in blocks.items():
        assert start <= at and at + len(code) <= end, f'{at:08X}'
        out[at - start:at - start + len(code)] = code
    return bytes(out)


def label(text, name, **fields):
    """A label's address in assembled text."""
    lines = text.format(**fields).splitlines()
    marker = f'{name}:'
    assert marker in [line.strip() for line in lines]
    probe = '\n'.join(lines) + f'\n.align 4\n_probe_:\n    .long  {name}\n'
    blocks = sh2asm.assemble(probe.splitlines())
    org, code = blocks[-1]
    return struct.unpack_from('>I', code, len(code) - 4)[0]


def build(dusa, cce, dst):
    """{file: data}: NAMED.BIN and RESULT2P.BIN with the code, and NAME95.BIN; the chars of each picture."""
    patched = {n: open(os.path.join(dst, 'DAYTONA', n), 'rb').read() for n in ('NAME.BIN', 'RESULT2P.BIN')}
    named = open(os.path.join(cce, 'DAYTONA', 'NAMED.BIN'), 'rb').read()
    r2p = open(os.path.join(cce, 'DAYTONA', 'RESULT2P.BIN'), 'rb').read()
    assert LOAD + len(named) <= CODE_AT and R2P_BASE + len(r2p) == R2P_END
    pal = np.array([cp.rgb(c) for c in struct.unpack_from('>256H', named, CCE_PALETTE - LOAD)])
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
    marbles = [background(named, NAME_AT, NAME_BG)] + [background(r2p, at, R2P_BG) for at in R2P_AT]
    cars = {0: Car(poly, cp.textures(texpl, False), cp.textures(texpl, True))}
    sources = liveries.Sources(dusa, cce)
    for number, paint in liveries.NINETY_FIVE.items():
        p = paint(sources)
        art = liveries.ninety_five_art(number, sources, cp.ART_SCALE)
        cars[number - 1] = Car(poly, cp.paint_textures(p, False, art[0]), cp.paint_textures(p, True, art[1]))
    assert sorted(cars) == list(range(8))
    pictures, sizes = {}, {}
    for n, car in cars.items():
        pictures[0, n] = car.own(marbles[0])
        for player in (0, 1):
            for manual in (0, 1):
                pictures[1 + 2 * player + manual, n] = car.in_colours(marbles[1 + player], manual, pal)
    pics95 = bytearray(KINDS * 8 * PICTURE_SECTORS * 2048)
    for (kind, n), (data, chars) in pictures.items():
        at = (8 * kind + n) * PICTURE_SECTORS * 2048
        pics95[at:at + len(data)] = data
        sizes[kind, n] = chars
    assert PICTURE_SECTORS == 16                    # the code's shifts

    out = {'NAME95.BIN': bytes(pics95)}
    name_at = CODE_AT + 0x400
    fields = dict(code_at=CODE_AT, file_at=FILE_AT, tag=TAG, name_at=name_at, sectors=PICTURE_SECTORS,
                  map_off=MAP_OFF, at_off=AT_OFF, mt_off=MT_OFF, chars_off=CHARS_OFF)
    blocks = assemble(NAME_CODE + COMMON, **fields)
    blocks[name_at] = b'NAME95.BIN'.ljust(16, b'\0')
    assert struct.unpack_from('>I', patched['NAME.BIN'], SWITCH_LITERAL - 0x06028000)[0] == CODE_AT, \
        'NAME.BIN does not call the code: patches/name_pictures.patch'
    out['NAMED.BIN'] = named + place(blocks, LOAD + len(named), name_at + 16)

    name_at = R2P_TABLE_AT + 0x100
    table = ''.join(f'    .long  {v:#x}\n' for v in struct.unpack_from('>44I', r2p, R2P_TABLE - R2P_BASE))
    fields = dict(code_at=R2P_CODE_AT, table_at=R2P_TABLE_AT, table=table, tag=TAG, name_at=name_at,
                  sectors=PICTURE_SECTORS, map_off=MAP_OFF, chars_off=CHARS_OFF, buffer_0=R2P_BUFFERS[0],
                  buffer_1=R2P_BUFFERS[1], scroll=R2P_SCROLL)
    text = R2P_CODE + COMMON + R2P_DATA
    blocks = assemble(text, **fields)
    blocks[name_at] = b'NAME95.BIN'.ljust(16, b'\0')
    for literal, name in R2P_HOOKS.items():
        base, _, plus = name.partition(' + ')
        want = label(text, base, **fields) + int(plus or 0)
        got = struct.unpack_from('>I', patched['RESULT2P.BIN'], literal - R2P_BASE)[0]
        assert got == want, f'RESULT2P.BIN {literal:08X} has {got:08X}, the code wants {want:08X}: ' \
                            'patches/result2p_pictures.s'
    out['RESULT2P.BIN'] = patched['RESULT2P.BIN'] + place(blocks, R2P_END, name_at + 16)
    for at in R2P_BUFFERS:
        assert at + PICTURE_SECTORS * 2048 <= 0x00290000
    return out, sizes


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    out, sizes = build(dusa, cce, dst)
    for name, data in out.items():
        open(os.path.join(dst, 'DAYTONA', name), 'wb').write(data)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [f'DAYTONA/{n}' for n in out if f'DAYTONA/{n}' not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'name and result pictures: cars 0-7, at most {max(sizes.values())} chars (room for {MAX_CHARS}); '
          f'NAME95.BIN {len(out["NAME95.BIN"])} bytes')


if __name__ == '__main__':
    main()
