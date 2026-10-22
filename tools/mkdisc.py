"""Build a patched CCE disc: copy the original data track, overwrite files in
place with replacements from a patch directory, regenerate EDC/ECC, and emit a
cue sheet whose audio tracks are hard links to the original image's tracks
(Mednafen on Windows does not follow '..' paths inside a cue).

usage: mkdisc.py <orig.cue> <patchdir> <outdir>

A replacement may not outgrow the sectors the original file occupies. Only
the files listed in <patchdir>/PATCHED.txt are used.
"""
import os
import re
import sys

from cdimage import Image


def main():
    cue, patchdir, outdir = sys.argv[1:4]
    srcdir = os.path.dirname(os.path.abspath(cue))
    os.makedirs(outdir, exist_ok=True)
    text = open(cue).read()
    names = re.findall(r'FILE "([^"]+)"', text)

    img = Image(os.path.join(srcdir, names[0]))
    layout = {p: (lba, size) for p, lba, size in img.files()}
    patched = []
    listing = os.path.join(patchdir, 'PATCHED.txt')
    wanted = open(listing).read().split() if os.path.exists(listing) else []
    for rel in wanted:
        if rel not in layout:
            sys.exit(f'error: {rel} is not a file on the disc')
        lba, size = layout[rel]
        data = open(os.path.join(patchdir, rel), 'rb').read()
        cap = (size + 2047) // 2048 * 2048
        if len(data) > cap:
            sys.exit(f'error: {rel} is {len(data)} bytes, slot holds {cap}')
        img.write(lba, data)
        patched.append(rel)

    track1 = 'track01.bin'
    img.save(os.path.join(outdir, track1))

    out = text.replace(f'FILE "{names[0]}"', f'FILE "{track1}"', 1)
    for i, n in enumerate(names[1:], 2):
        link = f'track{i:02d}.bin'
        dst = os.path.join(outdir, link)
        if not os.path.exists(dst):
            os.link(os.path.join(srcdir, n), dst)
        out = out.replace(f'FILE "{n}"', f'FILE "{link}"')
    with open(os.path.join(outdir, 'cce.cue'), 'w') as f:
        f.write(out)
    print(f'patched {len(patched)} file(s): {", ".join(sorted(patched)) or "none"}')


if __name__ == '__main__':
    main()
