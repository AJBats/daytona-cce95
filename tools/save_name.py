"""The save files' names, our own for each release (docs/backup.md).

usage: save_name.py <out dir>
  Rewrites the names in <out dir>/DAYTONA/BKUP.BIN, NAME.BIN and SLCT.BIN.

The Saturn knows a save only by its file name: 11 characters, shown in the
Memory Manager with a comment of up to 10. CCE writes DAYTONA96_0 (comment
RECORDS) and, on a cartridge, DAYTONA96_1 (GHOST). Ours are named for the
release, from the version in patcher/src-tauri/Cargo.toml: 1.0.0-beta.2 is
DAYULT_B2_0 and DAYULT_B2_1, 1.0.0 DAYULT_V1_0 and DAYULT_V1_1. So a release
never reads another's save, CCE's or an earlier beta's, whose layout may
differ (patches/save_ext.s), and CCE never reads ours. A beta's fix release
(1.0.0-beta.2.1) keeps its beta's names and layout, so its save carries
over. The comments stay CCE's.

Each of the three programs that reads and writes the save (the boot check,
the name entry and the menus) holds the two names, each in 12 bytes with its
terminating zero; nothing else names the files.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 0x06028000
NAMES = {                                   # program: where its two names are
    'BKUP.BIN': 0x06036808,
    'NAME.BIN': 0x0603BD38,
    'SLCT.BIN': 0x06041880,
}
CCE = [b'DAYTONA96_0', b'DAYTONA96_1']


def release_tag():
    toml = open(os.path.join(ROOT, 'patcher', 'src-tauri', 'Cargo.toml')).read()
    v = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M).group(1)
    m = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+)(?:\.\d+)?)?', v)
    if not m:
        sys.exit(f'save_name.py: no save name for version {v}')
    major, minor, patch, beta = m.groups()
    if beta:
        return v, f'B{beta}'
    return v, f'V{major}' + (minor if minor != '0' else '')


def main():
    dst = sys.argv[1]
    version, tag = release_tag()
    names = [f'DAYULT_{tag}_{n}'.encode() for n in (0, 1)]
    for name in names:
        if len(name) > 11 or not re.fullmatch(rb'[A-Z0-9_]+', name):
            sys.exit(f'save_name.py: {name.decode()} is not a Saturn file name (11 of A-Z, 0-9, _)')
    for prog, at in NAMES.items():
        path = os.path.join(dst, 'DAYTONA', prog)
        data = bytearray(open(path, 'rb').read())
        for i, (old, new) in enumerate(zip(CCE, names)):
            off = at - BASE + 12 * i
            if data[off:off + 12] != old + b'\0':
                sys.exit(f'save_name.py: {prog} {at + 12 * i:08X} holds {bytes(data[off:off + 12])!r}, not {old!r}')
            data[off:off + 12] = new.ljust(12, b'\0')
        open(path, 'wb').write(data)
    print(f'save names for {version}: {names[0].decode()} (records), {names[1].decode()} (ghosts)')


if __name__ == '__main__':
    main()
