"""The zip players download from GitHub's Releases: the disc builder and its read-me.

usage: release_zip.py <builder exe> <read-me> <Cargo.toml> <out dir>

The version comes from Cargo.toml; it names the zip and fills {version} in the
read-me, which goes in with Windows line endings so Notepad shows it right.
"""
import re, sys, zipfile
from pathlib import Path

EXE_NAME = 'Daytona USA Ultimate Builder.exe'


def main():
    exe, readme, cargo, out_dir = map(Path, sys.argv[1:5])
    version = re.search(r'^version = "(.+)"', cargo.read_text(), re.M).group(1)
    text = readme.read_text(encoding='utf-8').replace('{version}', version)
    text = text.replace('\r\n', '\n').replace('\n', '\r\n')
    out = out_dir / f'Daytona-USA-Ultimate-v{version}-windows.zip'
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(exe, EXE_NAME)
        z.writestr('README.txt', text)
    print(out, out.stat().st_size)


main()
