"""Car select's picture of DUSA's car, rendered from its model in both
liveries, for the Hornet (car 1) and the secret car 9, and the Hornet's
choice of DUSA's car or CCE's (docs/car_select.md).

usage: car_pictures.py <dusa extracted dir> <cce extracted dir> <out dir>
  Writes the car-select screens' files (ARC, TA, TWO_P, LINK and
  XBANDISE.DAT) under <out dir>/DAYTONA and lists them in PATCHED.txt.

Car select draws a car's picture on VDP2 NBG3: 13 x 27 cells of 8 x 8
256-colour chars, one 256-colour palette shared by all eleven pictures
(the screen file's +0x71BEA). The screen file is loaded at 0x250000 and
holds each picture as its chars, then a header (the chars' size) and the
13 x 27 map (char number x 2). Every car-select screen file has them at the
same place.

DUSA's car is drawn top-down, nose up, as long and where CCE's pictures
have their cars, so its halo fades out inside the picture: its model
(POLYGON.BIN model 0) with its textures and the 16-colour tables of each
gearbox, lit from above, in CCE's dark halo (a palette ramp each screen
sets from its own background to black).
The automatic and manual pictures share one set of palette indices: the
manual one is the automatic one's chars through a 256-byte remap, so one
picture's chars serve both. They take the place of the secret car's
picture (Sega's drawing of DUSA's #41), with the remap and the code that
copies them after the chars; patches/car_pictures.s points car select's
picture switch at that code for cars 1 and 9, calls it again whenever a
player's gearbox cursor moves, and gives it left and right on the car
list, which flip the Hornet, and the cars with a '95 livery
(tools/liveries.py), between DUSA's body and CCE's own car (CCE's own
picture, where it was; patches/car_choice.s loads the car). A '95 car's
picture is CCE's either way for now.
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

CAMERA = (14.0, 0.15)                   # distance above the car, lean toward the rear
CAR_ROWS, CAR_X = (15, 204), 50         # where CCE's pictures put the car: its rows, its middle
SHADOW = (2, 2)                         # the halo's offset, down and right, as CCE's
LIGHT = (-0.4, 1.0, 0.5)
BRIGHT, GLASS = 1.2, 0.3                # overall light; the windows' tint
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

; SLCT 0602FA06, car select's picture case for cars 1 and 9, jumps here
; (player at @(8,r15)). DUSA's car: the chars for the player's gearbox,
; then the map as the other cases draw it (0602FACA, the rest of the
; picture routine). The Hornet with CCE's car chosen: its own case.
picture:
    mov.b  @(8,r15),r0
    bsr    is_dusa
    mov    r0,r4
    bt     dusa_picture
    mov.l  hornet_case,r0
    jmp    @r0
    nop
dusa_picture:
    bsr    chars
    nop
    mov.l  r12,@-r15
    mov.l  r14,@-r15
    mov.l  r9,@-r15
    mov    #13,r2
    mov.l  r2,@-r15
    mov.l  map_at,r4
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
    bsr    chars
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

; T = player r4's car is DUSA's: the secret car, or the Hornet with DUSA's
; car chosen. Uses r0, r1.
is_dusa:
    mov.l  cars,r1
    add    r4,r1
    mov.b  @r1,r0
    cmp/eq #8,r0
    bt     is_done
    tst    r0,r0
    bf     is_done
    mov.l  choices,r1
    add    r4,r1
    mov.b  @r1,r0
    tst    r0,r0
is_done:
    rts
    nop

; Player r4's picture chars into its VRAM when its car is DUSA's, through
; the remap while its gearbox cursor is on manual.
chars:
    sts.l  pr,@-r15
    bsr    is_dusa
    nop
    lds.l  @r15+,pr
    bf     chars_done
    mov.l  gears,r1
    add    r4,r1
    mov.b  @r1,r7
    mov.l  vram_1p,r5
    tst    r4,r4
    bt     have_vram
    mov.l  vram_2p,r5
have_vram:
    mov.l  chars_at,r6
    mov.w  n_words,r3
    tst    r7,r7
    bt     automatic
    mova   remap,r0
manual:
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
    bf/s   manual
    add    #2,r5
    rts
    nop
automatic:
    mov.w  @r6+,r1
    mov.w  r1,@r5
    dt     r3
    bf/s   automatic
    add    #2,r5
chars_done:
    rts
    nop
n_words:
    .word  {n_words}
k_up:
    .word  0x1000
k_sides:
    .word  0xC000
.align 4
map_at:
    .long  {map_at:#x}
map_draw:
    .long  0x0602FACA
hornet_case:
    .long  0x0602F952       ; case 0 as CCE had it: the Hornet's own picture
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
    .long  0x002FC3A9       ; 0 DUSA's car, 1 CCE's (patches/car_choice.s)
vram_1p:
    .long  0x25E10000
vram_2p:
    .long  0x25E18000
chars_at:
    .long  {chars_at:#x}
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


def render(poly, texpl, manual):
    """The car at SS times the picture's size: (colour, coverage)."""
    vo, nv, fo, nf = cc.BODY
    verts = np.array([struct.unpack_from('>iii', poly, vo + 12 * i) for i in range(nv)], float) / 65536
    tex = textures(texpl, manual)
    sw, sh = W * SS, H * SS
    img = np.zeros((sh, sw, 3))
    depth_buf = np.full((sh, sw), np.inf)
    cover = np.zeros((sh, sw))
    dist, lean = CAMERA
    light = np.array(LIGHT) / np.linalg.norm(LIGHT)

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
    for i in range(nf):
        f = struct.unpack_from('>iiiHHHHHH', poly, fo + 24 * i)
        normal, attr, tid, idx = np.array(f[:3], float), f[3], f[4], f[5:9]
        col, px = tex[tid]
        if tid == cc.WINDOW_TEX:
            col, px = col[:40], px[:40]
        th, tw = px.shape
        a, b, c, d = (verts[k] for k in idx)
        p = (a * ((1 - uu) * (1 - vv))[..., None] + b * (uu * (1 - vv))[..., None]
             + c * (uu * vv)[..., None] + d * ((1 - uu) * vv)[..., None])
        sx, sy, sz = project(p)
        lit = BRIGHT * (0.7 + 0.45 * max(0.0, float(normal @ light) / (np.linalg.norm(normal) or 1)))
        if tid == cc.WINDOW_TEX:
            lit *= GLASS
        for j in range(n):
            for k in range(n):
                for tri in (((j, k), (j, k + 1), (j + 1, k + 1)), ((j, k), (j + 1, k + 1), (j + 1, k))):
                    xs, ys, zs = (np.array([q[t] for t in tri]) for q in (sx, sy, sz))
                    us, vs = (np.array([q[t] for t in tri]) for q in (uu, vv))
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
                    img[y0:y1 + 1, x0:x1 + 1][m] = col[ty, tx][m] * lit
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


def pack(idx, remap, pal):
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
        look = np.concatenate([pal[table], pal[remap[table]]], -1).reshape(len(table), -1)
        cost = ((look[:, None] - look[None]) ** 2).sum(-1)
        cost[np.tril_indices(len(table))] = np.inf
        cost[:, 0] = cost[0] = np.inf              # char 0 stays the blank one
        keep, drop = np.unravel_index(np.argmin(cost), cost.shape)
        cells[cells == drop] = keep
        cells[cells > drop] -= 1
        table = np.delete(table, drop, 0)
    return table.astype(np.uint8).tobytes(), struct.pack(f'>{len(cells)}H', *(2 * cells))


def build(dusa, cce):
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
    screens = {s: open(os.path.join(cce, 'DAYTONA', s), 'rb').read() for s in SCREENS}
    arc = screens['ARC.DAT']
    pal = np.array([rgb(struct.unpack_from('>H', arc, PALETTE + 2 * i)[0]) for i in range(256)])
    at, car, halo = finish(*render(poly, texpl, False), pal)
    mt, _, _ = finish(*render(poly, texpl, True), pal)
    idx, remap = quantize(at, mt, car, halo, pal)
    chars, cells = pack(idx, remap, pal)
    flip_cars = ''.join(f'    cmp/eq #{n - 1},r0\n    bt     can_flip\n' for n in liveries.NINETY_FIVE)
    (org, code), = sh2asm.assemble(CODE.format(code_at=CODE_AT, n_words=len(chars) // 2, flip_cars=flip_cars,
                                               map_at=MAP_AT, chars_at=CHARS_AT).splitlines())
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
    return out, idx, remap, pal, len(chars) // 64


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    out, _, _, _, n_chars = build(dusa, cce)
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    for name, data in out.items():
        open(os.path.join(dst, 'DAYTONA', name), 'wb').write(data)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [f'DAYTONA/{n}' for n in out if f'DAYTONA/{n}' not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'car pictures: DUSA\'s car in both liveries, {n_chars} chars (room for {MAX_CHARS})')


if __name__ == '__main__':
    main()
