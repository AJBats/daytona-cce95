"""The release patch: what the disc builder (patcher/) needs to turn a player's own
Daytona USA and Daytona USA - Circuit Edition (Japan) discs into ours, without the
patch carrying either disc.

usage: make_release_patch.py <cce.cue> <dusa.cue> <built disc dir> <out.patch> [<dump.zip>...]
                             [--option <id>=<default> <value>:<built disc dir>...]...

<dusa.cue> is Daytona USA (USA), the disc ours is built from. Each zip is a rip
of another region's Daytona USA the builder should take too, read without
unpacking. The built disc is the one with every option at its default; each
--option names one of the disc's options (docs/options.md), its default, and
for each other value the disc built with that value and the other options at
their defaults (Makefile release-patch).

The built disc (tools/mkdisc.py) is CCE's data track with some sectors rewritten
or added, and audio tracks each the same as one of CCE's or DUSA's (DUSA's in
place of some of CCE's and after them, docs/music.md).
So the patch holds:
  - every needed track of both discs, by size and SHA-1, to check the player's;
    for DUSA, those of each dump it takes, with its name and product number;
  - the data track's sector count and the list of sectors that differ from
    CCE's (all Mode 1: the builder writes their sync, header, EDC and ECC);
  - those sectors' 2048 data bytes, as copies from CCE's and DUSA (USA)'s data
    tracks (their data bytes, one after the other) where they match, and the
    bytes themselves where nothing does;
  - the ranges of DUSA (USA)'s data bytes those copies read, and the SHA-1 of
    the ranges' bytes one after the other;
  - for each other dump, a fixup that makes those bytes from its own data bytes
    (its files lie elsewhere on the disc, and a few differ);
  - where each output track comes from, the cue sheet, and the SHA-1 of the
    data track it must come out as. Every audio track takes its INDEX lines
    from the disc it comes from (a DUSA dump's own, as their pregaps differ):
    the cue has @nn:INDEX@ in their place, and the header CCE's and each
    dump's lines for the tracks we take;
  - for each option's other values, what differs from the default disc: the
    data track's changed bytes (in the 2048 data bytes of its sectors; the
    builder writes the sectors' EDC and ECC again) and its SHA-1 with only
    that option changed, and the tracks that come from elsewhere. Options
    change different bytes and tracks, so the builder can take any mix.

File: b'DUSAULT\\x03', a little-endian u32 header length, the header (JSON), then
zlib streams one after another: the copy list, then each other dump's fixup. The
header gives each stream's place as [offset, length] from the end of the header.
Each stream is repeated [varint n, n literal bytes, varint m, varint offset if m]
until the data is complete (copy m bytes from that offset of the source)."""
import hashlib
import json
import os
import posixpath
import re
import struct
import sys
import zipfile
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdimage import SECTOR, USER, HDR, fix_sector  # noqa: E402
from mkdisc import RING_CAP  # noqa: E402

BLOCK = 32                                   # the shortest copy looked for


class Dump:
    """A disc: its cue sheet with the track files beside it, or a zip of them."""

    def __init__(self, path):
        if path.lower().endswith('.zip'):
            self.zip = zipfile.ZipFile(path)
            cue = next(n for n in self.zip.namelist() if n.lower().endswith('.cue'))
            text = self.zip.read(cue).decode()
            self.dir = posixpath.dirname(cue)
        else:
            self.zip = None
            cue = path
            text = open(path).read()
            self.dir = os.path.dirname(os.path.abspath(path))
        self.name = os.path.splitext(os.path.basename(cue))[0]
        self.cue = text.replace('\r\n', '\n')
        self.files = {int(num): name for name, num in re.findall(r'FILE "([^"]+)"[^\n]*\n\s*TRACK (\d+)', self.cue)}

    def read(self, n, size=-1):
        """Track n's file; its first size bytes if size is given."""
        if self.zip:
            with self.zip.open(posixpath.join(self.dir, self.files[n])) as f:
                return f.read(size)
        with open(os.path.join(self.dir, self.files[n]), 'rb') as f:
            return f.read(size)

    def info(self, n):
        return track_info(self.read(n))

    def product(self):
        """The product number in the disc header."""
        return self.read(1, SECTOR)[HDR + 0x20:HDR + 0x2A].decode().strip()

    def index(self):
        """{track number: its INDEX lines} of the cue sheet."""
        out, n = {}, None
        for line in self.cue.splitlines():
            words = line.split()
            if words[:1] == ['TRACK']:
                n = int(words[1])
                out[n] = []
            elif words[:1] == ['INDEX'] and n is not None:
                out[n].append(' '.join(words))
        return out


def track_info(data):
    return {'size': len(data), 'sha1': hashlib.sha1(data).hexdigest()}


def user_data(raw):
    a = np.frombuffer(raw, np.uint8).reshape(-1, SECTOR)
    return a[:, HDR:HDR + USER].reshape(-1)


def mode1_sector(lba, payload):
    m, s = divmod(lba + 150, 75 * 60)
    s, f = divmod(s, 75)
    bcd = lambda v: (v // 10) << 4 | v % 10
    sec = bytearray(SECTOR)
    sec[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    sec[12:16] = bytes([bcd(m), bcd(s), bcd(f), 1])
    sec[HDR:HDR + USER] = payload
    return bytes(fix_sector(sec))


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def encode(ops):
    """A copy list as the patch stores it."""
    out = bytearray()
    for lit, n, q in ops:
        out += varint(len(lit)) + lit + varint(n) + (varint(q) if n else b'')
    return bytes(out)


# ---------------------------------------------------------------- matching

P = np.uint64(0x100000001B3)


def powers(n):
    pw = np.empty(n, np.uint64)
    pw[0] = 1
    if n > 1:
        pw[1:] = np.multiply.accumulate(np.full(n - 1, P, np.uint64))
    return pw


def block_hashes(s):
    """Hash of every BLOCK-aligned block of s: sum of byte * P**j."""
    m = len(s) // BLOCK
    pw = powers(BLOCK)
    out = np.empty(m, np.uint64)
    step = 1 << 16
    for i in range(0, m, step):
        blk = s[i * BLOCK:min(m, i + step) * BLOCK].reshape(-1, BLOCK).astype(np.uint64)
        out[i:i + len(blk)] = (blk * pw).sum(1)
    return out


def window_hashes(t):
    """The same hash of the BLOCK bytes at every position of t."""
    n = len(t) - BLOCK + 1
    if n <= 0:
        return np.empty(0, np.uint64)
    pw = powers(len(t) + 1)
    pref = np.zeros(len(t) + 1, np.uint64)
    pref[1:] = np.cumsum(t.astype(np.uint64) * pw[:len(t)])
    inv = pow(int(P), -1, 1 << 64)
    ipw = np.empty(n, np.uint64)
    ipw[0] = 1
    if n > 1:
        ipw[1:] = np.multiply.accumulate(np.full(n - 1, np.uint64(inv), np.uint64))
    return (pref[BLOCK:BLOCK + n] - pref[:n]) * ipw


def match_len(t, p, s, q):
    """How many bytes from t[p] and s[q] on are equal."""
    n = 0
    lim = min(len(t) - p, len(s) - q)
    step = 4096
    while n < lim:
        k = min(step, lim - n)
        ne = np.flatnonzero(t[p + n:p + n + k] != s[q + n:q + n + k])
        if len(ne):
            return n + int(ne[0])
        n += k
    return n


def delta(t, s):
    """[(literal bytes, copy length, copy offset)] that make t from s."""
    hs = block_hashes(s)
    order = np.argsort(hs, kind='stable')
    sorted_h = hs[order]
    ht = window_hashes(t)
    idx = np.searchsorted(sorted_h, ht)
    idx = np.minimum(idx, len(sorted_h) - 1)
    hit = sorted_h[idx] == ht
    cand = np.flatnonzero(hit)
    ops = []
    lit_from = p = 0
    ci = 0
    while ci < len(cand):
        p = int(cand[ci])
        if p < lit_from:
            ci = int(np.searchsorted(cand, lit_from))
            continue
        q = int(order[idx[p]]) * BLOCK
        n = match_len(t, p, s, q)
        if n < BLOCK:
            ci += 1
            continue
        back = 0                                     # grow the copy back into the literal
        while p - back > lit_from and q - back > 0 and t[p - back - 1] == s[q - back - 1]:
            back += 1
        ops.append((t[lit_from:p - back].tobytes(), n + back, q - back))
        lit_from = p + n
        ci = int(np.searchsorted(cand, lit_from))
    ops.append((t[lit_from:].tobytes(), 0, 0))
    return ops


def apply(ops, s):
    out = bytearray()
    for lit, n, q in ops:
        out += lit
        out += s[q:q + n].tobytes()
    return bytes(out)


# ---------------------------------------------------------------- options

def byte_runs(a, b, gap=8):
    """[[offset, hex]] of the bytes of b that differ from a's, runs closer than gap merged."""
    diff = np.flatnonzero(np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8))
    runs = []
    for i in diff.tolist():
        if runs and i - runs[-1][1] <= gap:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1])
    return [[lo, b[lo:hi].hex()] for lo, hi in runs]


def track01_changes(base, variant):
    """The data bytes of variant's data track that differ from base's, by sector."""
    if len(base) != len(variant):
        sys.exit('error: an option changes the data track\'s length')
    out = []
    for lba in range(len(base) // SECTOR):
        a, b = base[lba * SECTOR:(lba + 1) * SECTOR], variant[lba * SECTOR:(lba + 1) * SECTOR]
        if a == b:
            continue
        if mode1_sector(lba, b[HDR:HDR + USER]) != b:
            sys.exit(f'error: an option\'s sector {lba} is not a plain Mode 1 sector')
        out.append([lba, byte_runs(a[HDR:HDR + USER], b[HDR:HDR + USER])])
    return out


def apply_changes(track, changes):
    out = bytearray(track)
    for lba, runs in changes:
        user = bytearray(out[lba * SECTOR + HDR:lba * SECTOR + HDR + USER])
        for at, data in runs:
            data = bytes.fromhex(data)
            user[at:at + len(data)] = data
        out[lba * SECTOR:(lba + 1) * SECTOR] = mode1_sector(lba, bytes(user))
    return bytes(out)


def parse_args(args):
    """(positional args, [(option id, default, [(value, built disc dir)])])"""
    pos, options = [], []
    i = 0
    while i < len(args):
        if args[i] == '--option':
            oid, default = args[i + 1].split('=')
            values = []
            i += 2
            while i < len(args) and not args[i].startswith('--'):
                value, built = args[i].split(':', 1)
                values.append((value, built))
                i += 1
            options.append((oid, default, values))
        else:
            pos.append(args[i])
            i += 1
    return pos, options


# ---------------------------------------------------------------- main

def main():
    pos, option_args = parse_args(sys.argv[1:])
    if len(pos) < 4:
        sys.exit(__doc__)
    cce_cue, dusa_cue, built, out = pos[:4]
    cce, dusa, made = Dump(cce_cue), Dump(dusa_cue), Dump(os.path.join(built, 'cce.cue'))
    others = sorted((Dump(p) for p in pos[4:]), key=lambda d: d.name)

    # where each of our tracks comes from: track 1 rebuilt, the rest the same as one of theirs
    info = {('cce', n): cce.info(n) for n in cce.files}
    info.update({('dusa', n): dusa.info(n) for n in dusa.files if n > 1})
    source_index = {'cce': cce.index(), 'dusa': dusa.index()}

    def layout_of(disc):
        lay = []
        index = disc.index()
        for n in sorted(disc.files):
            if n == 1:
                lay.append({'track': 1, 'from': 'patch'})
                continue
            sha = disc.info(n)['sha1']
            src = next((k for k, v in info.items() if v['sha1'] == sha), None)
            if src is None:
                sys.exit(f'error: built track {n} is none of the source tracks')
            if index[n] != source_index[src[0]][src[1]]:
                sys.exit(f'error: built track {n} has other INDEX lines than {src[0]} track {src[1]}')
            lay.append({'track': n, 'from': src[0], 'src': src[1]})
        return lay

    def sectors(disc):
        return sum(len(disc.read(n)) // SECTOR for n in disc.files)

    layout = layout_of(made)
    if sectors(made) > RING_CAP:
        sys.exit(f'error: {built} runs {sectors(made)} sectors, past {RING_CAP}')
    # each option's other values: discs of their own, as changes from the default one
    variants = []                                    # (option, value, Dump)
    for oid, default, values in option_args:
        for value, vdir in values:
            variants.append((oid, value, Dump(os.path.join(vdir, 'cce.cue'))))
    options, seen_tracks, seen_bytes = [], {}, {}
    target = made.read(1)
    layouts = [layout]
    for oid, default, values in option_args:
        entry = {'id': oid, 'default': default, 'values': [{'id': default}]}
        for value, vdir in values:
            disc = next(d for o, v, d in variants if (o, v) == (oid, value))
            if sorted(disc.files) != sorted(made.files):
                sys.exit(f'error: {oid}={value} has other track numbers than the default disc')
            if sectors(disc) > RING_CAP:
                sys.exit(f'error: {oid}={value} runs {sectors(disc)} sectors, past {RING_CAP}')
            lay = layout_of(disc)
            layouts.append(lay)
            moved = [e for e, b in zip(lay, layout) if e != b]
            for e in moved:
                if seen_tracks.setdefault(e['track'], oid) != oid:
                    sys.exit(f'error: options {seen_tracks[e["track"]]} and {oid} both change track {e["track"]}')
            vt = disc.read(1)
            changes = track01_changes(target, vt)
            if apply_changes(target, changes) != vt:
                sys.exit(f'error: {oid}={value}: the changes do not make its data track')
            for lba, runs in changes:
                for at, data in runs:
                    for k in range(at, at + len(data) // 2):
                        if seen_bytes.setdefault((lba, k), oid) != oid:
                            sys.exit(f'error: options {seen_bytes[lba, k]} and {oid} both change sector {lba}')
            entry['values'].append({'id': value, 'layout': moved,
                                    'track01': {'sha1': hashlib.sha1(vt).hexdigest(), 'changes': changes}})
            print(f'option {oid}={value}: {len(moved)} tracks from elsewhere, {len(changes)} sectors of the '
                  f'data track changed ({sum(len(d) // 2 for _, r in changes for _, d in r)} bytes)')
        options.append(entry)
    from_dusa = [e for lay in layouts for e in lay if e['from'] == 'dusa']
    needed_dusa = sorted({1} | {e['src'] for e in from_dusa})
    dusa_srcs = sorted({e['src'] for e in from_dusa})
    cce_srcs = sorted({e['src'] for lay in layouts for e in lay if e['from'] == 'cce'})

    # the data track: the sectors that differ from CCE's, as Mode 1 sectors
    base = cce.read(1)
    dusa1 = dusa.read(1)
    target = made.read(1)
    nb, nt = len(base) // SECTOR, len(target) // SECTOR
    dirty = []
    for lba in range(nt):
        sec = target[lba * SECTOR:(lba + 1) * SECTOR]
        if lba < nb and sec == base[lba * SECTOR:(lba + 1) * SECTOR]:
            continue
        if mode1_sector(lba, sec[HDR:HDR + USER]) != sec:
            sys.exit(f'error: built sector {lba} is not a plain Mode 1 sector')
        dirty.append(lba)
    runs = []
    for lba in dirty:
        if runs and runs[-1][0] + runs[-1][1] == lba:
            runs[-1][1] += 1
        else:
            runs.append([lba, 1])
    t = user_data(target)[np.repeat(np.array(dirty) * USER, USER) + np.tile(np.arange(USER), len(dirty))]
    cce_user, dusa_user = user_data(base), user_data(dusa1)
    s = np.concatenate([cce_user, dusa_user])
    ops = delta(t, s)
    if apply(ops, s) != t.tobytes():
        sys.exit('error: the copy list does not make the data back')

    # the ranges of DUSA (USA)'s data bytes the copies read, merged
    k = len(cce_user)
    ranges = []
    for a, b in sorted((max(q, k) - k, q + n - k) for _, n, q in ops if n and q + n > k):
        if ranges and a <= ranges[-1][1]:
            ranges[-1][1] = max(ranges[-1][1], b)
        else:
            ranges.append([a, b])
    ranges = [[a, b - a] for a, b in ranges]
    wanted = np.concatenate([dusa_user[a:a + n] for a, n in ranges])

    # the copy list, then each other dump's fixup: zlib streams one after another
    streams = bytearray()

    def put(data):
        z = zlib.compress(data, 9)
        streams.extend(z)
        return [len(streams) - len(z), len(z)]

    copy_list = put(encode(ops))

    # DUSA's tracks of ours take the dump's own INDEX lines (layout_of checked the built cue has USA's)
    dumps = []
    fixups = {}                                  # by data track SHA-1: dumps may share one
    for d in [dusa] + others:
        tracks = {str(n): d.info(n) for n in needed_dusa}
        if any(tracks == g['tracks'] for g in dumps):
            print(f'{d.name}: the same tracks as a dump before it, left out')
            continue
        index = d.index()
        entry = {'name': d.name, 'product': d.product(), 'tracks': tracks,
                 'fixup': None, 'index': {str(n): index[n] for n in dusa_srcs}}
        if d is not dusa and tracks['1']['sha1'] not in fixups:
            u = user_data(d.read(1))
            fops = delta(wanted, u)
            if apply(fops, u) != wanted.tobytes():
                sys.exit(f'error: the fixup for {d.name} does not make the data back')
            fixups[tracks['1']['sha1']] = {'ops': put(encode(fops)), 'copied': sum(n for _, n, _ in fops),
                                           'literal': sum(len(lit) for lit, _, _ in fops)}
        if d is not dusa:
            entry['fixup'] = fixups[tracks['1']['sha1']]
        dumps.append(entry)

    # the rebuilt data track, as the builder will make it
    rebuilt = bytearray(base[:nt * SECTOR] if nt <= nb else base + bytes((nt - nb) * SECTOR))
    tb = t.tobytes()
    for k, lba in enumerate(dirty):
        rebuilt[lba * SECTOR:(lba + 1) * SECTOR] = mode1_sector(lba, tb[k * USER:(k + 1) * USER])
    if bytes(rebuilt) != target:
        sys.exit('error: the rebuilt data track differs from the built one')

    cue = made.cue
    for n, name in made.files.items():
        cue = cue.replace(f'FILE "{name}"', f'FILE "@{n:02d}@"')
    for e in layout[1:]:
        tn = f'{e["track"]:02d}'
        cue, hits = re.subn(rf'(TRACK {tn} AUDIO\n)(?:[ \t]*INDEX [^\n]*\n)+', rf'\g<1>@{tn}:INDEX@\n', cue)
        if hits != 1:
            sys.exit(f'error: no INDEX lines for track {tn} in the built cue')
    copied = sum(n for _, n, _ in ops)
    literal = sum(len(lit) for lit, _, _ in ops)
    cce_index = cce.index()
    header = {
        'format': 3,
        'title': 'Daytona USA Ultimate',
        'cce': {'name': cce.name, 'product': cce.product(),
                'tracks': {str(n): info[('cce', n)] for n in sorted(cce.files)},
                'index': {str(n): cce_index[n] for n in cce_srcs}},
        'dusa': dumps,
        'dusa_ranges': {'data': len(dusa_user), 'ranges': ranges, 'sha1': hashlib.sha1(wanted).hexdigest()},
        'source': ['cce:1', 'dusa:1'],
        'track01': {'sectors': nt, 'dirty': runs, 'data': len(t), 'sha1': hashlib.sha1(target).hexdigest(),
                    'copied': copied, 'literal': literal, 'ops': copy_list},
        'layout': layout,
        'options': options,
        'cue': cue,
    }
    hj = json.dumps(header, indent=1).encode()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(b'DUSAULT\x03' + struct.pack('<I', len(hj)) + hj + bytes(streams))
    print(f'{len(dirty)} of {nt} sectors rebuilt ({len(t) // 1024} KB of data): '
          f'{copied // 1024} KB copied from the discs, {literal // 1024} KB new')
    print(f'{dusa.name}: {len(ranges)} ranges of its data track read, {len(wanted)} bytes')
    for g in dumps[1:]:
        fx = g['fixup']
        print(f'{g["name"]} ({g["product"]}): fixup {fx["literal"]} bytes new, '
              f'{fx["ops"][1]} bytes packed at {fx["ops"][0]}')
    print(f'patch {os.path.getsize(out) // 1024} KB (header {len(hj) // 1024} KB)')


if __name__ == '__main__':
    main()
