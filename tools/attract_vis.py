"""Record which course blocks show on screen, frame by frame, through DUSA's demos in CCE95's attract.

usage: attract_vis.py <out.npz>
  Boots the built CCE95 disc (tools/soundlab.py's debugger) with no input,
  twice at once, and samples every frame of each of DUSA's three demos
  (Three Seven, Dinosaur Canyon, Seaside Galaxy): one run the course view
  matrix (0605450C) and the blocks CCE draws (0605173C), the other
  src/attract.c's frame count (its frames, which the camera follows), and
  reads every course block's model. Then, per frame the camera was set at,
  the blocks owning a pixel of a z-buffer (half the screen's resolution) of
  every block's polygons as CCE draws them (below), or with a polygon too
  small to cover one that isn't hidden. Writes per course c: c<c>_frames
  (the attract's frame count at each camera), c<c>_vis (those frames x
  blocks, 1 on screen), c<c>_depth (the depth of each block's nearest point
  in front, in units), c<c>_eye (the camera's position) and c<c>_cce (the
  blocks CCE draws: record from a disc built without the lists,
  COURSE_LISTS=0, as make attract-vis does). tools/build_attract.py makes
  src/attract.c's block lists from it (docs/attract.md, "Course blocks").

The camera comes from DUSA's recording and src/attract.c only: record
again when either changes. Its time is the VBlank count, so a Saturn
dropping frames sees the same camera at a frame count as here.

CCE's course drawing (06045958, its transform 06046520): a block's model
holds 16-bit vertices (world x 32) and polygons (attribute, a word, three
or four vertex offsets into the transformed buffer (16 bytes each), three
more words when attribute bit 5 is set; bit 0: a triangle). The view
matrix rows are x, y, depth (16.16, rotation x 32); 06045958 scales the
rotation by 64, so camera space is 16.16 world units. A polygon with
attribute bit 4 is one-sided: 06045C9C skips it when (x1 - x0)(y2 - y1) +
(x2 - x1)(y0 - y1) >= 0 on screen. One whose depth reaches the render
context's far distance (+4, 319 units) is skipped, and one crossing its
near distance (+0, 0.5) is cut there (the road under the camera). Screen:
352 x 224, centre (176, 135), lens 160 (0605788C).
"""
import os
import shutil
import struct
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import soundlab  # noqa: E402

# boot frames a second or so before each demo's cut (Three Seven, Dinosaur
# Canyon, Seaside Galaxy: 2175, 6802, 11530 here; DEMOTTL.BIN's size moves
# them), and the frames to sample from there, through the demo; before the
# cut src/attract.c's frame count is -1
START = [2100, 6730, 11460]
LENGTH = [2900, 2900, 2720]
FLAGS, MATRIX, VIEW_END = 0x0605173C, 0x0605450C, 0x0605453C
BLOCK_MODELS = 0x06051738
SECTOR_MAP = 0x06054934     # the course's sector map (CSn_BLK.BIN): a block per sector record
PLACES = 0x0604EDC8         # where a placed block of kind k (its record's byte 3) goes: k - 1 x 12 bytes
CONTEXT = 0x06057800
LENS = 0x0605788C
W, H, CX, CY, RES = 352, 224, 176, 135, 2


def frames_at():
    """src/attract.c's frames, from the built blob's symbols."""
    nm = os.path.join(os.path.dirname(__file__), 'sh-gcc', 'bin', 'sh2eb-elf-nm')
    elf = os.path.join(os.path.dirname(__file__), '..', 'build', 'attract', 'attract.elf')
    for line in subprocess.run([nm, elf], capture_output=True, text=True, check=True).stdout.splitlines():
        if line.endswith(' _frames'):
            return int(line.split()[0], 16)
    sys.exit(f'no _frames in {elf}')


def run(pass_name):
    """One pass over the three demos: per course, 'view' gives (samples, models, near, far, lens,
    blocks), 'frames' the frame counts."""
    home = soundlab.mednafen_home()
    proc, ipc = soundlab.start('cce', dict(os.environ, MEDNAFEN_HOME=home, MEDNAFEN_ALLOWMULTI='1'))
    m = soundlab.Mednafen(ipc)
    out = []
    try:
        m.send('deterministic', 'ok deterministic')
        for c, (start, n) in enumerate(zip(START, LENGTH)):
            m.send(f'run_to_frame {start}', 'done run_to_frame', 900)
            path = os.path.join(ipc, f'{pass_name}{c}.bin')
            if pass_name == 'view':
                m.send(f'mem_sample {FLAGS:08X} {VIEW_END - FLAGS:X} {n} {path}', 'done mem_sample', 3600)
                tab = struct.unpack('>I', m.read(BLOCK_MODELS, 4))[0]
                models = {}
                blk = struct.unpack('>I', m.read(SECTOR_MAP, 4))[0]
                records, grid = struct.unpack('>2I', m.read(blk, 8))
                count = (grid - records) // 48
                kinds = m.read(blk + records, 48 * count)[3::48]
                for b, p in enumerate(struct.unpack('>%dI' % count, m.read(tab, 4 * count))):
                    if 0x06000000 <= p < 0x06100000:
                        nv, npoly, voff, poff = struct.unpack('>HHII', m.read(p, 12))
                        if 0 < nv < 2048 and 0 < npoly < 2048 and voff == 0x14 and poff < 0x8000:
                            at = (0, 0, 0)
                            if kinds[b]:            # placed: 0602A2A4 moves it by its kind's offset
                                at = struct.unpack('>3i', m.read(PLACES + 12 * (kinds[b] - 1), 12))
                            models[b] = (m.read(p, poff + 18 * npoly), at)
                ctx = m.read(CONTEXT, 8)
                near_d, far_d = (v / 65536 for v in struct.unpack('>2i', ctx))
                lens = struct.unpack('>h', m.read(LENS, 2))[0]
                raw = np.frombuffer(open(path, 'rb').read(), np.uint8).reshape(n, VIEW_END - FLAGS)
                out.append((raw, models, near_d, far_d, lens, count))
            else:
                m.send(f'mem_sample {frames_at():08X} 4 {n} {path}', 'done mem_sample', 3600)
                out.append(np.frombuffer(open(path, 'rb').read(), '>i4').astype(np.int64))
            print(f'{pass_name}: course {c} sampled from frame {start}', flush=True)
    finally:
        m.send('quit', 'quit', 10)
        proc.wait(timeout=30)
        shutil.rmtree(ipc, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    return out


def parse(model, at):
    """A block's vertices (world x 32, its placement added) and polygons."""
    nv, npoly, voff, poff = struct.unpack_from('>HHII', model, 0)
    v = np.array(struct.unpack_from('>%dh' % (3 * nv), model, voff), np.float64).reshape(-1, 3)
    v += np.array(at) / 2048.0
    polys, o = [], poff
    for _ in range(npoly):
        attr = struct.unpack_from('>H', model, o)[0]
        o += 4
        k = 3 if attr & 1 else 4
        polys.append((attr, [i // 16 for i in struct.unpack_from('>%dH' % k, model, o)]))
        o += 2 * k + (6 if attr & 32 else 0)
    return v, polys


def eye(mat):
    """The camera's position in the world (units) from its view matrix."""
    m = np.array(mat, np.float64).reshape(3, 4)
    r = m[:, :3] / (32 * 65536.0)
    return -r.T @ (m[:, 3] / 65536.0)


def camera(mat, v):
    out = []
    for r in range(3):
        a, b, c, d = (float(x) for x in mat[4 * r:4 * r + 4])
        out.append(((a * v[:, 0] + b * v[:, 1] + c * v[:, 2]) / 1024.0 + d) / 65536.0)
    return out


def raster(tri, inv_z, zbuf, idbuf, ident):
    """One triangle (z-buffer pixels) into the buffers, nearer pixels only; False if it covers no pixel centre."""
    xs, ys = tri[:, 0], tri[:, 1]
    x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), zbuf.shape[1] - 1)
    y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), zbuf.shape[0] - 1)
    area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
    if x0 > x1 or y0 > y1 or abs(area) < 1e-9:
        return False
    px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    w0 = ((xs[1] - px) * (ys[2] - py) - (xs[2] - px) * (ys[1] - py)) / area
    w1 = ((xs[2] - px) * (ys[0] - py) - (xs[0] - px) * (ys[2] - py)) / area
    w2 = 1 - w0 - w1
    inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
    if not inside.any():
        return False
    iz = w0 * inv_z[0] + w1 * inv_z[1] + w2 * inv_z[2]
    sub = zbuf[y0:y1 + 1, x0:x1 + 1]
    win = inside & (iz > sub)
    sub[win] = iz[win]
    idbuf[y0:y1 + 1, x0:x1 + 1][win] = ident
    return True


def clip_near(pts, near):
    """A polygon (camera-space points) cut to the part in front of the near plane."""
    out = []
    for k in range(len(pts)):
        a, b = pts[k], pts[(k + 1) % len(pts)]
        if a[2] > near:
            out.append(a)
        if (a[2] > near) != (b[2] > near):
            t = (near - a[2]) / (b[2] - a[2])
            out.append(tuple(a[i] + t * (b[i] - a[i]) for i in range(3)))
    return out


def visible(mat, lens, blocks, near, far, count):
    """The blocks on screen under one view matrix, and each block's nearest point's depth."""
    zbuf = np.zeros((H // RES, W // RES))
    idbuf = np.full((H // RES, W // RES), -1)
    shown = set()
    depth = np.full(count, np.inf)
    for b, (v, polys) in blocks.items():
        x, y, z = camera(mat, v)
        if z.max() <= near or z.min() >= far:
            continue
        depth[b] = z[z > near].min()
        for attr, idx in polys:
            if z[idx].max() <= near or z[idx].mean() >= far:
                continue
            pts = [(x[i], y[i], z[i]) for i in idx]
            if z[idx].min() <= near:        # crosses the camera plane: CCE draws the part in front
                pts = clip_near(pts, near)
            scr = np.array([[(px * lens / pz + CX) / RES, (-py * lens / pz + CY) / RES] for px, py, pz in pts])
            inv_z = np.array([1.0 / pz for _, _, pz in pts])
            if attr & 0x10:                 # one-sided: 06045C9C's test, by the polygon's winding
                area = np.sum(scr[:, 0] * np.roll(scr[:, 1], -1) - np.roll(scr[:, 0], -1) * scr[:, 1])
                if area >= 0:
                    continue
            hit = False
            for k in range(1, len(scr) - 1):
                tri = [0, k, k + 1]
                hit |= raster(scr[tri], inv_z[tri], zbuf, idbuf, b)
            if not hit:
                cx, cy = scr.mean(axis=0)
                if 0 <= cx < W / RES and 0 <= cy < H / RES and inv_z.mean() > zbuf[int(cy), int(cx)]:
                    shown.add(b)
    vis = np.zeros(count, bool)
    vis[np.unique(idbuf[idbuf >= 0])] = True
    vis[list(shown)] = True
    return vis, depth


def main():
    out = sys.argv[1]
    with ProcessPoolExecutor(2) as pool:  # a process each: tools/soundlab.py's command numbering is shared
        view = pool.submit(run, 'view')
        time.sleep(2)                       # and its IPC directory is named by the second
        count = pool.submit(run, 'frames')
        views, counts = view.result(), count.result()
    save = {}
    for c, ((raw, models, near, far, lens, count), frames) in enumerate(zip(views, counts)):
        blocks = {b: parse(mdl, at) for b, (mdl, at) in models.items()}
        mats = raw[:, MATRIX - FLAGS:MATRIX - FLAGS + 48].copy().view('>i4').astype(np.int64)
        cce = raw[:, :count] != 0
        # the camera at each frame count: the sample where the count last reads so
        # from the cut (the count leaves -1; before, the blob may still be loading)
        cut = next(k for k in range(1, len(frames)) if frames[k - 1] == -1 and frames[k] >= 0)
        last = {}
        for k in range(cut, len(frames)):
            last[int(frames[k])] = k
        fs = sorted(last)
        found = [visible(mats[last[f]], lens, blocks, near, far, count) for f in fs]
        vis = np.array([v for v, _ in found])
        save[f'c{c}_frames'] = np.array(fs)
        save[f'c{c}_vis'] = vis
        save[f'c{c}_depth'] = np.array([np.minimum(d, 0xFFFF) for _, d in found]).astype(np.uint16)
        save[f'c{c}_cce'] = cce[[last[f] for f in fs]]
        save[f'c{c}_eye'] = np.array([eye(mats[last[f]]) for f in fs], np.float32)
        print(f'course {c}: {len(fs)} cameras, {vis.sum(axis=1).mean():.1f} blocks on screen a frame '
              f'(CCE draws {save[f"c{c}_cce"].sum(axis=1).mean():.1f})', flush=True)
    np.savez_compressed(out, **save)


if __name__ == '__main__':
    main()
