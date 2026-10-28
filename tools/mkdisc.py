"""Build a patched CCE disc: copy the original data track, overwrite files in
place with replacements from a patch directory, regenerate EDC/ECC, and emit a
cue sheet whose audio tracks are hard links to the original image's tracks
(Mednafen on Windows does not follow '..' paths inside a cue).

usage: mkdisc.py <orig.cue> <patchdir> <outdir> [--append <cue> <track>...]

A replacement that fits the sectors the original file occupies is written
in place. One that outgrows them moves to the end of the data track's
files: the track grows, keeping its 150 empty sectors before the audio,
the file's directory record points at its new place, and every directory
record past the track (CCE's CDDA* files, which NAMED.BIN and RESULT2P.BIN
open by name to play music) and the volume size move with the audio
tracks. CCE opens its files by name (GFS), so a moved file is found where
the directory says. A file not on the disc is added the same way, at the
end of the files, with a record after the last one of its directory (in
that directory's last sector, which must have room; records keep their
order, so GFS's file numbers of the files already there don't change; its
directory table holds 256, DAYTONA has 205). Only the files listed in <patchdir>/PATCHED.txt are
used. --append adds audio
tracks from another disc's cue after the last track, in the order given
(DUSA's attract song and jingle, docs/attract.md), hard-linked like the
others.
"""
import os
import re
import sys

from cdimage import Image, SECTOR, USER


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
    records = {p: (lba, size, at) for p, lba, size, at in img.records()}
    track = len(img.raw) // SECTOR
    data_end = max(lba + (size + USER - 1) // USER for lba, size, _ in records.values() if lba < track)
    patched, moved, added = [], [], []
    listing = os.path.join(patchdir, 'PATCHED.txt')
    wanted = open(listing).read().split() if os.path.exists(listing) else []
    cursor = data_end
    dirs = img.directories()
    for rel in wanted:
        data = open(os.path.join(patchdir, rel), 'rb').read()
        if rel not in records:
            directory, _, name = rel.rpartition('/')
            if directory + '/' not in dirs and directory:
                sys.exit(f'error: {rel}: no directory {directory} on the disc')
            lba = cursor
            cursor += (len(data) + USER - 1) // USER
            img.extend(cursor + track - data_end)
            img.write(lba, data)
            img.add_record(directory + '/' if directory else '', name, lba, len(data))
            added.append(f'{rel} at sector {lba}')
            patched.append(rel)
            continue
        lba, size, at = records[rel]
        if len(data) > (size + USER - 1) // USER * USER:
            lba = cursor
            cursor += (len(data) + USER - 1) // USER
            img.extend(cursor + track - data_end)
            moved.append(f'{rel} to sector {lba}')
        img.write(lba, data)
        if (lba, len(data)) != records[rel][:2]:
            img.set_extent(at, lba, len(data))
        patched.append(rel)
    shift = len(img.raw) // SECTOR - track
    if shift:
        for lba, size, at in records.values():
            if lba >= track:
                img.set_extent(at, lba + shift, size)
        img.volume_size(img.volume_size() + shift)

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
          + (f'; added {", ".join(added)}' if added else '')
          + (f'; moved {", ".join(moved)}' if moved else '')
          + (f', data track +{shift} sectors' if shift else '')
          + (f'; appended tracks {", ".join(map(str, extra))} as {len(names) + 1}-{n}' if extra else ''))


if __name__ == '__main__':
    main()
