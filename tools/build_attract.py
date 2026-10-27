"""Build the attract's scene code: DUSA's attract camera and cars running in
CCE95's attract, from src/attract.c.

usage: build_attract.py <dusa extracted dir> <out dir> <cce files dir>
  Reads DUSA's APROG.BIN for its attract tables on its three courses,
  <out dir>/dusa_cars.npz (tools/attract_record.py) for its cars and, when
  there, <out dir>/course_vis.npz (tools/attract_vis.py) for the course
  blocks on screen, writes
  <out dir>/dusa_attract.h, compiles and links src/attract.c at LWRAM
  0x002E2780 (src/attract.ld) with tools/sh-gcc (SH-2 GCC, gitignored, copied in per
  machine) and writes <out dir>/attract.bin (the code) and <out dir>/cars.blk
  (the cars' tracks: a 4-byte address, then the data), which
  tools/title_convert.py puts in DEMOTTL.BIN (docs/attract.md, "Camera work").
  The cce files dir holds the ground files the attract loads (their sizes
  say where the cars can go).

Cars (cars.blk, read where it lands in work RAM): one piece per course,
each where its course's demo leaves work RAM alone (below). A piece is a
scene count byte, the offset of its course blocks (24-bit, 0 for none), a
4-byte offset per scene; a scene is a car
count byte, a pad byte, its tick count (16-bit; its track holds one more,
the last again), then per car 24 bytes: position x, y, z (16.16), pitch,
yaw, roll (16-bit), its visibility at the first tick (16-bit: 1 when DUSA
draws it) and the offset of its track. A track holds each tick after the
first as changes of the per-tick step (the second difference) of the
position (16.16) and of the angles (unwrapped), and when DUSA starts or
stops drawing the car (its flags +0 & 0xE00000, the detail levels its draw
loop 0600B914 needs one of): a byte with bit 7 set is a run of (bits 0-6)
ticks with no change; otherwise bits 0-5 say which of the six values
change, bit 6 that the visibility flips, and a signed varint (zigzag, 7
bits a byte, low first) follows per change. Offsets count from the start
of the piece.

Course blocks (COURSE_LISTS; none with COURSE_LISTS=0 in the environment):
per camera of the demo (course_vis.npz, by src/attract.c's frame count),
the blocks CCE draws there, and the blocks on screen that CCE draws at
some other camera of the same shot, for patches/course_list.s to draw in
place of CCE's own choice: CCE's choice without the drops as the camera's
sector changes. A block on screen is listed from the camera before it
shows (a frame between two cameras, as a Saturn's frame count runs on
whether or not it draws, has both cameras' blocks) to 15 cameras after it
last shows (so one hidden for a moment, behind the bridge's tower or a few
pixels at the screen's edge, doesn't blink), within its shot (a camera
more than SHOT_JUMP from the last starts one). Records: a frame count (16-bit), a
count byte and that many block numbers (16-bit) whose state flips from
that frame; frame 0xFFFF ends them.

Where: CCE's race start reads DEMOTTL.BIN whole to 0x220000, copies its
blocks out, then reads the course's ground file over the buffer, also from
0x220000. Through every demo, work RAM from the ground file's end to
0x2DC000 (CMVDATA.BIN) is left alone. The pieces go top down from
0x2DC000, the last course's first: each lies past its own course's ground
file; a piece of another course may lie under a ground file, which loads
over it after the copy.

DUSA (APROG.BIN loaded at 06003000): the attract's scene list for course c
is at *(0605F5EC + 4c); a scene is (car count, events, first camera
keyframe, car placements). Camera keyframes are 32 bytes: +0 time in 20 Hz
ticks (0 starts a shot, 0xFFFF jumps to the keyframe at +4), +2 the car the
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
COURSE_SCENES = 0x0605F5EC  # a scene list per course
LWRAM = 0x002E2780          # DEMOTTL.BIN's work RAM block, CCE's title data before
LWRAM_SIZE = 0x2680
GROUND_AT = 0x00220000      # where the race start reads the ground file
CARS_END = 0x002DC000       # CMVDATA.BIN
GROUND = {0: ['CS0_COL.BIN'], 1: ['CS1_COL.BIN', 'CS12_COL.BIN'], 2: ['CS2_COL.BIN']}
GCC = os.path.join(os.path.dirname(__file__), 'sh-gcc', 'bin')
COURSE_LISTS = (2,)         # the courses whose demo draws its recorded block lists (Seaside Galaxy)
LIST_LEAD, LIST_HOLD = 1, 15    # a block is listed from a camera before it shows to 15 after (half a second)
SHOT_JUMP = 10              # units: a camera this far from the last starts a shot
MAX_BLOCKS = 512            # src/attract.c's block bits


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


def cars(z, c):
    """Course c's piece of cars.blk, and its number of cars per scene."""
    scenes, counts = [], []
    for s in range(int(z[f'c{c}_scenes'])):
        pose = z[f'c{c}_pose{s}'].astype(np.int64)
        vis = (z[f'c{c}_flags{s}'] & 0xE00000) != 0
        n = max(i for i in range(pose.shape[1]) if vis[:, i].any()) + 1
        q = pose[:, :n].copy()
        step = (np.diff(q[:, :, 3:], axis=0) + 0x8000) % 0x10000 - 0x8000
        q[1:, :, 3:] = q[0, :, 3:] + np.cumsum(step, axis=0)
        ticks = len(q)
        # the last tick once more: the player reads a tick ahead, and holds the last
        q, vis = np.concatenate([q, q[-1:]]), np.concatenate([vis, vis[-1:]])
        scenes.append((ticks, [(q[:, i], vis[:, i]) for i in range(n)]))
        counts.append(n)
    head = 4 + 4 * len(scenes)
    blob = bytearray(head)
    blob[0] = len(scenes)
    for s, (ticks, tracks) in enumerate(scenes):
        struct.pack_into('>I', blob, 4 + 4 * s, len(blob))
        at = len(blob)
        blob += struct.pack('>BBH', len(tracks), 0, ticks) + bytes(24 * len(tracks))
        for i, (q, v) in enumerate(tracks):
            p = q[0]
            struct.pack_into('>3i3hHI', blob, at + 4 + 24 * i, *[int(x) for x in p[:3]],
                             *[int(x) - 0x10000 if x >= 0x8000 else int(x) for x in p[3:]], int(v[0]), len(blob))
            blob += track(q, v)
    blob += bytes(-len(blob) % 4)
    return bytes(blob), counts


def course_blocks(vz, c):
    """Course c's block list stream (see above), or None."""
    if vz is None or c not in COURSE_LISTS or os.environ.get('COURSE_LISTS') == '0' or f'c{c}_vis' not in vz:
        return None
    frames, vis, cce = vz[f'c{c}_frames'], vz[f'c{c}_vis'], vz[f'c{c}_cce']
    jump = np.linalg.norm(np.diff(vz[f'c{c}_eye'], axis=0), axis=1) > SHOT_JUMP
    starts = [0] + [i + 1 for i in np.nonzero(jump)[0]] + [len(frames)]
    padded = np.zeros_like(vis)
    for a, b in zip(starts, starts[1:]):
        shot = vis[a:b] & cce[a:b].any(axis=0)
        p = shot.copy()
        for k in range(1, LIST_LEAD + 1):
            p[:-k] |= shot[k:]
        for k in range(1, LIST_HOLD + 1):
            p[k:] |= shot[:-k]
        padded[a:b] = p | cce[a:b]
    if vis.shape[1] > MAX_BLOCKS:
        sys.exit(f'course {c}: {vis.shape[1]} blocks, src/attract.c keeps {MAX_BLOCKS}')
    out, shown = bytearray(), np.zeros(vis.shape[1], bool)
    for i, f in enumerate(frames):
        flip = np.nonzero(padded[i] != shown)[0]
        if len(flip):
            out += struct.pack('>HB%dH' % len(flip), 0 if i == 0 else int(f), len(flip), *(int(b) for b in flip))
            shown = padded[i].copy()
    return bytes(out) + b'\xFF\xFF'


def u32(a, addr):
    return struct.unpack_from('>I', a, addr - APROG_AT)[0]


def keyframes(aprog, scenes):
    """The keyframes from the first scene's first through the last loop."""
    first_kf = min(u32(aprog, s + 8) for s in scenes)
    last_loop = max(u32(aprog, s + 8) for s in scenes)
    kfs, k = [], first_kf
    while True:
        rec = aprog[k - APROG_AT:k - APROG_AT + 32]
        kfs.append(rec)
        if struct.unpack_from('>H', rec, 0)[0] == 0xFFFF and \
                struct.unpack_from('>I', rec, 4)[0] >= last_loop and k > last_loop:
            return first_kf, kfs
        k += 32


def tables(aprog, n_scenes, cars_at):
    """dusa_attract.h: every course's keyframes in one table (jumps index it),
    the scenes' first keyframes, and per course its scenes and cars."""
    kf_lines, scene_lines, course_lines = [], [], []
    for c, n in enumerate(n_scenes):
        lst = u32(aprog, COURSE_SCENES + 4 * c)
        scenes = [u32(aprog, lst + 4 * i) for i in range(n)]
        first_kf, kfs = keyframes(aprog, scenes)
        base = len(kf_lines)
        for rec in kfs:
            t, pcar, tcar = struct.unpack_from('>Hbb', rec, 0)
            jump = struct.unpack_from('>I', rec, 4)[0]
            pos = struct.unpack_from('>3i', rec, 8)
            tgt = struct.unpack_from('>3i', rec, 20)
            kf_lines.append('    {%d, %d, %d, %d, {%d, %d, %d}, {%d, %d, %d}},' % (
                t if t != 0xFFFF else -1, pcar, tcar, base + (jump - first_kf) // 32 if t == 0xFFFF else 0,
                *pos, *tgt))
        course_lines.append('    {%d, %d, (const unsigned char *)0x%08X},' % (len(scene_lines), n, cars_at[c]))
        scene_lines += ['    {%d},' % (base + (u32(aprog, s + 8) - first_kf) // 32) for s in scenes]
    return '\n'.join([
        '/* DUSA\'s attract tables, from APROG.BIN by tools/build_attract.py */',
        '#define N_KF %d' % len(kf_lines), 'static const kf_t kfs[N_KF] = {', *kf_lines, '};',
        'static const scene_t scenes[%d] = {' % len(scene_lines), *scene_lines, '};',
        '#define N_DUSA_COURSES %d' % len(n_scenes),
        'static const course_t courses[N_DUSA_COURSES] = {', *course_lines, '};']) + '\n'


def ground_end(cce, c):
    return GROUND_AT + max(os.path.getsize(os.path.join(cce, 'DAYTONA', n)) for n in GROUND[c])


def main():
    dusa, out, cce = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    aprog = open(os.path.join(dusa, 'APROG.BIN'), 'rb').read()
    npz = os.path.join(out, 'dusa_cars.npz')
    if not os.path.exists(npz):
        sys.exit(f'{npz} missing: tools/attract_record.py {npz} records it from DUSA')
    z = np.load(npz)
    if 'courses' not in z:
        sys.exit(f'{npz} is from before the attract had three courses: delete it, make disc records it again')
    pieces = [cars(z, c) for c in range(int(z['courses']))]
    vis_npz = os.path.join(out, 'course_vis.npz')
    vz = np.load(vis_npz) if os.path.exists(vis_npz) else None
    if vz is None:
        print(f'attract: {vis_npz} missing: CCE chooses the course blocks (tools/attract_vis.py records it from a built disc)')
    for c, (piece, counts) in enumerate(pieces):
        stream = course_blocks(vz, c)
        if stream:
            piece = bytearray(piece)
            piece[1:4] = len(piece).to_bytes(3, 'big')
            piece += stream + bytes(-len(stream) % 4)
            pieces[c] = (bytes(piece), counts)
    at, cars_at = CARS_END, []
    for c in reversed(range(len(pieces))):
        at -= len(pieces[c][0])
        if at < ground_end(cce, c):
            sys.exit(f'cars: course {c} at {at:08X} lies under its ground file (to {ground_end(cce, c):08X})')
        cars_at.insert(0, at)
    open(os.path.join(out, 'cars.blk'), 'wb').write(struct.pack('>I', cars_at[0]) + b''.join(p for p, _ in pieces))
    counts = [n for _, cs in pieces for n in cs]
    header = tables(aprog, [len(cs) for _, cs in pieces], cars_at) + '#define MAX_CARS %d\n' % max(counts)
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
    print(f'attract: scene code {size} of {LWRAM_SIZE} bytes at {LWRAM:08X}; cars, '
          + ', '.join(f'course {c}: {len(cs)} scene(s) ({", ".join(map(str, cs))} cars) in {len(p)} bytes at {a:08X}'
                      for c, ((p, cs), a) in enumerate(zip(pieces, cars_at))))


if __name__ == '__main__':
    main()
