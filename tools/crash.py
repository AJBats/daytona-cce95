"""The crash screen (src/crash.c, src/crash_entry.s) as DAYTONA/CRASH.BIN.

usage: crash.py <out dir>
  Writes <out dir>/DAYTONA/CRASH.BIN, lists it in PATCHED.txt, and prints
  where its parts landed.

The blob runs at CRASH_AT, in the zeros CCE's main program carries before
its code at 060191A8: tools/race_block.py's block ends below CRASH_AT, and
nothing else in any mode touches the stretch (docs/crash_screen.md). It
can't come with the main program: CCE clears that stretch at boot. So
patches/crash.s loads the file at boot, after CCE's init, and copies it in.

The screen names the build: the release's version (patcher/src-tauri/
Cargo.toml) and the commit, with + when the tree had changes.
"""
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCC = os.path.join(ROOT, 'tools', 'sh-gcc', 'bin')
CRASH_AT = 0x06018A00
CRASH_END = 0x060191A8                  # the main program's code from here on
MAGIC = 0x43525348                      # 'CRSH', patches/crash.s checks it


def version():
    toml = open(os.path.join(ROOT, 'patcher', 'src-tauri', 'Cargo.toml')).read()
    v = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M).group(1)
    git = lambda *a: subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout.strip()
    commit = git('rev-parse', '--short=7', 'HEAD') or 'UNKNOWN'
    dirty = '+' if git('status', '--porcelain', '--untracked-files=no') else ''
    return f'{v} {commit}{dirty}'.upper()


def build(work):
    os.makedirs(work, exist_ok=True)
    v = version()
    assert re.fullmatch(r'[0-9A-Z .:/+-]+', v), v       # what the screen's font draws
    open(os.path.join(work, 'crash_version.h'), 'w').write(f'#define CRASH_VERSION "{v}"\n')
    env = dict(os.environ, PATH=GCC + os.pathsep + os.environ['PATH'])
    src = os.path.join(ROOT, 'src')
    elf, binf = os.path.join(work, 'crash.elf'), os.path.join(work, 'crash.bin')
    run = lambda *cmd: subprocess.run(cmd, env=env, check=True)
    run(os.path.join(GCC, 'sh2eb-elf-gcc'), '-m2', '-mb', '-Os', '-fomit-frame-pointer', '-ffreestanding',
        '-nostdlib', '-I', work, '-T', os.path.join(src, 'crash.ld'), f'-Wl,--defsym,crash_at={CRASH_AT:#x}',
        '-Wl,-e,_crash_init', '-Wl,--no-warn-rwx-segments', '-Wl,-Map,' + os.path.join(work, 'crash.map'),
        '-o', elf, os.path.join(src, 'crash.c'), os.path.join(src, 'crash_entry.s'), '-lgcc')
    run(os.path.join(GCC, 'sh2eb-elf-objcopy'), '-O', 'binary', '-j', '.blob', elf, binf)
    syms = subprocess.run([os.path.join(GCC, 'sh2eb-elf-nm'), elf], env=env, check=True, capture_output=True,
                          text=True).stdout
    syms = {n: int(a, 16) for a, _, n in (line.split() for line in syms.splitlines() if len(line.split()) == 3)}
    return open(binf, 'rb').read(), syms, v


def main():
    dst = sys.argv[1]
    blob, syms, v = build(os.path.join(dst, '..', 'crash'))
    assert struct.unpack_from('>I', blob)[0] == MAGIC and len(blob) % 4 == 0
    assert struct.unpack_from('>I', blob, 4)[0] == syms['_crash_init']
    assert CRASH_AT + len(blob) <= CRASH_END, f'{len(blob)} bytes, room for {CRASH_END - CRASH_AT}'
    os.makedirs(os.path.join(dst, 'DAYTONA'), exist_ok=True)
    open(os.path.join(dst, 'DAYTONA', 'CRASH.BIN'), 'wb').write(blob)
    listing = os.path.join(dst, 'PATCHED.txt')
    have = open(listing).read().split() if os.path.exists(listing) else []
    have += [n for n in ['DAYTONA/CRASH.BIN'] if n not in have]
    open(listing, 'w').write(''.join(n + '\n' for n in sorted(have)))
    print(f'crash screen: {len(blob)} bytes at {CRASH_AT:08X} (room to {CRASH_END:08X}), "{v}"; '
          f'crash_max_still at {syms["_crash_max_still"]:08X}, crash_slave at {syms["_crash_slave"]:08X}')


if __name__ == '__main__':
    main()
