"""The Linux download for GitHub's Releases: the builder and its read-me, in a folder in a tar.gz.

usage: release_linux.py <builder> <read-me> <Cargo.toml> <Windows builder's Cargo.toml> <out dir>

The version comes from Cargo.toml, and must be the Windows builder's; it names the
archive and fills {version} in the read-me. The builder goes in executable, whatever
the file system it was built on keeps.
"""
import io, re, sys, tarfile, time
from pathlib import Path

FOLDER = 'Daytona USA Ultimate Builder'
EXE_NAME = 'daytona-usa-ultimate-builder'


def version(cargo):
    return re.search(r'^version = "(.+)"', cargo.read_text(), re.M).group(1)


def main():
    exe, readme, cargo, windows_cargo, out_dir = map(Path, sys.argv[1:6])
    ver = version(cargo)
    if ver != version(windows_cargo):
        sys.exit(f'{cargo} says {ver}, {windows_cargo} says {version(windows_cargo)}: make them the same')
    if exe.read_bytes()[:4] != b'\x7fELF':
        sys.exit(f'{exe} is not a Linux program')
    text = readme.read_text(encoding='utf-8').replace('{version}', ver).replace('\r\n', '\n').encode('utf-8')
    out = out_dir / f'Daytona-USA-Ultimate-v{ver}-linux-x86_64.tar.gz'
    out_dir.mkdir(parents=True, exist_ok=True)
    now = int(time.time())

    def entry(name, mode, size=0, kind=tarfile.REGTYPE):
        t = tarfile.TarInfo(name)
        t.mode, t.size, t.mtime, t.type = mode, size, now, kind
        t.uname = t.gname = ''
        return t

    with tarfile.open(out, 'w:gz', compresslevel=9) as tar:
        tar.addfile(entry(FOLDER, 0o755, kind=tarfile.DIRTYPE))
        data = exe.read_bytes()
        tar.addfile(entry(f'{FOLDER}/{EXE_NAME}', 0o755, len(data)), io.BytesIO(data))
        tar.addfile(entry(f'{FOLDER}/README.txt', 0o644, len(text)), io.BytesIO(text))
    print(out, out.stat().st_size)


main()
