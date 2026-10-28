"""Sheets of a car's candidate '95 colourings (tools/liveries.py,
CANDIDATES), each from above and from the front and rear three-quarters,
with CCE's own car under them, for the user to pick an automatic and a
manual pair from.

usage: livery_candidates.py <out dir> [car number from 1 ...]
  Writes <out dir>/cand_<n>_<name>.png for each car (all with candidates
  when none are given). Run from the repository root (extracted/dusa,
  extracted/cce).
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
import car_convert as cc  # noqa: E402
import car_sheet as cs  # noqa: E402
import liveries as lv  # noqa: E402

NAMES = {2: 'Gallop', 3: 'Max', 4: 'Phoenix', 5: 'Oriole', 6: 'Magic', 7: 'Wolf', 8: 'Balance'}


def main():
    out_dir = sys.argv[1]
    cars = [int(x) for x in sys.argv[2:]] or list(lv.DESIGNS)
    texpl = open('extracted/dusa/TEX_PL.BIN', 'rb').read()
    poly = open('extracted/dusa/POLYGON.BIN', 'rb').read()
    _, faces = cc.faces(poly, cc.BODY)
    base = cs.dusa_mesh('extracted/dusa', False)
    font = ImageFont.truetype('arial.ttf', 16)
    os.makedirs(out_dir, exist_ok=True)
    for car in cars:
        rows = []
        for p in lv.candidates(texpl, car):
            quads = []
            for (idx, _, px, tr, hf, vf, gl), (_, tid, _) in zip(base.quads, faces):
                quads.append((idx, p.rgb(tid, False)[:px.shape[0]], p.pixels[tid][:px.shape[0]], tr, hf, vf, gl))
            rows.append((p.name, cs.Mesh('', base.verts, quads, '')))
        rows.append((f"CCE's {NAMES[car]} (the inspiration)", cs.cce_mesh('extracted/cce', car, '')))
        cs.PX = 62
        img = Image.new('RGB', (150 + 2 * 360 + 40, 300 * len(rows)), cs.BG)
        d = ImageDraw.Draw(img)
        for r, (label, mesh) in enumerate(rows):
            y = r * 300
            d.text((10, y + 4), f'{r + 1}  {label}' if r < len(rows) - 1 else label, fill=(235, 235, 235),
                   font=font)
            img.paste(cs.render(mesh, 0, 90, 140, 270), (10, y + 26))
            img.paste(cs.render(mesh, 50, 25, 360, 260), (160, y + 30))
            img.paste(cs.render(mesh, 230, 25, 360, 260), (530, y + 30))
        dst = os.path.join(out_dir, f'cand_{car}_{NAMES[car].lower()}.png')
        img.save(dst)
        print('wrote', dst)


if __name__ == '__main__':
    main()
