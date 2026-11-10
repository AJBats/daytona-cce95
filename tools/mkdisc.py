"""Build a patched CCE disc: copy the original data track, overwrite files in
place with replacements from a patch directory, regenerate EDC/ECC, and emit a
cue sheet whose audio tracks are hard links to the original image's tracks
(Mednafen on Windows does not follow '..' paths inside a cue).

usage: mkdisc.py <orig.cue> <patchdir> <outdir> [--from <cue> <slot>=<track>...]

A replacement that fits the sectors the original file occupies is written
in place. One that outgrows them moves to the end of the data track's
files: the track grows, keeping its 150 empty sectors before the audio,
the file's directory record points at its new place, and every directory
record past the track (CCE's CDDA* files, which NAMED.BIN and RESULT2P.BIN
open by name to play music) and the volume size move with the audio
tracks. CCE opens its files by name (GFS), so a moved file is found where
the directory says. A file not on the disc is added the same way, at the
end of the files, with a record after the last one of its directory, in
that directory's last sector. Records keep their order, so GFS's file
numbers of the files already there don't change; its directory table holds
256, CCE's DAYTONA has 205. When the last sector is full, the directory
moves to the end of the files with one more sector (its record in the
root, its '.' record and the path tables follow; the old copy stays where
it was). Only the files listed in <patchdir>/PATCHED.txt are used.

--from takes audio tracks from another disc's cue (DUSA's music,
docs/music.md): <slot>=<track> puts that disc's track in our track <slot>,
in place of CCE's track there, or after the last one (the slots past CCE's
come in order, no gaps). They are hard-linked like CCE's, with their own
INDEX lines. CCE's root directory has a record per audio track (CDDA2 to
CDDA31: the track's INDEX 01 and its length from there, 2048 bytes a
sector); they follow their tracks to wherever the new layout puts them,
and the volume ends where track 31 does. CCE plays its music by track
number, not through these. The disc must fit an 80-minute CD-R.

The disc boots in every region (region_free).
"""
import os
import re
import sys

from cdimage import DirectoryFull, Image, SECTOR, USER

# The Saturn BIOS boots a disc only where it lists the console's area: the
# header's area symbols, and after the security code one block per area (a
# branch over the area's string, which the BIOS compares with its own) ahead
# of the boot program. The strings as both BIOS images hold them.
AREAS = (('J', 'For JAPAN.'), ('T', 'For TAIWAN and PHILIPINES.'), ('U', 'For USA and CANADA.'),
         ('B', 'For BRAZIL.'), ('K', 'For KOREA.'), ('A', 'For ASIA PAL area.'),
         ('E', 'For EUROPE.'), ('L', 'For LATIN AMERICA.'))
SYMBOLS = 'UJTBKAEL'   # emulators that boot as the first area listed pick a US console
AREA_BLOCKS = 0xE00
# A file here that outgrows its sectors stays where it is, and the unchanged files right after it on
# the disc move to the end instead. SCREEN.BIN (grown by tools/vdp1x.py's block) is read at every race
# start right after RACE.BIN, its neighbour before it; RESULT.BIN only at a race's end. These go
# after the rest, so what moves for them moves no other file (the menus' files keep their places and
# timings, as tools/vdp1_lap.py's frame-exact menu inputs expect).
MAKE_ROOM = {'DAYTONA/SCREEN.BIN': ('DAYTONA/RESULT.BIN',)}
BLOCK_HEAD = bytes.fromhex('a00e0009')   # bra over the string; nop
CDR_80 = 359849                          # sectors on an 80-minute CD-R


def region_free(img):
    """List all eight areas in the disc's header (sectors 0-1). The boot program
    after the blocks moves down with them; it is position-independent, and the
    move is a multiple of 4 bytes, so its PC-relative loads still line up."""
    ip = bytearray(img.read(0, 2))
    ip_size = int.from_bytes(ip[0xE0:0xE4], 'big')
    end = AREA_BLOCKS
    while ip[end:end + 4] == BLOCK_HEAD:
        end += 0x20
    used = max(i for i in range(end, ip_size) if ip[i]) + 1
    boot = bytes(ip[end:(used + 3) & ~3])
    blocks = b''.join(BLOCK_HEAD + text.ljust(28).encode() for _, text in AREAS)
    if AREA_BLOCKS + len(blocks) + len(boot) > ip_size:
        sys.exit('error: no room in the disc header for every area block')
    ip[AREA_BLOCKS:ip_size] = (blocks + boot).ljust(ip_size - AREA_BLOCKS, b'\0')
    ip[0x40:0x50] = SYMBOLS.ljust(16).encode()
    img.write(0, bytes(ip))


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


def index01(block):
    """A track's INDEX 01, in sectors from the start of its file."""
    m, s, f = map(int, re.search(r'INDEX 01 (\d\d):(\d\d):(\d\d)', block).groups())
    return (m * 60 + s) * 75 + f


def link(src, dst):
    """dst becomes a hard link to src, replacing what was there (a link from an earlier build)."""
    if os.path.exists(dst) and os.path.samefile(src, dst):
        return
    tmp = dst + '.tmp'
    if os.path.exists(tmp):
        os.replace(tmp, dst)          # left from an interrupted build: it is about to be replaced again
    os.link(src, tmp)
    os.replace(tmp, dst)


def main():
    args = sys.argv[1:]
    takes = {}
    if '--from' in args:
        i = args.index('--from')
        other_cue = args[i + 1]
        for word in args[i + 2:]:
            slot, t = word.split('=')
            takes[int(slot)] = int(t)
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
    wanted.sort(key=lambda rel: rel in MAKE_ROOM)
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
            path = directory + '/' if directory else ''
            try:
                img.add_record(path, name, lba, len(data))
            except DirectoryFull:
                at = cursor
                cursor += img.directories()[path][1] // USER + 1
                img.extend(cursor + track - data_end)
                img.move_directory(path, at)
                moved.append(f'{path} to sector {at}, a sector longer')
                img.add_record(path, name, lba, len(data))
                # the disc's own files' records now live in the copy
                now = {p: at_ for p, _, _, at_ in img.records()}
                records = {p: (lba_, size_, now[p]) for p, (lba_, size_, _) in records.items()}
            added.append(f'{rel} at sector {lba}')
            patched.append(rel)
            continue
        lba, size, at = records[rel]
        room = (size + USER - 1) // USER
        for nb in MAKE_ROOM.get(rel, ()):
            nlba, nsize, nat = records[nb]
            if len(data) <= room * USER or nlba != lba + room or nb in wanted:
                break
            n = (nsize + USER - 1) // USER
            blob = img.read(nlba, n)[:nsize]
            img.extend(cursor + n + track - data_end)
            img.write(cursor, blob)
            img.set_extent(nat, cursor, nsize)
            moved.append(f'{nb} to sector {cursor}, making room for {rel}')
            cursor += n
            room += n
        if len(data) > room * USER:
            lba = cursor
            cursor += (len(data) + USER - 1) // USER
            img.extend(cursor + track - data_end)
            moved.append(f'{rel} to sector {lba}')
        img.write(lba, data)
        if (lba, len(data)) != records[rel][:2]:
            img.set_extent(at, lba, len(data))
        patched.append(rel)
    # the audio tracks: CCE's, with --from's in their slots or after them
    cce_tracks = cue_tracks(cue)
    audio = {n: (os.path.join(srcdir, name), block) for n, (name, _, block) in cce_tracks.items() if n > 1}
    if takes:
        other = cue_tracks(other_cue)
        otherdir = os.path.dirname(os.path.abspath(other_cue))
        for slot in sorted(takes):
            name, kind, block = other[takes[slot]]
            if kind != 'AUDIO':
                sys.exit(f'error: track {takes[slot]} of {other_cue} is not audio')
            if slot < 2 or slot > max(audio) + 1:
                sys.exit(f'error: track slot {slot}: the slots past the last track come in order')
            audio[slot] = (os.path.join(otherdir, name), block)
    sectors = {n: os.path.getsize(path) // SECTOR for n, (path, _) in audio.items()}

    # CCE's CDDA records follow their tracks; the volume ends with track 31
    new_track = len(img.raw) // SECTOR
    shift = new_track - track
    start, at_ = {}, new_track
    for n in sorted(audio):
        start[n] = at_ + index01(audio[n][1])
        at_ += sectors[n]
    total = at_
    old_start, at_ = {}, track
    for n in sorted(cce_tracks):
        if n > 1:
            old_start[n] = at_ + index01(cce_tracks[n][2])
            at_ += os.path.getsize(os.path.join(srcdir, cce_tracks[n][0])) // SECTOR
    old_end = at_
    last = max(old_start)
    for rel, (lba, size, at) in records.items():
        m = re.fullmatch(r'CDDA(\d+)', rel)
        if m and int(m.group(1)) in start and lba == old_start[int(m.group(1))]:
            n = int(m.group(1))
            end = start[n] - index01(audio[n][1]) + sectors[n]
            img.set_extent(at, start[n], (end - start[n]) * USER)
        elif lba >= track:
            sys.exit(f'error: {rel} lies past the data track but is no CDDA record of a track')
    end_31 = start[last] - index01(audio[last][1]) + sectors[last]
    img.volume_size(img.volume_size() + end_31 - old_end)
    region_free(img)

    track1 = 'track01.bin'
    img.save(os.path.join(outdir, track1))

    head = re.split(r'(?=^FILE )', text, flags=re.M)[0]
    out = head + cce_tracks[1][2].replace(f'FILE "{names[0]}"', f'FILE "{track1}"', 1)
    for n in sorted(audio):
        path, block = audio[n]
        name = f'track{n:02d}.bin'
        link(path, os.path.join(outdir, name))
        block = re.sub(r'FILE "[^"]+"', f'FILE "{name}"', block, count=1)
        block = re.sub(r'TRACK \d+ AUDIO', f'TRACK {n:02d} AUDIO', block)
        out = out.rstrip('\n') + '\n' + block.rstrip('\n') + '\n'
    with open(os.path.join(outdir, 'cce.cue'), 'w') as f:
        f.write(out)
    if total > CDR_80:
        sys.exit(f'error: the disc runs {total} sectors, {total - CDR_80} past an 80-minute CD-R')
    mmss = lambda s: f'{s // 4500}:{s % 4500 / 75:05.2f}'
    print(f'patched {len(patched)} file(s): {", ".join(sorted(patched)) or "none"}'
          + (f'; added {", ".join(added)}' if added else '')
          + (f'; moved {", ".join(moved)}' if moved else '')
          + (f', data track +{shift} sectors' if shift else '')
          + (f'; tracks from {os.path.basename(other_cue)}: '
             + ', '.join(f'{t} as {s}' for s, t in sorted(takes.items())) if takes else '')
          + f'; the disc runs {mmss(total)}, {mmss(CDR_80 - total)} left on an 80-minute CD-R')


if __name__ == '__main__':
    main()
