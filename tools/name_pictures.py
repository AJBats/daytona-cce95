"""The name entry's pictures of the cars on DUSA's body, rendered from its
model in both liveries as car select's are (tools/car_pictures.py): DUSA's
car (the Hornet on DUSA's body and the secret car) and each '95 car
(docs/car_select.md, "The name entry's pictures").

usage: name_pictures.py <dusa extracted dir> <cce extracted dir> <out dir>
  Writes DAYTONA/NAMED.BIN (CCE's, with the code in its tail) and the
  pictures, NAME95.BIN, under <out dir>/DAYTONA, and lists them in
  PATCHED.txt. Run after tools/apply_patches.py: it checks the patched
  NAME.BIN calls the code.

The name entry (NAME.BIN) reads NAMED.BIN whole to 0x220000 and draws the
player's car on NBG1 at cell (20, 42) of its 704 x 448 screen, below the
letters: 32 x 12 cells of 256-colour chars over one palette, CRAM 0x600,
the car nose left on a blue marble with its shadow. CCE's eleven pictures
(its eight cars, the secret car, the horses) share that palette; each has
its marble drawn in.

Ours are car select's picture turned a quarter left, as long as CCE's
cars are here or a little taller than they are (DUSA's body is wider for
its length), its shadow darkening the screen's own marble (NBG0, the same
place), and everything else colour 0, transparent, so the marble is the
screen's. Each has a palette of its own for each livery (the automatic
and manual colours of 255 entries over one index picture, as car
select's), which the code puts in CRAM with its chars. NAME95.BIN holds
them all, PICTURE_SECTORS apart (the picture of car n from 0, 0 DUSA's
car), and the code reads only the car's (GFS_Seek and GFS_Fread, as
patches/attract_load.s does): all of them would add 200 KB to the name
entry's load, and the disc's DAYTONA directory has room for one more file,
not eight.

patches/name_pictures.patch points the picture switch at the code (CODE_AT,
NAMED.BIN's tail): a car on DUSA's body (patches/car_choice.s: the secret
car always, the others with DUSA's body chosen, 002FC3A9) has its picture
read to FILE_AT and drawn with the gearbox's colours (002FC3A7); any other car,
or a picture that didn't arrive, goes to its own case.
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
TAG = 0x4E393550                        # 'N95P'
SWITCH_LITERAL = 0x06029C30             # patches/name_pictures.s
COLS, ROWS = 32, 12
W, H = 8 * COLS, 8 * ROWS
AT_X, AT_Y = 160, 336                   # the picture's place on the screen (cell 20, 42)
CAR_COLS, CAR_MID = (9, 247), 48        # where CCE's pictures put the car: its columns, its middle row
CAR_WIDTH = 80                          # at most this tall: DUSA's body is wider for its length than CCE's drawings
SHADOW, SHADOW_BLUR = (2, 2), 7         # the shadow's offset (down, right) and blur
MAX_CHARS = 378                         # VRAM 0x40000 on, as much as CCE's biggest picture takes
COLOURS = 255                           # palette entries 1-255; 0 is transparent
BG_CHARS, BG_MAP, BG_PALETTE = 0x26A4AC, 0x275EF0, 0x278570     # the screen's NBG0, 88 x 56 cells

# a picture: the tag, the chars' size, the map, the automatic and
# manual colours, the chars
MAP_OFF = 8
AT_OFF = MAP_OFF + 2 * COLS * ROWS
MT_OFF = AT_OFF + 2 * 256
CHARS_OFF = MT_OFF + 2 * 256

CODE = '''
.org {code_at:#x}
; NAME 06029C04, the name entry's picture switch, calls here for the car
; (r9-r14 as the switch's cases use them). -> r0 the car for its own
; case, or 11 (none) once ours is drawn; r1 11.
name_picture:
    sts.l  pr,@-r15
    mov.l  car_at,r0
    mov.b  @r0,r4
    mov    r4,r0
    cmp/eq #8,r0
    bt/s   dusa                 ; the secret car: DUSA's car always (file 0)
    mov    #0,r0
    mov    #7,r1
    cmp/hi r1,r4
    bt     cce                  ; the horses
    mov.l  choice_at,r1
    mov.b  @r1,r1
    tst    r1,r1
    bf     cce                  ; CCE's own car chosen
    mov    r4,r0
dusa:
    mov.l  r8,@-r15
    mov.l  r4,@-r15             ; the car, for its own case
    mov    r0,r8                ; its picture
    mov.l  busy_at,r1
    mov    #0,r0
    mov.b  r0,@r1               ; reading, as 060058B4
    mov.l  file_at,r1
    mov.l  r0,@r1               ; no tag until the picture is read
    mov.l  name_at,r4
    mov.l  gfs_id,r0
    jsr    @r0
    nop
    mov.l  gfs_open,r1
    jsr    @r1
    mov    r0,r4
    mov    r8,r5
    shll2  r5
    shll2  r5                   ; its first sector, PICTURE_SECTORS a picture
    mov    r0,r8                ; the file
    mov    r0,r4
    mov.l  gfs_seek,r0
    jsr    @r0
    mov    #0,r6
    mov    r8,r4
    mov    #{sectors},r5
    mov.l  file_at,r6
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
    mov.l  @r15+,r4
    mov.l  file_at,r1
    mov.l  @r1,r1
    mov.l  tag,r2
    cmp/eq r1,r2
    bf     loaded               ; not read: the car's own case
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
    mov    #11,r4               ; drawn: no case
loaded:
    mov.l  @r15+,r8
cce:
    lds.l  @r15+,pr
    mov    #11,r1
    rts
    mov    r4,r0

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
car_at:
    .long  0x002FC230
choice_at:
    .long  0x002FC3A9           ; player 1's body: 0 DUSA's
gear_at:
    .long  0x002FC3A7           ; player 1's gearbox: 0 automatic
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
set_colours:
    .long  0x0602CD64           ; NAME's colour copy (colours, CRAM entry, count)
file_at:
    .long  {file_at:#x}
tag:
    .long  {tag:#x}
name_at:
    .long  {name_at:#x}
'''


def background(named):
    """The screen's marble under the picture (NBG0 at the picture's place), (H, W, 3)."""
    pal = np.array([cp.rgb(c) for c in struct.unpack_from('>256H', named, BG_PALETTE - LOAD)])
    size = struct.unpack_from('>I', named, BG_MAP - 4 - LOAD)[0]
    chars = np.frombuffer(named, np.uint8, size, BG_CHARS - LOAD).reshape(-1, 8, 8)
    cells = struct.unpack_from(f'>{88 * 56}H', named, BG_MAP - LOAD)
    idx = np.zeros((H, W), int)
    for r in range(ROWS):
        for c in range(COLS):
            idx[8 * r:8 * r + 8, 8 * c:8 * c + 8] = chars[cells[(AT_Y // 8 + r) * 88 + AT_X // 8 + c] // 2]
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


def picture(poly, at_tex, mt_tex, marble):
    """A car's picture: one index picture, the automatic and manual colours."""
    at, cover = view(poly, at_tex)
    mt, _ = view(poly, mt_tex)
    dark = shadow(cover)
    under = marble * (1 - dark[..., None]) * (1 - cover[..., None])
    at, mt = at + under, mt + under
    shown = (cover > 0.02) | (dark > 0.03)
    c = cp.own_colours(at, mt, shown, n=COLOURS)
    at_pal, mt_pal = np.zeros((256, 3)), np.zeros((256, 3))
    at_pal[1:1 + len(c)], mt_pal[1:1 + len(c)] = c[:, :3], c[:, 3:]
    idx = cp.diffuse(at, mt, shown, np.zeros((H, W), int), at_pal, mt_pal, np.arange(1, 1 + len(c)))
    chars, cells = cp.pack(idx, at_pal, mt_pal, MAX_CHARS)
    colours = [struct.pack('>256H', *(cp.colour_word(v) for v in p)) for p in (at_pal, mt_pal)]
    out = struct.pack('>II', TAG, len(chars)) + cells + colours[0] + colours[1] + chars
    assert len(cells) == AT_OFF - MAP_OFF and out[CHARS_OFF:] == chars
    return out, len(chars) // 64


def build(dusa, cce, patched_name):
    """{file: data}: NAMED.BIN with the code, and NAME95.BIN."""
    name = open(patched_name, 'rb').read()
    assert struct.unpack_from('>I', name, SWITCH_LITERAL - 0x06028000)[0] == CODE_AT, \
        'NAME.BIN does not call the code: patches/name_pictures.patch'
    named = open(os.path.join(cce, 'DAYTONA', 'NAMED.BIN'), 'rb').read()
    assert LOAD + len(named) <= CODE_AT
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
    marble = background(named)
    pics, sizes = {}, {}
    pics[0], sizes[0] = picture(poly, cp.textures(texpl, False), cp.textures(texpl, True), marble)
    sources = liveries.Sources(dusa, cce)
    for number, paint in liveries.NINETY_FIVE.items():
        p = paint(sources)
        art = liveries.ninety_five_art(number, sources, cp.ART_SCALE)
        pics[number - 1], sizes[number - 1] = picture(
            poly, cp.paint_textures(p, False, art[0]), cp.paint_textures(p, True, art[1]), marble)
    assert sorted(pics) == list(range(8))
    assert PICTURE_SECTORS == 16                    # the code's two shll2
    out = {'NAME95.BIN': b''}
    for n in range(8):
        assert len(pics[n]) <= PICTURE_SECTORS * 2048
        out['NAME95.BIN'] += pics[n].ljust(PICTURE_SECTORS * 2048, b'\0')
    name_at = CODE_AT + 0x200
    (org, code), = sh2asm.assemble(CODE.format(code_at=CODE_AT, file_at=FILE_AT, tag=TAG, name_at=name_at,
                                               sectors=PICTURE_SECTORS, map_off=MAP_OFF, at_off=AT_OFF,
                                               mt_off=MT_OFF, chars_off=CHARS_OFF).splitlines())
    assert org == CODE_AT and CODE_AT + len(code) <= name_at
    tail = code + bytes(name_at - CODE_AT - len(code)) + b'NAME95.BIN'.ljust(16, b'\0')
    out['NAMED.BIN'] = named + bytes(CODE_AT - LOAD - len(named)) + tail
    assert LOAD + len(out['NAMED.BIN']) <= FILE_AT
    return out, sizes


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    out, sizes = build(dusa, cce, os.path.join(dst, 'DAYTONA', 'NAME.BIN'))
    for name, data in out.items():
        open(os.path.join(dst, 'DAYTONA', name), 'wb').write(data)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [f'DAYTONA/{n}' for n in out if f'DAYTONA/{n}' not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'name pictures: cars {sorted(sizes)}, chars {[sizes[n] for n in sorted(sizes)]} (room for {MAX_CHARS}); '
          f'NAMED.BIN {len(out["NAMED.BIN"])} bytes')


if __name__ == '__main__':
    main()
