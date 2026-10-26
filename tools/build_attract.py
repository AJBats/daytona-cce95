"""Build the attract's scene code: DUSA's attract camera and cars running in
CCE95's attract, from src/attract.c.

usage: build_attract.py <dusa extracted dir> <out dir>
  Reads DUSA's APROG.BIN for its course-0 attract tables and
  <out dir>/dusa_cars.npz (tools/attract_record.py) for its cars, writes
  <out dir>/dusa_attract.h, compiles and links src/attract.c at LWRAM
  0x002E2780 (src/attract.ld) with tools/sh-gcc (SH-2 GCC, gitignored, copied in per
  machine) and writes <out dir>/attract.bin (the code) and <out dir>/cars.blk
  (the cars' tracks: a 4-byte address, then the data), which
  tools/title_convert.py puts in DEMOTTL.BIN (docs/attract.md, "Camera work").

Cars (cars.blk, read where it lands in VDP2 VRAM): a scene count byte, 3
pad bytes, a 4-byte offset per scene; a scene is a car count byte, a pad
byte, its tick count (16-bit), then per car 24 bytes: position x, y, z
(16.16), pitch, yaw, roll (16-bit), its visibility at the first tick
(16-bit: 1 when DUSA draws it) and the offset of its track. A track holds
each tick after the first as changes of the per-tick step (the second
difference) of the position (16.16) and of the angles (unwrapped), and
when DUSA starts or stops drawing the car (its flags +0 & 0xE00000, the
detail levels its draw loop 0600B914 needs one of): a byte with bit 7
set is a run of (bits 0-6) ticks with no change; otherwise bits 0-5 say
which of the six values change, bit 6 that the visibility flips, and a
signed varint (zigzag, 7 bits a byte, low first) follows per change.
Offsets count from the start of the data.

DUSA (APROG.BIN loaded at 06003000): the attract's scenes for course 0 are
listed at 0605F5CC; a scene is (car count, events, first camera keyframe,
car placements). Camera keyframes are 32 bytes: +0 time in 20 Hz ticks
(0 starts a shot, 0xFFFF jumps to the keyframe at +4), +2 the car the
position rides with (-1 the world), +3 the car the target rides with, +8
position, +20 target (16.16). Events are (time, car or 0xFFFF for the end
of the scene), then (speed, lane).
"""
import os
import struct
import subprocess
import sys

import numpy as np

APROG_AT = 0x06003000
SCENES = 0x0605F5CC         # course 0's scene list
N_SCENES = 3
CAR_SCENES = 1              # scenes whose cars are DUSA's so far
LWRAM = 0x002E2780          # DEMOTTL.BIN's work RAM block, CCE's title data before
LWRAM_SIZE = 0x2680
CARS_AT = 0x25E47000        # VDP2 VRAM after the title's staging (tools/title_convert.py),
CARS_END = 0x25E58184       # in the space CCE's own title kept there through the demo
GCC = os.path.join(os.path.dirname(__file__), 'sh-gcc', 'bin')


def varint(v):
    z = (v << 1) ^ (v >> 63)
    out = bytearray()
    while True:
        out.append(z & 0x7F | (0x80 if z > 0x7F else 0))
        z >>= 7
        if not z:
            return bytes(out)


def track(q, vis):
    """q: ticks x 6 (position 16.16, angles unwrapped), vis: ticks."""
    out, run = bytearray(), 0
    d1, shown = np.zeros(6, np.int64), vis[0]
    for t in range(1, len(q)):
        step = q[t] - q[t - 1]
        d2, d1 = step - d1, step
        flip = vis[t] != shown
        shown = vis[t]
        if not d2.any() and not flip:
            run += 1
            if run == 0x7F:
                out.append(0x80 | run)
                run = 0
            continue
        if run:
            out.append(0x80 | run)
            run = 0
        mask = sum(1 << i for i in range(6) if d2[i]) | (0x40 if flip else 0)
        out.append(mask)
        for i in range(6):
            if d2[i]:
                out += varint(int(d2[i]))
    if run:
        out.append(0x80 | run)
    return bytes(out)


def cars(npz):
    """cars.blk's data, and the number of cars per scene."""
    z = np.load(npz)
    scenes, counts = [], []
    for s in range(CAR_SCENES):
        pose = z[f'pose{s}'].astype(np.int64)
        vis = (z[f'flags{s}'] & 0xE00000) != 0
        n = max(c for c in range(pose.shape[1]) if vis[:, c].any()) + 1
        q = pose[:, :n].copy()
        step = (np.diff(q[:, :, 3:], axis=0) + 0x8000) % 0x10000 - 0x8000
        q[1:, :, 3:] = q[0, :, 3:] + np.cumsum(step, axis=0)
        scenes.append((len(q), [(q[:, c], vis[:, c]) for c in range(n)]))
        counts.append(n)
    head = 4 + 4 * len(scenes)
    blob = bytearray(head)
    blob[0] = len(scenes)
    for s, (ticks, tracks) in enumerate(scenes):
        struct.pack_into('>I', blob, 4 + 4 * s, len(blob))
        at = len(blob)
        blob += struct.pack('>BBH', len(tracks), 0, ticks) + bytes(24 * len(tracks))
        for c, (q, v) in enumerate(tracks):
            p = q[0]
            struct.pack_into('>3i3hHI', blob, at + 4 + 24 * c, *[int(x) for x in p[:3]],
                             *[int(x) - 0x10000 if x >= 0x8000 else int(x) for x in p[3:]], int(v[0]), len(blob))
            blob += track(q, v)
    if len(blob) > CARS_END - CARS_AT:
        sys.exit(f'cars: {len(blob)} bytes, room for {CARS_END - CARS_AT}')
    return bytes(blob), counts


def u32(a, addr):
    return struct.unpack_from('>I', a, addr - APROG_AT)[0]


def tables(aprog):
    scenes = [u32(aprog, SCENES + 4 * i) for i in range(N_SCENES)]
    first_kf = min(u32(aprog, s + 8) for s in scenes)
    # keyframes from the first scene's first through the last loop
    kfs, k = [], first_kf
    last_loop = max(u32(aprog, s + 8) for s in scenes)
    while True:
        rec = aprog[k - APROG_AT:k - APROG_AT + 32]
        kfs.append(rec)
        if struct.unpack_from('>H', rec, 0)[0] == 0xFFFF and \
                struct.unpack_from('>I', rec, 4)[0] >= last_loop and k > last_loop:
            break
        k += 32
    lines = ['/* DUSA course-0 attract tables, from APROG.BIN by tools/build_attract.py */',
             '#define N_KF %d' % len(kfs), 'static const kf_t kfs[N_KF] = {']
    for rec in kfs:
        t, pcar, tcar = struct.unpack_from('>Hbb', rec, 0)
        jump = struct.unpack_from('>I', rec, 4)[0]
        if t == 0xFFFF:
            jump = (jump - first_kf) // 32
        pos = struct.unpack_from('>3i', rec, 8)
        tgt = struct.unpack_from('>3i', rec, 20)
        lines.append('    {%d, %d, %d, %d, {%d, %d, %d}, {%d, %d, %d}},' % (
            t if t != 0xFFFF else -1, pcar, tcar, jump if t == 0xFFFF else 0, *pos, *tgt))
    lines.append('};')
    lines.append('static const scene_t scenes[%d] = {' % N_SCENES)
    for s in scenes:
        events = u32(aprog, s + 4)
        end = 0
        for i in range(64):
            t, car = struct.unpack_from('>HH', aprog, events - APROG_AT + 8 * i)
            if car == 0xFFFF:
                end = t
                break
        lines.append('    {%d, %d},' % ((u32(aprog, s + 8) - first_kf) // 32, end))
    lines.append('};')
    return '\n'.join(lines) + '\n'


def main():
    dusa, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    aprog = open(os.path.join(dusa, 'APROG.BIN'), 'rb').read()
    npz = os.path.join(out, 'dusa_cars.npz')
    if not os.path.exists(npz):
        sys.exit(f'{npz} missing: tools/attract_record.py {npz} records it from DUSA')
    data, counts = cars(npz)
    open(os.path.join(out, 'cars.blk'), 'wb').write(struct.pack('>I', CARS_AT) + data)
    header = tables(aprog) + '#define CARS_AT 0x%08X\n#define N_CAR_SCENES %d\n#define MAX_CARS %d\n' % (
        CARS_AT, CAR_SCENES, max(counts))
    open(os.path.join(out, 'dusa_attract.h'), 'w').write(header)
    env = dict(os.environ, PATH=GCC + os.pathsep + os.environ['PATH'])
    src = os.path.join(os.path.dirname(__file__), '..', 'src', 'attract.c')
    elf = os.path.join(out, 'attract.elf')
    run = lambda *cmd: subprocess.run(cmd, env=env, check=True)
    run(os.path.join(GCC, 'sh2eb-elf-gcc'), '-m2', '-mb', '-O2', '-fomit-frame-pointer',
        '-ffreestanding', '-nostdlib', '-I', out, '-T', src[:-2] + '.ld', '-Wl,-e,_attract_entry', '-Wl,--no-warn-rwx-segments',
        '-o', elf, src, '-lgcc')
    run(os.path.join(GCC, 'sh2eb-elf-objcopy'), '-O', 'binary', elf, os.path.join(out, 'attract.bin'))
    size = os.path.getsize(os.path.join(out, 'attract.bin'))
    if size > LWRAM_SIZE:
        sys.exit(f'attract.bin is {size} bytes, room for {LWRAM_SIZE}')
    print(f'attract: scene code {size} of {LWRAM_SIZE} bytes at {LWRAM:08X}; cars of {CAR_SCENES} scene(s) '
          f'({", ".join(map(str, counts))} cars) in {len(data)} of {CARS_END - CARS_AT} bytes at {CARS_AT:08X}')


if __name__ == '__main__':
    main()
