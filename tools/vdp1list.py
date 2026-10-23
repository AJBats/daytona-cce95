"""List a VDP1 command table from a VDP1 VRAM dump.

usage: vdp1list.py <vdp1_vram.bin> [x0 y0 x1 y1]
  Walks the command list from address 0 and prints one line per command;
  with a box, only textured/polygon commands with a vertex inside it.
"""
import struct
import sys

TYPES = {0: 'sprite', 1: 'scaled', 2: 'distorted', 4: 'polygon', 5: 'polyline', 6: 'line',
         8: 'userclip', 9: 'sysclip', 10: 'local'}
MODES = {0: '4bpp bank', 1: '4bpp LUT', 2: '8bpp 64', 3: '8bpp 128', 4: '8bpp 256', 5: 'RGB'}


def main():
    v = open(sys.argv[1], 'rb').read()
    box = [int(a) for a in sys.argv[2:6]] if len(sys.argv) > 5 else None
    a, stack, n = 0, [], 0
    while n < 4000:
        n += 1
        ctrl, link, pmod, colr, srca, size = struct.unpack_from('>6H', v, a)
        xy = struct.unpack_from('>8h', v, a + 12)
        grda = struct.unpack_from('>H', v, a + 28)[0]
        if ctrl & 0x8000:
            break
        jump = (ctrl >> 12) & 3          # next, assign, call, return (bit 14: skip)
        typ = ctrl & 0xF
        if not ctrl & 0x4000:  # not skipped
            pts = list(zip(xy[0::2], xy[1::2]))
            inside = box is None or any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for x, y in pts)
            if inside and (box is None or typ in (0, 1, 2, 4)):
                mode = (pmod >> 3) & 7
                print(f'{a:05X} {TYPES.get(typ, typ):9s} pmod {pmod:04X} ({MODES.get(mode, mode)}'
                      f'{" gouraud" if pmod & 4 else ""}{" half" if pmod & 3 == 3 else ""}) colr {colr:04X} '
                      f'srca {srca * 8:05X} size {size >> 8 << 3}x{size & 0xFF} grd {grda * 8:05X} '
                      f'pts {pts if typ in (2, 4) else pts[:2]} dir {(ctrl >> 4) & 3}')
        nxt = a + 32
        if jump == 1:
            nxt = link * 8
        elif jump == 2:
            stack.append(a + 32)
            nxt = link * 8
        elif jump == 3:
            nxt = stack.pop() if stack else a + 32
        a = nxt


if __name__ == '__main__':
    main()
