"""The release patch: what the disc builder (patcher/) needs to turn a player's own
Daytona USA and Daytona USA - Circuit Edition (Japan) discs into ours, without the
patch carrying either disc.

usage: make_release_patch.py <cce.cue> <dusa.cue> <built disc dir> <out.patch> [<dump.zip>...]

<dusa.cue> is Daytona USA (USA), the disc ours is built from. Each zip is another
Redump dump of Daytona USA the builder should take too, read without unpacking.

The built disc (tools/mkdisc.py) is CCE's data track with some sectors rewritten
or added, CCE's audio tracks unchanged, and two of DUSA's audio tracks appended.
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
    data track it must come out as. The INDEX lines of the tracks taken from
    DUSA are left to the dump used (its own, as their pregaps differ): the cue
    has @nn:INDEX@ in their place.

File: b'DUSAULT\\x02', a little-endian u32 header length, the header (JSON), then
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


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    cce_cue, dusa_cue, built, out = sys.argv[1:5]
    cce, dusa, made = Dump(cce_cue), Dump(dusa_cue), Dump(os.path.join(built, 'cce.cue'))
    others = sorted((Dump(p) for p in sys.argv[5:]), key=lambda d: d.name)

    # where each of our tracks comes from: track 1 rebuilt, the rest the same as one of theirs
    info = {('cce', n): cce.info(n) for n in cce.files}
    info.update({('dusa', n): dusa.info(n) for n in dusa.files if n <= 3})
    layout = []
    for n in sorted(made.files):
        if n == 1:
            layout.append({'track': 1, 'from': 'patch'})
            continue
        sha = made.info(n)['sha1']
        src = next((k for k, v in info.items() if v['sha1'] == sha), None)
        if src is None:
            sys.exit(f'error: built track {n} is none of the source tracks')
        layout.append({'track': n, 'from': src[0], 'src': src[1]})
    from_dusa = [e for e in layout if e['from'] == 'dusa']
    needed_dusa = sorted({1} | {e['src'] for e in from_dusa})

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

    # DUSA's tracks of ours take the dump's own INDEX lines: the built cue has (USA)'s
    usa_index, made_index = dusa.index(), made.index()
    for e in from_dusa:
        if made_index[e['track']] != usa_index[e['src']]:
            sys.exit(f'error: built track {e["track"]} has other INDEX lines than {dusa.name} track {e["src"]}')
    dumps = []
    fixups = {}                                  # by data track SHA-1: dumps may share one
    for d in [dusa] + others:
        tracks = {str(n): d.info(n) for n in needed_dusa}
        if any(tracks == g['tracks'] for g in dumps):
            print(f'{d.name}: the same tracks as a dump before it, left out')
            continue
        index = d.index()
        entry = {'name': d.name, 'product': d.product(), 'tracks': tracks,
                 'fixup': None, 'index': {str(e['src']): index[e['src']] for e in from_dusa}}
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
    for e in from_dusa:
        tn = f'{e["track"]:02d}'
        cue, hits = re.subn(rf'(TRACK {tn} AUDIO\n)(?:[ \t]*INDEX [^\n]*\n)+', rf'\g<1>@{tn}:INDEX@\n', cue)
        if hits != 1:
            sys.exit(f'error: no INDEX lines for track {tn} in the built cue')
    copied = sum(n for _, n, _ in ops)
    literal = sum(len(lit) for lit, _, _ in ops)
    header = {
        'format': 2,
        'title': 'Daytona USA Ultimate',
        'cce': {'name': cce.name, 'product': cce.product(),
                'tracks': {str(n): info[('cce', n)] for n in sorted(cce.files)}},
        'dusa': dumps,
        'dusa_ranges': {'data': len(dusa_user), 'ranges': ranges, 'sha1': hashlib.sha1(wanted).hexdigest()},
        'source': ['cce:1', 'dusa:1'],
        'track01': {'sectors': nt, 'dirty': runs, 'data': len(t), 'sha1': hashlib.sha1(target).hexdigest(),
                    'copied': copied, 'literal': literal, 'ops': copy_list},
        'layout': layout,
        'cue': cue,
    }
    hj = json.dumps(header, indent=1).encode()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(b'DUSAULT\x02' + struct.pack('<I', len(hj)) + hj + bytes(streams))
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
