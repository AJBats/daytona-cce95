"""A sheet of the player cars side by side: DUSA's car in both liveries,
CCE's eight cars and its secret car 9, each from above, both sides, and
front and rear three-quarters, all at one scale, with their model counts.

usage: car_sheet.py <dusa extracted dir> <cce extracted dir> <out png>

Drawn as VDP1 draws them (docs/car_model.md): each polygon a distorted
sprite, its texture stretched over the four corners, colour 0 left out on
transparent ones, with a light from above added so the shape reads. CCE's
glass (the loader puts a shared texture in the model's glass entry) is
drawn dark. Orthographic, so the cars' proportions compare directly.
"""
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import car_convert as cc  # noqa: E402
import car_pictures as cp  # noqa: E402

CCE_CARS = ('Hornet', 'Gallop', 'Max', 'Phoenix', 'Oriole', 'Magic', 'Wolf', 'Balance', 'Daytona (secret)')
PX = 40                                 # pixels per world unit
SS = 3
LIGHT = np.array([-0.3, 1.0, 0.4]) / np.linalg.norm([-0.3, 1.0, 0.4])
GLASS = np.array([0.08, 0.1, 0.14])
BG = (40, 40, 44)
# (name, azimuth, elevation): azimuth 0 = from the car's left, 90 = from the front
VIEWS = (('top', 0, 90), ('left', 0, 0), ('right', 180, 0), ('front 3/4', 50, 25), ('rear 3/4', 230, 25))


class Mesh:
    """Vertices (n x 3, y up, nose at -z, x mirrored to a right-handed frame)
    and quads: (4 vertex indices, colours h x w x 3, pixels h x w, transparent,
    h flip, v flip, glass)."""
    def __init__(self, name, verts, quads, note):
        self.name, self.verts, self.quads, self.note = name, verts, quads, note


def dusa_mesh(dusa, manual):
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    texpl = open(os.path.join(dusa, 'TEX_PL.BIN'), 'rb').read()
    vo, nv, fo, nf = cc.BODY
    verts = np.array([struct.unpack_from('>iii', poly, vo + 12 * i) for i in range(nv)], float) / 65536
    tex = cp.textures(texpl, manual)
    quads = []
    for i in range(nf):
        f = struct.unpack_from('>iiiHHHHHH', poly, fo + 24 * i)
        attr, tid, idx = f[3], f[4], f[5:9]
        col, px = tex[tid]
        if tid == cc.WINDOW_TEX:
            col, px = col[:40], px[:40]
        quads.append((idx, col, px, bool(attr & 0x10), bool(attr & 0x80), bool(attr & 0x40), tid == cc.WINDOW_TEX))
    texels = sum(w * h for _, w, h, _ in cc.TEXTURES.values())
    return Mesh(f"DUSA's car, {'manual' if manual else 'automatic'}", verts * [-1, 1, 1], quads,
                f'{nv} vertices, {nf} polygons, {len(cc.TEXTURES)} textures, {texels // 1000}k texels')


def symbols(data):
    count = struct.unpack_from('>I', data, len(data) - 4)[0]
    at = len(data) - 4 - 8 * count
    return {sid: at + off for sid, off in (struct.unpack_from('>Ii', data, at + 8 * i) for i in range(count))}


# CCE triangle layouts (attribute bits 9-11, 06045C3C): the sprite's four corners
TRIANGLE = {0: (0, 1, 2, 2), 1: (0, 0, 1, 2), 2: (0, 1, 1, 2), 3: (0, 1, 2, 2), 4: (0, 1, 2, 0)}


def cce_mesh(cce, n, name):
    mdl = open(os.path.join(cce, 'DAYTONA', f'PLCAR{n:02d}.MDL'), 'rb').read()
    tex = open(os.path.join(cce, 'DAYTONA', f'PLCAR{n:02d}.TEX'), 'rb').read()
    sym, tsym = symbols(mdl), symbols(tex)
    tables, pixels = tsym[0xB9], tsym[0xBA]
    glass_entry = (sym[0x28] - 8) // 8
    h = sym[0x2C]
    nv, npoly, vo, po, _, _ = struct.unpack_from('>HHiiii', mdl, h)
    verts = np.array([struct.unpack_from('>3h', mdl, h + vo + 6 * i) for i in range(nv)], float) / 1024
    quads, entries, p = [], set(), h + po
    for _ in range(npoly):
        attr, tw = struct.unpack_from('>HH', mdl, p)
        k = 3 if attr & 1 else 4
        idx = [v // 16 for v in struct.unpack_from(f'>{k}H', mdl, p + 4)]
        p += 4 + 2 * k
        if k == 3:
            idx = [idx[c] for c in TRIANGLE[(attr >> 9) & 7]]
        e = tw // 8
        entries.add(e)
        pmod, lut, src, size = struct.unpack_from('>4H', mdl, 8 + tw)
        w, hgt = (size >> 8) * 8, size & 0xFF
        raw = tex[pixels + 8 * src:pixels + 8 * src + w * hgt // 2]
        px = np.array([v for b in raw for v in (b >> 4, b & 15)]).reshape(hgt, w)
        table = np.array([cp.rgb(struct.unpack_from('>H', tex, tables + 8 * lut + 2 * i)[0]) for i in range(16)])
        flip = (attr >> 12) & 3
        quads.append((idx, table[px], px, pmod == 0x1488, bool(flip & 1), bool(flip & 2), e == glass_entry))
    sizes = {struct.unpack_from('>HH', mdl, 8 + 8 * e + 4) for e in entries - {glass_entry}}
    texels = sum((size >> 8) * 8 * (size & 0xFF) for _, size in sizes)
    return Mesh(name, verts * [-1, 1, 1], quads,
                f'{nv} vertices, {npoly} polygons, {len(sizes)} textures, {texels // 1000}k texels')


def render(mesh, azimuth, elevation, width, height, lit_from=LIGHT):
    """The mesh seen from (azimuth, elevation) degrees, orthographic, PX per
    unit, centred, SS times the size averaged down; lit_from None draws the
    textures' own colours."""
    az, el = math.radians(azimuth), math.radians(elevation)
    # camera direction toward the car; azimuth 0 from -x (the car's left), 90 from -z (its front)
    back = np.array([-math.cos(az) * math.cos(el), math.sin(el), -math.sin(az) * math.cos(el)])
    up_hint = np.array([0, 0, -1.0]) if elevation > 89 else np.array([0, 1.0, 0])
    right = np.cross(up_hint, back)
    right /= np.linalg.norm(right)
    up = np.cross(back, right)
    sw, sh = width * SS, height * SS
    img = np.zeros((sh, sw, 3))
    img[:] = np.array(BG) / 255
    depth = np.full((sh, sw), -np.inf)
    cover = np.zeros((sh, sw))
    centre = (mesh.verts.max(0) + mesh.verts.min(0)) / 2
    v = mesh.verts - centre
    sx = sw / 2 + PX * SS * (v @ right)
    sy = sh / 2 - PX * SS * (v @ up)
    sz = v @ back
    n = 8
    uu, vv = np.meshgrid(np.linspace(0, 1, n + 1), np.linspace(0, 1, n + 1))
    w4 = np.stack([(1 - uu) * (1 - vv), uu * (1 - vv), uu * vv, (1 - uu) * vv], -1)
    for idx, col, px, transparent, hflip, vflip, glass in mesh.quads:
        corners = mesh.verts[list(idx)]
        normal = np.cross(corners[2] - corners[0], corners[3] - corners[1])
        if not normal.any():
            normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
        nn = np.linalg.norm(normal) or 1
        lit = 1.0 if lit_from is None else 0.75 + 0.4 * abs(float(normal @ lit_from)) / nn
        qx, qy, qz = (w4 @ q[list(idx)] for q in (sx, sy, sz))
        th, tw = px.shape
        for j in range(n):
            for k in range(n):
                for tri in (((j, k), (j, k + 1), (j + 1, k + 1)), ((j, k), (j + 1, k + 1), (j + 1, k))):
                    xs, ys, zs = (np.array([q[t] for t in tri]) for q in (qx, qy, qz))
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
                    t = l0 * vs[0] + l1 * vs[1] + l2 * vs[2]
                    if hflip:
                        u = 1 - u
                    if vflip:
                        t = 1 - t
                    tx = np.clip((u * tw).astype(int), 0, tw - 1)
                    ty = np.clip((t * th).astype(int), 0, th - 1)
                    if transparent:
                        m &= px[ty, tx] != 0
                    win = depth[y0:y1 + 1, x0:x1 + 1]
                    m &= z > win - 0.02
                    win[m] = np.maximum(win[m], z[m])
                    c = GLASS * lit if glass else col[ty, tx] * lit
                    img[y0:y1 + 1, x0:x1 + 1][m] = np.clip(c[m] if not glass else c, 0, 1)
                    cover[y0:y1 + 1, x0:x1 + 1][m] = 1
    out = (img.reshape(height, SS, width, SS, 3).mean(axis=(1, 3)) * 255).astype(np.uint8)
    return Image.fromarray(out)


def main():
    dusa, cce, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    meshes = [dusa_mesh(dusa, False), dusa_mesh(dusa, True)]
    meshes += [cce_mesh(cce, n + 1, name) for n, name in enumerate(CCE_CARS)]
    cell = {'top': (110, 230), 'left': (230, 80), 'right': (230, 80), 'front 3/4': (220, 130), 'rear 3/4': (220, 130)}
    label_w, pad = 230, 10
    row_h = max(h for _, h in cell.values()) + pad
    width = label_w + sum(w for w, _ in cell.values()) + pad * len(cell)
    sheet = Image.new('RGB', (width, 30 + row_h * len(meshes)), BG)
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('arial.ttf', 15)
        small = ImageFont.truetype('arial.ttf', 12)
    except OSError:
        font = small = ImageFont.load_default()
    x = label_w
    for name, _, _ in VIEWS:
        draw.text((x + 4, 8), name, fill=(200, 200, 200), font=small)
        x += cell[name][0] + pad
    for r, mesh in enumerate(meshes):
        y = 30 + r * row_h
        lo, hi = mesh.verts.min(0), mesh.verts.max(0)
        draw.text((10, y + 10), mesh.name, fill=(240, 240, 240), font=font)
        lines = mesh.note.split(', ')
        lines.append(f'{hi[2] - lo[2]:.2f} long, {hi[0] - lo[0]:.2f} wide, {hi[1] - lo[1]:.2f} high')
        for i, line in enumerate(lines):
            draw.text((10, y + 34 + 16 * i), line, fill=(170, 170, 170), font=small)
        x = label_w
        for name, az, el in VIEWS:
            w, h = cell[name]
            sheet.paste(render(mesh, az, el, w, h), (x, y))
            x += w + pad
        print(mesh.name, '|', mesh.note)
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    sheet.save(dst)
    print('wrote', dst)


if __name__ == '__main__':
    main()
