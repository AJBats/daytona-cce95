"""A sheet of DUSA's drone liveries: every rival car's paint on Three Seven,
drawn from above, from the left and from the front three-quarters.

usage: drone_sheet.py <dusa extracted dir> <vdp1 vram dump> <wram high dump> <out png>

The dumps come from DUSA in a race or its attract on Three Seven (any frame
once the course is loaded; docs/car_model.md, "DUSA's drones"). DUSA
registers its car textures in banks at the course's load: a face's texture
id picks a slot through the bank's table (060684EC, 64 words a bank), and
the slot (06063F64, 8 bytes: 0, VRAM / 8, CMDSIZE, colour table / 8 from
VDP1 0xC800) gives the pixels and the 16-colour table. Bank 0 is the
player's car, banks 3-41 the drones, each its own colour tables and some
textures of its own (numbers, sponsor panels). The near drone is model 6.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import car_pictures as cp  # noqa: E402
import car_sheet as cs  # noqa: E402

BANKS = 0x060684EC
SLOTS = 0x06063F64
TABLES_AT = 0x1900 * 8
DRONES = range(3, 42)
MODEL = 6
MODELS_V, MODELS_F, COUNTS_V, COUNTS_F = 0x0606212C, 0x060620D8, 0x060621D8, 0x06062180
APROG_AT, POLYGON_AT = 0x06003000, 0x060F8000
WINDOW_TEX = 10
VIEWS = (('top', 0, 90), ('left', 0, 0), ('front 3/4', 50, 25))


def drone_mesh(aprog, poly, vram, wram, bank):
    def word(a):
        return struct.unpack_from('>I', aprog, a - APROG_AT)[0]
    vo, fo = word(MODELS_V + 4 * MODEL) - POLYGON_AT, word(MODELS_F + 4 * MODEL) - POLYGON_AT
    nv, nf = word(COUNTS_V + 4 * MODEL), word(COUNTS_F + 4 * MODEL)
    verts = np.array([struct.unpack_from('>iii', poly, vo + 12 * i) for i in range(nv)], float) / 65536
    table = struct.unpack_from('>64H', wram, BANKS - 0x06000000 + 128 * bank)
    quads = []
    for i in range(nf):
        f = struct.unpack_from('>iiiHHHHHH', poly, fo + 24 * i)
        attr, tid, idx = f[3], f[4], f[5:9]
        _, addr, size, lut = struct.unpack_from('>4H', wram, SLOTS - 0x06000000 + 8 * table[tid])
        w, h = (size >> 8) * 8, size & 0xFF
        if tid == WINDOW_TEX:
            h = 40
        raw = vram[8 * addr:8 * addr + w * h // 2]
        px = np.array([v for b in raw for v in (b >> 4, b & 15)]).reshape(h, w)
        colours = np.array([cp.rgb(struct.unpack_from('>H', vram, TABLES_AT + 8 * lut + 2 * k)[0]) for k in range(16)])
        quads.append((idx, colours[px], px, bool(attr & 0x10), bool(attr & 0x80), bool(attr & 0x40), tid == WINDOW_TEX))
    return cs.Mesh(f'bank {bank}', verts * [-1, 1, 1], quads, '')


def main():
    dusa, vram_path, wram_path, dst = sys.argv[1:5]
    aprog = open(os.path.join(dusa, 'APROG.BIN'), 'rb').read()
    poly = open(os.path.join(dusa, 'POLYGON.BIN'), 'rb').read()
    vram, wram = open(vram_path, 'rb').read(), open(wram_path, 'rb').read()
    cell = {'top': (90, 200), 'left': (200, 70), 'front 3/4': (190, 110)}
    pad, cols = 8, 3
    block_w = sum(w for w, _ in cell.values()) + pad * len(cell)
    block_h = 200 + 22
    rows = -(-len(DRONES) // cols)
    sheet = Image.new('RGB', (cols * block_w + pad, rows * block_h + pad), cs.BG)
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('arial.ttf', 13)
    except OSError:
        font = ImageFont.load_default()
    for n, bank in enumerate(DRONES):
        mesh = drone_mesh(aprog, poly, vram, wram, bank)
        x0, y0 = pad + (n % cols) * block_w, pad + (n // cols) * block_h
        draw.text((x0, y0), f'drone {n + 1} (bank {bank})', fill=(230, 230, 230), font=font)
        x = x0
        for name, az, el in VIEWS:
            w, h = cell[name]
            sheet.paste(cs.render(mesh, az, el, w, h), (x, y0 + 18))
            x += w + pad
        print('drone', n + 1, 'bank', bank)
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    sheet.save(dst)
    print('wrote', dst)


if __name__ == '__main__':
    main()
