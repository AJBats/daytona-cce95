"""Build a patched CCE disc: copy the original data track, overwrite files in
place with replacements from a patch directory, regenerate EDC/ECC, and emit a
cue sheet whose audio tracks are hard links to the original image's tracks
(Mednafen on Windows does not follow '..' paths inside a cue).

usage: mkdisc.py <orig.cue> <patchdir> <outdir> [--append <cue> <track>...]

A replacement may not outgrow the sectors the original file occupies. Only
the files listed in <patchdir>/PATCHED.txt are used. --append adds audio
tracks from another disc's cue after the last track, in the order given
(DUSA's attract song and jingle, docs/attract.md), hard-linked like the
others.
"""
import os
import re
import sys

from cdimage import Image


def cue_tracks(cue):
    """{track number: (file name, track type, its FILE block)} of a cue sheet."""
    text = open(cue).read()
    blocks = re.split(r'(?=^FILE )', text, flags=re.M)
    out = {}
    for b in blocks:
        m = re.search(r'FILE "([^"]+)"[^\n]*\n\s*TRACK (\d+) (\S+)', b)
        if m:
            out[int(m.group(2))] = (m.group(1), m.group(3), b)
    return out


def main():
    args = sys.argv[1:]
    extra = []
    if '--append' in args:
        i = args.index('--append')
        extra_cue, extra = args[i + 1], [int(t) for t in args[i + 2:]]
        args = args[:i]
    cue, patchdir, outdir = args[:3]
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
    n = len(names)
    if extra:
        src = cue_tracks(extra_cue)
        for t in extra:
            name, kind, block = src[t]
            if kind != 'AUDIO':
                sys.exit(f'error: track {t} of {extra_cue} is not audio')
            n += 1
            link = f'track{n:02d}.bin'
            dst = os.path.join(outdir, link)
            if not os.path.exists(dst):
                os.link(os.path.join(os.path.dirname(os.path.abspath(extra_cue)), name), dst)
            block = block.replace(f'FILE "{name}"', f'FILE "{link}"')
            block = re.sub(r'TRACK \d+ AUDIO', f'TRACK {n:02d} AUDIO', block)
            out = out.rstrip('\n') + '\n' + block.rstrip('\n') + '\n'
    with open(os.path.join(outdir, 'cce.cue'), 'w') as f:
        f.write(out)
    print(f'patched {len(patched)} file(s): {", ".join(sorted(patched)) or "none"}'
          + (f'; appended tracks {", ".join(map(str, extra))} as {len(names) + 1}-{n}' if extra else ''))


if __name__ == '__main__':
    main()
