"""Build the attract's scene code: DUSA's attract camera (and later its
staging) running in CCE95's attract, from src/attract.c.

usage: build_attract.py <dusa extracted dir> <out dir>
  Reads DUSA's APROG.BIN for its course-0 attract tables, writes
  <out dir>/dusa_attract.h, compiles and links src/attract.c at LWRAM
  0x002E2780 (src/attract.ld) with tools/sh-gcc (SH-2 GCC, gitignored, copied in per
  machine) and writes <out dir>/attract.bin, which tools/title_convert.py
  puts in DEMOTTL.BIN (docs/attract.md, "Camera work").

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

APROG_AT = 0x06003000
SCENES = 0x0605F5CC         # course 0's scene list
N_SCENES = 3
LWRAM = 0x002E2780          # DEMOTTL.BIN's work RAM block, CCE's title data before
LWRAM_SIZE = 0x2680
GCC = os.path.join(os.path.dirname(__file__), 'sh-gcc', 'bin')


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
    open(os.path.join(out, 'dusa_attract.h'), 'w').write(tables(aprog))
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
    print(f'attract: scene code {size} of {LWRAM_SIZE} bytes at {LWRAM:08X}')


if __name__ == '__main__':
    main()
