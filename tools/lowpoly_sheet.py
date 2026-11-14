"""Two-player cars before and after model 11: each livery's 132-face body
(car_convert.build) beside its 49-face low-detail car (rebake.build_2p),
from above, both sides and both three-quarters, at one scale.

usage: lowpoly_sheet.py <dusa extracted dir> <cce extracted dir> <out png> [car ...]
  cars: 9 (the Gallop) and the '95 cars' numbers (default 9 2 3 4)
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import car_convert as cc  # noqa: E402
import car_pictures as cp  # noqa: E402
import car_sheet as cs  # noqa: E402
import liveries  # noqa: E402
import rebake  # noqa: E402


def mesh_of(mdl, tex, name, manual):
    """car_sheet.cce_mesh on bytes, with the manual set over tables 2-14 as
    patches/livery.s copies it."""
    sym, tsym = cs.symbols(mdl), cs.symbols(tex)
    tables, pixels = tsym[0xB9], tsym[0xBA]
    tex = bytearray(tex)
    if manual:
        tex[tables + 64:tables + 64 + 13 * 32] = tex[tables + 16 * 32:tables + 29 * 32]
    glass_entry = (sym[0x28] - 8) // 8
    h = sym[0x2C]
    nv, npoly, vo, po, _, _ = struct.unpack_from('>HHiiii', mdl, h)
    verts = np.array([struct.unpack_from('>3h', mdl, h + vo + 6 * i) for i in range(nv)], float) / 1024
    quads, p = [], h + po
    texels = set()
    for _ in range(npoly):
        attr, tw = struct.unpack_from('>HH', mdl, p)
        idx = [v // 16 for v in struct.unpack_from('>4H', mdl, p + 4)]
        p += 12
        e = tw // 8
        pmod, lut, src, size = struct.unpack_from('>4H', mdl, 8 + tw)
        w, hgt = (size >> 8) * 8, size & 0xFF
        texels.add((src, w * hgt))
        raw = tex[pixels + 8 * src:pixels + 8 * src + w * hgt // 2]
        px = np.array([v for b in raw for v in (b >> 4, b & 15)]).reshape(hgt, w)
        table = np.array([cp.rgb(struct.unpack_from('>H', tex, tables + 8 * lut + 2 * i)[0]) for i in range(16)])
        flip = (attr >> 12) & 3
        quads.append((idx, table[px], px, pmod == 0x1488, bool(flip & 1), bool(flip & 2), e == glass_entry))
    return cs.Mesh(name, verts * [-1, 1, 1], quads,
                   f'{nv} vertices, {npoly} polygons, {sum(t for _, t in texels) // 1000}k texels')


def main():
    dusa, cce, dst = sys.argv[1:4]
    cars = [int(c) for c in sys.argv[4:]] or [9, 2, 3, 4]
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
    orig = open(os.path.join(cce, 'DAYTONA', 'PLCAR21.MDL'), 'rb').read()
    mdl_size, tex_size = len(orig), os.path.getsize(os.path.join(cce, 'DAYTONA', 'PLCAR21.TEX'))
    count = max(struct.unpack_from('>H', orig, 0)[0], cc.ENTRIES)
    sources = liveries.Sources(dusa, cce)
    views = (('top', 0, 90, 90, 200), ('left', 0, 0, 200, 70), ('right', 180, 0, 200, 70),
             ('front 3/4', 50, 25, 190, 110), ('rear 3/4', 230, 25, 190, 110))
    rows = []
    for car in cars:
        paint = liveries.gallop(texpl) if car == 9 else liveries.NINETY_FIVE[car](sources)
        old = cc.build(poly, paint, (cc.BODY,), (0,) * 6, 'used', count, mdl_size, tex_size, False,
                       {cc.FLOOR_TEX: 4, cc.GRILLE_TEX: 2})
        new = rebake.build_2p(poly, paint, count, mdl_size, tex_size)
        print(paint.name, '| now:', old[2], '| model 11:', new[2])
        for manual in (False, True):
            for label, (mdl, tex, _) in (('132 faces', old), ('model 11', new)):
                rows.append(mesh_of(mdl, tex, f'{paint.name} {"MT" if manual else "AT"}, {label}', manual))
    pad, label_w = 8, 210
    width = label_w + sum(v[3] for v in views) + pad * len(views)
    height = len(rows) * (200 + pad) + pad
    sheet = Image.new('RGB', (width, height), cs.BG)
    draw = ImageDraw.Draw(sheet)
    try:
        font, small = ImageFont.truetype('arial.ttf', 14), ImageFont.truetype('arial.ttf', 12)
    except OSError:
        font = small = ImageFont.load_default()
    for r, mesh in enumerate(rows):
        y = pad + r * (200 + pad)
        draw.text((8, y + 8), mesh.name, fill=(235, 235, 235), font=font)
        draw.text((8, y + 30), mesh.note, fill=(170, 170, 170), font=small)
        x = label_w
        for name, az, el, w, h in views:
            sheet.paste(cs.render(mesh, az, el, w, h), (x, y + (200 - h) // 2))
            x += w + pad
    sheet.save(dst)
    print('wrote', dst)


if __name__ == '__main__':
    main()
