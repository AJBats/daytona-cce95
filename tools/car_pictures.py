"""Car select's pictures of the cars on DUSA's body, rendered from its
model in both liveries: the Gallop for the Hornet (car 1) and the secret
car 9, and each '95 car's own (tools/liveries.py); and the choice of DUSA's
body or CCE's car (docs/car_select.md, docs/liveries.md).

usage: car_pictures.py <dusa extracted dir> <cce extracted dir> <out dir>
  Writes the car-select screens' files (ARC, TA, TWO_P, LINK and
  XBANDISE.DAT) and the '95 pictures (PICS95.BIN) under <out dir>/DAYTONA
  and lists them in PATCHED.txt.

Car select draws a car's picture on VDP2 NBG3: 13 x 27 cells of 8 x 8
256-colour chars, one 256-colour palette shared by all eleven pictures
(the screen file's +0x71BEA). The screen file is loaded at 0x250000 and
holds each picture as its chars, then a header (the chars' size) and the
13 x 27 map (char number x 2). Every car-select screen file has them at the
same place.

A car on DUSA's body is drawn top-down, nose up, as long and where CCE's
pictures have their cars, so its halo fades out inside the picture: its
model (POLYGON.BIN model 0) with its textures and the 16-colour tables of
each gearbox, shaded smooth as CCE's pictures are (render), in CCE's dark
halo (a palette ramp each screen sets from its own background to black).

CCE's palette was made for CCE's eight cars, and ours, put in its colours,
came out dithered. So each of our pictures has colours of its own (OWN,
entries 15-255 of the pictures' palette, CRAM 0x600): one index picture,
an automatic and a manual colour for each entry. With one player only one
picture shows, and the code puts its colours in the palette, and CCE's
back for CCE's own pictures. With two, both pictures share the palette,
so ours keep CCE's colours: their chars go through a remap to the nearest.
The palette can't grow instead: car select fills all 1024 colours of
colour RAM mode 0, and in mode 1 (2048) a screen in high resolution, as
car select is, can't blend palette colours (ST-058, table 12.1), which its
screens do.

The Gallop's picture in CCE's colours, the manual one through a remap,
takes the place of the secret car's picture (Sega's drawing of DUSA's #41),
with the code that copies the pictures after its chars: the fallback for
when PICS95.BIN isn't there. The pictures in colours of their own (the
Gallop's and the '95 cars') don't fit in the screen files, so they go in
PICS95.BIN, which patches/car_pictures.s loads after each car-select
screen into work RAM free in the menus (PICS_AT).

patches/car_pictures.s points car select's picture switch at the code
for cars 1-9, calls it again whenever a player's gearbox cursor moves, and
gives it left and right on the car list. The code draws a car on DUSA's
body from its record (in PICS95.BIN when its tags show it all loaded, else
the Gallop's in the screen file) and sends any other car to its own case, as CCE
had it; left and right flip the Hornet and the '95 cars between DUSA's body
and CCE's car (patches/car_choice.s loads the car).
"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
import car_convert as cc  # noqa: E402
import liveries  # noqa: E402
import sh2asm  # noqa: E402
from dusa_lzss import decompress  # noqa: E402

SCREENS = ('ARC.DAT', 'TA.DAT', 'TWO_P.DAT', 'LINK.DAT', 'XBANDISE.DAT')
LOADED_AT = 0x250000
PALETTE = 0x71BEA
HALO = range(2, 15)                     # palette ramp from the screen's background to black
COLS, ROWS = 13, 27
W, H, SS = 8 * COLS, 8 * ROWS, 4        # picture size and supersampling
# the secret car's picture's place: chars, then the code and remap, then
# the map where its map was (nothing reads its header now)
CHARS_AT, CODE_AT, MAP_AT = 0x2B521E, 0x2BA000, 0x2BA7A4
SLOT_END = MAP_AT + 2 * COLS * ROWS
MAX_CHARS = (CODE_AT - CHARS_AT) // 64
# the '95 cars' pictures, loaded with each car-select screen into work RAM
# that is free in the menus (patches/car_pictures.s)
PICS_AT, PICS_END, PICS_TAG = 0x060B0000, 0x060ED000, 0x50494353   # 'PICS'
SWITCH, SWITCH_BASE = 0x0602F900, 0x0602F8E8    # the picture switch's words (braf base), as CCE had them
GALLOP_RECORD = 8                       # the pictures file's record of DUSA's own livery

CAMERA = (14.0, 0.15)                   # distance above the car, lean toward the rear
CAR_ROWS, CAR_X = (15, 204), 50         # where CCE's pictures put the car: its rows, its middle
SHADOW = (2, 2)                         # the halo's offset, down and right, as CCE's
# Lit as CCE's pictures are, from the front left (the picture's top left)
# and above, with a highlight; a car's x is the picture's right to left.
LIGHT = (0.5, 1.0, -0.6)
AMBIENT, DIFFUSE, SPECULAR, SHINE = 0.42, 0.6, 0.7, 60
FACING = 0.25                           # how much a surface seen edge-on darkens
CREASE = math.radians(65)               # faces meeting at less than this share their corners' normals
GLASS_FRONT, GLASS_BACK, GLASS_DARK = 0.6, 0.2, 0.04
GLASS_TINT, GLASS_SHINE = (0.95, 0.97, 1.0), 0.8
DITHER = 0.6

CODE = '''
.org {code_at:#x}
    bra    picture
    nop
    bra    gear
    nop
    bra    input_1p
    nop
    bra    input_2p
    nop

; SLCT 0602FA06, car select's picture case for cars 1-9, jumps here
; (player at @(8,r15)). A car on DUSA's body: the chars for the player's
; gearbox, then the map as the other cases draw it (0602FACA, the rest of
; the picture routine). Any other: the car's own case, as CCE had it.
picture:
    mov.b  @(8,r15),r0
    bsr    source
    mov    r0,r4
    tst    r0,r0
    bf     dusa_picture
    bsr    cce_colours_1p
    nop
    mov.l  cars,r1
    add    r4,r1
    mov.b  @r1,r0
    shll2  r0
    mov    r0,r2
    mova   cases,r0
    mov.l  @(r0,r2),r0
    jmp    @r0
    nop
dusa_picture:
    mov.l  r0,@-r15
    bsr    copy_chars
    mov    r0,r3
    mov.l  @r15+,r3
    mov.l  r12,@-r15
    mov.l  r14,@-r15
    mov.l  r9,@-r15
    mov    #13,r2
    mov.l  r2,@-r15
    mov.l  @(4,r3),r4       ; the record's map
    mov    r11,r5
    mov    r13,r6
    mov    r10,r7
    mov.l  map_draw,r0
    jmp    @r0
    nop

; SLCT 0602FAE6, the gearbox cursor's draw (r4 the player), jumps here
; after each move: its first steps, the chars again, then back to it.
gear:
    mov.l  r14,@-r15
    mov.l  r13,@-r15
    mov.l  r12,@-r15
    mov.l  r11,@-r15
    exts.b r4,r12
    sts.l  pr,@-r15
    bsr    chars_for
    nop
    lds.l  @r15+,pr
    mov    r12,r4
    mov.l  gear_back,r0
    jmp    @r0
    nop

; SLCT 0602EE2C and 0602F1D2, each player's car list input (r13 the sound
; call), jump here: left or right on the Hornet flips that player's choice
; of car, else up and down go on as before.
input_1p:
    mov.l  @(4,r15),r2
    mov.w  @r2,r5
    extu.w r5,r5
    bsr    flip
    mov    #0,r4
    bt     flipped_1p
    mov.w  k_up,r2
    tst    r2,r5
    bt     not_up_1p
    mov.l  up_1p,r0
    jmp    @r0
    nop
not_up_1p:
    mov.l  down_1p,r0
    jmp    @r0
    nop
flipped_1p:
    mov.l  done_1p,r0
    jmp    @r0
    nop
input_2p:
    mov.l  @r15,r2
    mov.w  @r2,r5
    extu.w r5,r5
    bsr    flip
    mov    #1,r4
    bt     flipped_2p
    mov.l  pad_2p,r4        ; as the handler had it
    mov.w  k_up,r2
    tst    r2,r5
    bt     not_up_2p
    mov.l  up_2p,r0
    jmp    @r0
    nop
not_up_2p:
    mov.l  down_2p,r0
    jmp    @r0
    nop
flipped_2p:
    mov.l  done_2p,r0
    jmp    @r0
    nop

; T = left or right (r5 the buttons pressed) on player r4's car with a
; choice of body (the Hornet, the '95 liveries): its choice flipped, the
; cursor's sound, and its picture drawn again.
flip:
    mov.w  k_sides,r0
    tst    r0,r5
    bt     no_flip
    mov.l  cars,r1
    add    r4,r1
    mov.b  @r1,r0
    tst    r0,r0
    bt     can_flip
{flip_cars}    bra    no_flip
    nop
can_flip:
    sts.l  pr,@-r15
    mov.l  r4,@-r15
    mov.l  choices,r1
    add    r4,r1
    mov.b  @r1,r0
    xor    #1,r0
    mov.b  r0,@r1
    mov    #1,r6
    mov    #1,r5
    jsr    @r13
    mov    #0,r4
    mov.l  @r15,r4
    mov    #27,r6
    mov    #73,r5           ; player 2's column
    tst    r4,r4
    bf     redraw
    mov    #46,r5           ; one player's
    mov.l  mode,r0
    mov.b  @r0,r0
    cmp/eq #12,r0
    bt     two_players
    cmp/eq #13,r0
    bf     redraw
two_players:
    mov    #43,r5           ; player 1's in two-player
redraw:
    mov.l  picture_draw,r0
    jsr    @r0
    nop
    mov.l  @r15+,r4
    lds.l  @r15+,pr
    rts
    sett
no_flip:
    rts
    clrt

; Player r4's picture on DUSA's body: r0 = its record (below), or 0 for
; CCE's own picture. The secret car, and with DUSA's body chosen the
; Hornet, have the Gallop's: the pictures file's record 8, or failing that
; the one in this file; a '95 car has its own in the pictures file
; (PICS95.BIN, at {pics_at:#x} since the screen's load, patches/
; car_pictures.s). Uses r0-r3.
source:
    sts.l  pr,@-r15
    mov.l  cars,r1
    add    r4,r1
    mov.b  @r1,r0
    cmp/eq #8,r0
    bt     gallop
    mov    r0,r2
    mov.l  choices,r1
    add    r4,r1
    mov.b  @r1,r0
    tst    r0,r0
    bf     no_source
    tst    r2,r2
    bt     gallop
    bsr    lookup
    nop
    bra    source_done
    nop
gallop:
    bsr    lookup
    mov    #8,r2
    tst    r0,r0
    bf     source_done
    mova   gallop_record,r0
    bra    source_done
    nop
no_source:
    mov    #0,r0
source_done:
    lds.l  @r15+,pr
    rts
    nop

; Record r2 of the pictures file -> r0, or 0 when it has none or isn't all
; loaded: its tag at both ends. Uses r0-r3.
lookup:
    mov.l  pics,r1
    mov.l  @r1,r0
    mov.l  tag,r3
    cmp/eq r3,r0
    bf     lookup_none
    shll2  r2
    add    r1,r2
    mov.l  @(4,r2),r0
    tst    r0,r0
    bt     lookup_done
    mov.l  @(48,r1),r2      ; the end tag's address
    mov.l  @r2,r2
    cmp/eq r3,r2
    bt     lookup_done
lookup_none:
    mov    #0,r0
lookup_done:
    rts
    nop

; Player r4's picture chars into its VRAM when its car is on DUSA's body.
chars_for:
    sts.l  pr,@-r15
    bsr    source
    nop
    tst    r0,r0
    bt     chars_none
    bsr    copy_chars
    mov    r0,r3
chars_none:
    lds.l  @r15+,pr
    rts
    nop

; A record: the chars' size in words, the map, the chars; for each gearbox
; (automatic, manual) its own colours (entries 15-255 of the pictures'
; palette, CRAM 0x600) or 0, and its chars' remap to CCE's colours or 0.
; Record r3's chars into player r4's VRAM for the player's gearbox. With one
; player, the picture's own colours go in the palette (CCE's when it has
; none); with two, both pictures share CCE's colours, so its chars go
; through the remap. Uses r0-r7.
copy_chars:
    mov.l  gears,r1
    add    r4,r1
    mov.b  @r1,r7
    shll2  r7
    mov    r3,r0
    add    r7,r0
    mov.l  @(12,r0),r6      ; the gearbox's own colours
    mov.l  @(20,r0),r7      ; its remap
    mov.l  mode,r0
    mov.b  @r0,r0
    cmp/eq #12,r0
    bt     to_vram
    cmp/eq #13,r0
    bt     to_vram
    tst    r6,r6
    bf     own_colours
    mov.l  cce_colours,r6
    bra    set_colours
    nop
own_colours:
    mov    #0,r7
set_colours:
    mov.l  colours_at,r5
    mov    #-15,r1
    extu.b r1,r1            ; 241 entries
colour:
    mov.w  @r6+,r2
    mov.w  r2,@r5
    dt     r1
    bf/s   colour
    add    #2,r5
to_vram:
    mov.l  vram_1p,r5
    tst    r4,r4
    bt     have_vram
    mov.l  vram_2p,r5
have_vram:
    mov.l  @(8,r3),r6       ; chars
    mov    r7,r0            ; remap
    mov.l  @r3,r3           ; words
    tst    r0,r0
    bt     straight
remapped:
    mov.w  @r6+,r1
    extu.b r1,r2
    shlr8  r1
    extu.b r1,r1
    mov.b  @(r0,r1),r1
    mov.b  @(r0,r2),r2
    shll8  r1
    extu.b r2,r2
    or     r2,r1
    mov.w  r1,@r5
    dt     r3
    bf/s   remapped
    add    #2,r5
    rts
    nop
straight:
    mov.w  @r6+,r1
    mov.w  r1,@r5
    dt     r3
    bf/s   straight
    add    #2,r5
    rts
    nop

; With one player, CCE's colours back in the pictures' palette, for CCE's
; own picture. Uses r0-r3.
cce_colours_1p:
    mov.l  mode,r0
    mov.b  @r0,r0
    cmp/eq #12,r0
    bt     cce_done
    cmp/eq #13,r0
    bt     cce_done
    mov.l  cce_colours,r1
    mov.l  colours_at,r2
    mov    #-15,r3
    extu.b r3,r3
cce_colour:
    mov.w  @r1+,r0
    mov.w  r0,@r2
    dt     r3
    bf/s   cce_colour
    add    #2,r2
cce_done:
    rts
    nop
k_up:
    .word  0x1000
k_sides:
    .word  0xC000
.align 4
map_draw:
    .long  0x0602FACA
gear_back:
    .long  0x0602FAF0
up_1p:
    .long  0x0602EE38
down_1p:
    .long  0x0602EEB8
done_1p:
    .long  0x0602F198
up_2p:
    .long  0x0602F1DE
down_2p:
    .long  0x0602F210
done_2p:
    .long  0x0602F508
pad_2p:
    .long  0x060072D0       ; player 2's pad
picture_draw:
    .long  0x0602F83E
mode:
    .long  0x06042369       ; 12 or 13 in two-player modes
cars:
    .long  0x002FC230
gears:
    .long  0x002FC3A7
choices:
    .long  0x002FC3A9       ; 0 DUSA's body, 1 CCE's car (patches/car_choice.s)
vram_1p:
    .long  0x25E10000
vram_2p:
    .long  0x25E18000
colours_at:
    .long  0x25F0061E       ; the pictures' palette (CRAM 0x600), entry 15
cce_colours:
    .long  {cce_colours:#x}       ; CCE's, in the screen file, entry 15
pics:
    .long  {pics_at:#x}
tag:
    .long  {tag:#x}
; each car's own case, as CCE had it, for CCE's picture
cases:
{cases}
gallop_record:
    .long  {n_words}
    .long  {map_at:#x}
    .long  {chars_at:#x}
    .long  0
    .long  0
    .long  0
    .long  remap
remap:
'''


def rgb(c):
    return np.array([c & 31, (c >> 5) & 31, (c >> 10) & 31], float) / 31


def textures(texpl, manual):
    """Texture id -> (colours, pixels) for the automatic or manual livery."""
    def table(n):
        off = 0x100 + 32 * (n - 2) if manual and 2 <= n <= 7 else 32 * n
        return [rgb(struct.unpack_from('>H', texpl, off + 2 * i)[0]) for i in range(16)]
    out = {}
    for tid, (off, w, h, tn) in cc.TEXTURES.items():
        n = 80 * 80 // 2 if tid == cc.WINDOW_TEX else w * h // 2
        data, _ = decompress(texpl, off, n)
        px = np.array([v for b in data[:w * h // 2] for v in (b >> 4, b & 15)]).reshape(h, w)
        out[tid] = (np.array(table(tn))[px], px)
    return out


def paint_textures(paint, manual):
    """A paint's textures (tools/liveries.py) as textures() gives DUSA's."""
    return {tid: (paint.rgb(tid, manual), paint.pixels[tid]) for tid in cc.TEXTURES}


def corner_normals(verts, faces):
    """Each face's four corner normals (outward), smoothed over the faces
    that meet at a corner's place within CREASE of the face's own."""
    flat = []
    for normal, _, _, idx in faces:
        a, b, c, d = (verts[k] for k in idx)
        area = np.linalg.norm(np.cross(c - a, d - b)) / 2
        flat.append((-normal / (np.linalg.norm(normal) or 1), area))   # DUSA's normals point in
    at = {}
    for i, (_, _, _, idx) in enumerate(faces):
        for k in set(idx):
            at.setdefault(tuple(np.round(verts[k], 3)), []).append(i)
    out = []
    for i, (_, _, _, idx) in enumerate(faces):
        own = flat[i][0]
        corners = []
        for k in idx:
            s = sum(flat[j][0] * flat[j][1] for j in at[tuple(np.round(verts[k], 3))]
                    if flat[j][0] @ own > math.cos(CREASE))
            corners.append(s / (np.linalg.norm(s) or 1))
        out.append(corners)
    return out


def shade(nrm, light, half, eye):
    """Diffuse and specular light for unit normals nrm (..., 3), the sides
    the camera sees edge-on darker, as on CCE's pictures."""
    diffuse = np.clip(nrm @ light, 0, None)
    specular = np.clip(nrm @ half, 0, None) ** SHINE
    facing = 1 - FACING * (1 - np.clip(nrm @ eye, 0, 1))
    return (AMBIENT + DIFFUSE * diffuse) * facing, SPECULAR * specular


def glass_tone(p, outward):
    """The windows as CCE's pictures draw them: the windscreen light grey at
    its front edge, dark at the roof; the back and side windows dark."""
    y = p[..., 1]
    t = (y - y.min()) / ((y.max() - y.min()) or 1)
    if outward[2] < -0.3:                   # windscreen: its front edge is its low edge
        return GLASS_FRONT * (1 - t) ** 1.5 + GLASS_DARK
    if outward[2] > 0.3:                    # back window: a little light at the roof
        return GLASS_BACK * t + GLASS_DARK
    return np.full_like(y, GLASS_DARK)


def render(poly, tex):
    """The car with textures tex (texture id -> (colours, pixels)) at SS
    times the picture's size: (colour, coverage). Shaded smooth, as CCE's
    pictures are: normals interpolated across each face from its corners
    (corner_normals), lit from the front left and above with a highlight."""
    vo, nv, fo, nf = cc.BODY
    verts = np.array([struct.unpack_from('>iii', poly, vo + 12 * i) for i in range(nv)], float) / 65536
    faces = []
    for i in range(nf):
        f = struct.unpack_from('>iiiHHHHHH', poly, fo + 24 * i)
        faces.append((np.array(f[:3], float), f[3], f[4], f[5:9]))
    normals = corner_normals(verts, faces)
    sw, sh = W * SS, H * SS
    img = np.zeros((sh, sw, 3))
    depth_buf = np.full((sh, sw), np.inf)
    cover = np.zeros((sh, sw))
    dist, lean = CAMERA
    light = np.array(LIGHT) / np.linalg.norm(LIGHT)
    eye = np.array([0.0, math.cos(lean), math.sin(lean)])
    half = (light + eye) / np.linalg.norm(light + eye)

    def view(p):
        # model y up, nose at -z; the camera above, leaning back by `lean`
        x, y, z = p[..., 0], p[..., 1], p[..., 2]
        zt = z * math.cos(lean) - y * math.sin(lean)
        d = dist - (z * math.sin(lean) + y * math.cos(lean))
        return -x / d, zt / d, d

    # scaled and placed so the car spans CAR_ROWS, centred on CAR_X
    vx, vy, _ = view(verts)
    scale = (CAR_ROWS[1] - CAR_ROWS[0]) * SS / (vy.max() - vy.min())
    ox = CAR_X * SS - scale * (vx.max() + vx.min()) / 2
    oy = CAR_ROWS[0] * SS - scale * vy.min()

    def project(p):
        x, y, d = view(p)
        return ox + scale * x, oy + scale * y, d

    n = 16                                  # each face split n x n
    uu, vv = np.meshgrid(np.linspace(0, 1, n + 1), np.linspace(0, 1, n + 1))
    def bilinear(a, b, c, d):
        return (a * ((1 - uu) * (1 - vv))[..., None] + b * (uu * (1 - vv))[..., None]
                + c * (uu * vv)[..., None] + d * ((1 - uu) * vv)[..., None])

    for i, (normal, attr, tid, idx) in enumerate(faces):
        col, px = tex[tid]
        glass = tid == cc.WINDOW_TEX
        if glass:
            col, px = col[:40], px[:40]
        th, tw = px.shape
        p = bilinear(*(verts[k] for k in idx))
        nrm = bilinear(*normals[i])
        tone = glass_tone(p, -normal / np.linalg.norm(normal)) if glass else None
        sx, sy, sz = project(p)
        for j in range(n):
            for k in range(n):
                for tri in (((j, k), (j, k + 1), (j + 1, k + 1)), ((j, k), (j + 1, k + 1), (j + 1, k))):
                    xs, ys, zs = (np.array([q[t] for t in tri]) for q in (sx, sy, sz))
                    us, vs = (np.array([q[t] for t in tri]) for q in (uu, vv))
                    ns = np.array([nrm[t] for t in tri])
                    x0, x1 = max(0, math.floor(xs.min())), min(sw - 1, math.ceil(xs.max()))
                    y0, y1 = max(0, math.floor(ys.min())), min(sh - 1, math.ceil(ys.max()))
                    det = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
                    if x1 < x0 or y1 < y0 or abs(det) < 1e-9:
                        continue
                    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                    l1 = ((gx - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (gy - ys[0])) / det
                    l2 = ((xs[1] - xs[0]) * (gy - ys[0]) - (gx - xs[0]) * (ys[1] - ys[0])) / det
                    l0 = 1 - l1 - l2
                    m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
                    z = l0 * zs[0] + l1 * zs[1] + l2 * zs[2]
                    u = l0 * us[0] + l1 * us[1] + l2 * us[2]
                    v = l0 * vs[0] + l1 * vs[1] + l2 * vs[2]
                    if attr & 0x80:             # DUSA's flips: 0x80 horizontal, 0x40 vertical
                        u = 1 - u
                    if attr & 0x40:
                        v = 1 - v
                    tx = np.clip((u * tw).astype(int), 0, tw - 1)
                    ty = np.clip((v * th).astype(int), 0, th - 1)
                    if attr & 0x10:             # transparent: colour 0 not drawn
                        m &= px[ty, tx] != 0
                    window = depth_buf[y0:y1 + 1, x0:x1 + 1]
                    m &= z < window
                    window[m] = z[m]
                    nn = l0[..., None] * ns[0] + l1[..., None] * ns[1] + l2[..., None] * ns[2]
                    nn /= np.linalg.norm(nn, axis=-1, keepdims=True) + 1e-9
                    diffuse, specular = shade(nn, light, half, eye)
                    if glass:
                        ts = np.array([tone[t] for t in tri])
                        base = (l0 * ts[0] + l1 * ts[1] + l2 * ts[2])[..., None] * np.array(GLASS_TINT)
                        colour = base + GLASS_SHINE * specular[..., None]
                    else:
                        colour = col[ty, tx] * diffuse[..., None] + specular[..., None]
                    img[y0:y1 + 1, x0:x1 + 1][m] = colour[m]
                    cover[y0:y1 + 1, x0:x1 + 1][m] = 1
    return img, cover


def finish(img, cover, pal):
    """Down to the picture's size: (colour over the halo, car drawn, halo index)."""
    c = img.reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
    a = cover.reshape(H, SS, W, SS).mean(axis=(1, 3))
    dy, dx = SHADOW
    shadow = np.zeros_like(a)
    shadow[dy:, dx:] = a[:H - dy, :W - dx]
    blur = Image.fromarray((shadow * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
    shade = np.clip(np.asarray(blur, float) / 255 * 2.2, 0, 1)
    halo = np.where(shade > 0.08, HALO[0] + np.round(shade * (len(HALO) - 1)).astype(int), 0)
    return c + pal[halo] * (1 - a[..., None]), a > 0.02, halo


def quantize(at, mt, car, halo, pal, iterations=8):
    """One index picture and a remap: the automatic picture's indices, and
    for each the manual livery's (k-means over the pairs, the automatic
    colours fixed to the palette, then error diffusion on both). Around the
    car, the halo's own ramp index; on it, any colour but the ramp's, which
    each car-select screen sets to its own background (its darkest, black,
    is the same everywhere)."""
    usable = np.array([i for i in range(1, 256) if i not in HALO[:-1]])
    choices = pal[usable]
    remap = np.arange(256)

    def refit(idx):
        for i in usable:
            sel = (idx == i) & car
            if sel.any() and i != HALO[-1]:
                remap[i] = usable[int(np.argmin(((choices - mt[sel].mean(0)) ** 2).sum(1)))]

    refit(usable[np.argmin(((at[..., None, :] - choices) ** 2).sum(-1), axis=-1)])
    for it in range(iterations + 1):
        last = it == iterations
        wa, wm = at.copy(), mt.copy()
        idx = np.where(car, 0, halo)
        paired = pal[remap[usable]]
        for y in range(H):
            for x in range(W):
                if not car[y, x]:
                    continue
                k = int(np.argmin(((choices - wa[y, x]) ** 2).sum(1) + ((paired - wm[y, x]) ** 2).sum(1)))
                idx[y, x] = usable[k]
                if last:
                    ea, em = (wa[y, x] - choices[k]) * DITHER, (wm[y, x] - paired[k]) * DITHER
                    for dx, dy, f in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                        if 0 <= x + dx < W and y + dy < H and car[y + dy, x + dx]:
                            wa[y + dy, x + dx] += ea * f
                            wm[y + dy, x + dx] += em * f
        if not last:
            refit(idx)
    return idx, remap


OWN = np.arange(15, 256)                 # the entries a picture's own colours take


def own_colours(at, mt, car, iterations=16):
    """Colours of a picture's own for both liveries: an automatic and a
    manual colour for each of OWN's entries (k-means over the pairs of
    colours of the car's pixels), so one index picture serves both. ->
    (n, 6): each entry's automatic and manual colour, on the Saturn's 5 bits."""
    pts = np.clip(np.concatenate([at[car], mt[car]], 1), 0, 1)
    uniq = np.unique(np.round(pts * 31), axis=0) / 31
    rng = np.random.default_rng(0)
    c = uniq[rng.choice(len(uniq), min(len(OWN), len(uniq)), replace=False)]
    for _ in range(iterations):
        lab = np.argmin(((pts[:, None] - c[None]) ** 2).sum(-1), 1)
        for j in range(len(c)):
            if (lab == j).any():
                c[j] = pts[lab == j].mean(0)
    return np.round(c * 31) / 31


def diffuse(at, mt, car, halo, at_pal, mt_pal, usable):
    """The index picture for palettes at_pal and mt_pal (both liveries the
    same indices): error diffusion on both at once over entries usable;
    around the car, the halo's ramp."""
    idx = np.where(car, 0, halo)
    wa, wm = at.copy(), mt.copy()
    ca, cm = at_pal[usable], mt_pal[usable]
    for y in range(H):
        for x in range(W):
            if not car[y, x]:
                continue
            k = int(np.argmin(((ca - wa[y, x]) ** 2).sum(1) + ((cm - wm[y, x]) ** 2).sum(1)))
            idx[y, x] = usable[k]
            ea, em = (wa[y, x] - ca[k]) * DITHER, (wm[y, x] - cm[k]) * DITHER
            for dx, dy, f in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                if 0 <= x + dx < W and y + dy < H and car[y + dy, x + dx]:
                    wa[y + dy, x + dx] += ea * f
                    wm[y + dy, x + dx] += em * f
    return idx


def pack(idx, at_pal, mt_pal):
    """Chars (char 0 blank) and the map, as car select keeps them; past
    MAX_CHARS, the two chars nearest alike in both liveries become one."""
    chars, cells = {bytes(64): 0}, []
    for cy in range(ROWS):
        for cx in range(COLS):
            c = idx[8 * cy:8 * cy + 8, 8 * cx:8 * cx + 8].astype(np.uint8).tobytes()
            cells.append(chars.setdefault(c, len(chars)))
    table = np.array([np.frombuffer(c, np.uint8) for c in sorted(chars, key=chars.get)], int)
    cells = np.array(cells)
    while len(table) > MAX_CHARS:
        look = np.concatenate([at_pal[table], mt_pal[table]], -1).reshape(len(table), -1)
        cost = ((look[:, None] - look[None]) ** 2).sum(-1)
        cost[np.tril_indices(len(table))] = np.inf
        cost[:, 0] = cost[0] = np.inf              # char 0 stays the blank one
        keep, drop = np.unravel_index(np.argmin(cost), cost.shape)
        cells[cells == drop] = keep
        cells[cells > drop] -= 1
        table = np.delete(table, drop, 0)
    return table.astype(np.uint8).tobytes(), struct.pack(f'>{len(cells)}H', *(2 * cells))


class Picture:
    """A car's picture in both liveries: its chars, map and index picture;
    and either colours of its own (at, mt: 256 colours each, its own at
    OWN), each with a remap to CCE's colours for two players, or CCE's
    colours, the manual livery's through a remap (mt_remap only)."""
    def __init__(self, chars, cells, idx, at=None, mt=None, at_remap=None, mt_remap=None):
        self.chars, self.cells, self.idx = chars, cells, idx
        self.at, self.mt, self.at_remap, self.mt_remap = at, mt, at_remap, mt_remap


def nearest(colours, pal):
    """Each colour's nearest entry of CCE's palette, the halo's ramp left out."""
    usable = np.array([i for i in range(1, 256) if i not in HALO[:-1]])
    return usable[np.argmin(((colours[:, None] - pal[usable][None]) ** 2).sum(-1), 1)]


def picture(poly, at_tex, mt_tex, pal, own=True):
    """A car's picture in both liveries (Picture): in colours of its own, or
    (own=False) in CCE's."""
    at, car, halo = finish(*render(poly, at_tex), pal)
    mt, _, _ = finish(*render(poly, mt_tex), pal)
    if not own:
        idx, remap = quantize(at, mt, car, halo, pal)
        chars, cells = pack(idx, pal, pal[remap])
        return Picture(chars, cells, idx, mt_remap=remap)
    c = own_colours(at, mt, car)
    at_pal, mt_pal = pal.copy(), pal.copy()
    at_pal[OWN[:len(c)]], mt_pal[OWN[:len(c)]] = c[:, :3], c[:, 3:]
    idx = diffuse(at, mt, car, halo, at_pal, mt_pal, np.concatenate([[HALO[-1]], OWN[:len(c)]]))
    chars, cells = pack(idx, at_pal, mt_pal)
    at_remap, mt_remap = np.arange(256), np.arange(256)
    at_remap[OWN], mt_remap[OWN] = nearest(at_pal[OWN], pal), nearest(mt_pal[OWN], pal)
    return Picture(chars, cells, idx, at_pal, mt_pal, at_remap, mt_remap)


def colour_word(c):
    """A colour as a CRAM word: 5 bits each, red lowest."""
    r, g, b = (int(round(v * 31)) for v in np.clip(c, 0, 1))
    return r | g << 5 | b << 10


def pictures_file(pictures):
    """PICS95.BIN, loaded at PICS_AT: the tag; a record's address for each
    car from 0 (0 for none; GALLOP_RECORD the Gallop's, for the Hornet on
    DUSA's body and the secret car); the end tag's address; the records
    (the code's copy_chars), each with its map, colours, remaps and chars
    after it; the end tag."""
    head = 4 + 4 * 11 + 4
    body = bytearray()
    at = {}
    for car, pic in sorted(pictures.items()):
        rec = PICS_AT + head + len(body)
        cells = pic.cells + bytes(-len(pic.cells) % 4)
        colours = [struct.pack(f'>{len(OWN)}H', *(colour_word(c) for c in p[OWN])) for p in (pic.at, pic.mt)]
        colours = [c + bytes(-len(c) % 4) for c in colours]
        map_at = rec + 28
        at_colours = map_at + len(cells)
        mt_colours = at_colours + len(colours[0])
        at_remap = mt_colours + len(colours[1])
        mt_remap = at_remap + 256
        chars_at = mt_remap + 256
        at[car] = rec
        body += struct.pack('>7I', len(pic.chars) // 2, map_at, chars_at, at_colours, mt_colours, at_remap,
                            mt_remap)
        body += cells + colours[0] + colours[1] + bytes(pic.at_remap.astype(np.uint8))
        body += bytes(pic.mt_remap.astype(np.uint8)) + pic.chars
    end = PICS_AT + head + len(body)
    out = struct.pack('>I', PICS_TAG) + b''.join(struct.pack('>I', at.get(car, 0)) for car in range(11))
    out += struct.pack('>I', end) + body + struct.pack('>I', PICS_TAG)
    assert PICS_AT + len(out) <= PICS_END, f'the pictures run to 0x{PICS_AT + len(out):X}'
    return bytes(out)


def build(dusa, cce):
    """The car-select screen files with the Gallop's picture and the code,
    and the '95 cars' pictures file. -> ({file: data}, the Gallop's chars)"""
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
    slct = open(os.path.join(cce, 'DAYTONA', 'SLCT.BIN'), 'rb').read()
    screens = {s: open(os.path.join(cce, 'DAYTONA', s), 'rb').read() for s in SCREENS}
    arc = screens['ARC.DAT']
    pal = np.array([rgb(struct.unpack_from('>H', arc, PALETTE + 2 * i)[0]) for i in range(256)])
    gallop = textures(texpl, False), textures(texpl, True)
    shared = picture(poly, *gallop, pal, own=False)
    chars, cells, remap = shared.chars, shared.cells, shared.mt_remap
    pictures = {GALLOP_RECORD: picture(poly, *gallop, pal)}
    sources = liveries.Sources(dusa, cce)
    for number, paint in liveries.NINETY_FIVE.items():
        p = paint(sources)
        pictures[number - 1] = picture(poly, paint_textures(p, False), paint_textures(p, True), pal)
    flip_cars = ''.join(f'    cmp/eq #{n - 1},r0\n    bt     can_flip\n' for n in liveries.NINETY_FIVE)
    words = struct.unpack_from('>11H', slct, SWITCH - 0x06028000)
    cases = ''.join(f'    .long  {SWITCH_BASE + w:#x}\n' for w in words)
    (org, code), = sh2asm.assemble(CODE.format(code_at=CODE_AT, n_words=len(chars) // 2, flip_cars=flip_cars,
                                               map_at=MAP_AT, chars_at=CHARS_AT, cases=cases,
                                               pics_at=PICS_AT, tag=PICS_TAG,
                                               cce_colours=LOADED_AT + PALETTE + 2 * OWN[0]).splitlines())
    code += bytes(remap.astype(np.uint8))
    assert CODE_AT + len(code) <= MAP_AT, f'code and remap run to 0x{CODE_AT + len(code):X}'
    slot = bytearray(SLOT_END - CHARS_AT)
    slot[:len(chars)] = chars
    slot[CODE_AT - CHARS_AT:CODE_AT - CHARS_AT + len(code)] = code
    slot[MAP_AT - CHARS_AT:] = cells
    out = {}
    for name, data in screens.items():
        assert data[CHARS_AT - LOADED_AT:SLOT_END - LOADED_AT] == arc[CHARS_AT - LOADED_AT:SLOT_END - LOADED_AT]
        out[name] = data[:CHARS_AT - LOADED_AT] + bytes(slot) + data[SLOT_END - LOADED_AT:]
    out['PICS95.BIN'] = pictures_file(pictures)
    return out, len(chars) // 64


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    out, n_chars = build(dusa, cce)
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    for name, data in out.items():
        open(os.path.join(dst, 'DAYTONA', name), 'wb').write(data)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [f'DAYTONA/{n}' for n in out if f'DAYTONA/{n}' not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'car pictures: DUSA\'s car in both liveries, {n_chars} chars (room for {MAX_CHARS}); '
          f'PICS95.BIN {len(out["PICS95.BIN"])} bytes for cars {sorted(liveries.NINETY_FIVE)}')


if __name__ == '__main__':
    main()
