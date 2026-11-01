"""The release patch: what the disc builder (patcher/) needs to turn a player's own
Daytona USA (USA) and Daytona USA - Circuit Edition (Japan) discs into ours, without
the patch carrying either disc.

usage: make_release_patch.py <cce.cue> <dusa.cue> <built disc dir> <out.patch>

The built disc (tools/mkdisc.py) is CCE's data track with some sectors rewritten
or added, CCE's audio tracks unchanged, and two of DUSA's audio tracks appended.
So the patch holds:
  - every needed track of both discs, by size and SHA-1, to check the player's;
  - the data track's sector count and the list of sectors that differ from
    CCE's (all Mode 1: the builder writes their sync, header, EDC and ECC);
  - those sectors' 2048 data bytes, as copies from CCE's and DUSA's data tracks
    (their data bytes, one after the other) where they match, and the bytes
    themselves where nothing does;
  - where each output track comes from, the cue sheet, and the SHA-1 of the
    data track it must come out as.

File: b'DUSAULT\\x01', a little-endian u32 header length, the header (JSON), then
the copy list compressed with zlib: repeated [varint n, n literal bytes,
varint m, varint offset if m] until the data is complete (copy m bytes from
that offset of the source)."""
import hashlib
import json
import os
import re
import struct
import sys
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdimage import SECTOR, USER, HDR, fix_sector  # noqa: E402

BLOCK = 32                                   # the shortest copy looked for


def cue_files(cue):
    """{track number: bin path} of a cue sheet."""
    text = open(cue).read()
    out = {}
    for name, num in re.findall(r'FILE "([^"]+)"[^\n]*\n\s*TRACK (\d+)', text):
        out[int(num)] = os.path.join(os.path.dirname(os.path.abspath(cue)), name)
    return out


def track_info(path):
    data = open(path, 'rb').read()
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
    cce_cue, dusa_cue, built, out = sys.argv[1:5]
    cce, dusa = cue_files(cce_cue), cue_files(dusa_cue)
    built_cue = os.path.join(built, 'cce.cue')
    built_files = cue_files(built_cue)

    # where each of our tracks comes from: track 1 rebuilt, the rest the same as one of theirs
    info = {('cce', n): track_info(p) for n, p in cce.items()}
    info.update({('dusa', n): track_info(p) for n, p in dusa.items() if n <= 3})
    layout = []
    for n, path in sorted(built_files.items()):
        if n == 1:
            layout.append({'track': 1, 'from': 'patch'})
            continue
        sha = track_info(path)['sha1']
        src = next((k for k, v in info.items() if v['sha1'] == sha), None)
        if src is None:
            sys.exit(f'error: built track {n} is none of the source tracks')
        layout.append({'track': n, 'from': src[0], 'src': src[1]})
    needed_dusa = {1} | {e['src'] for e in layout if e['from'] == 'dusa'}

    # the data track: the sectors that differ from CCE's, as Mode 1 sectors
    base = open(cce[1], 'rb').read()
    dusa1 = open(dusa[1], 'rb').read()
    target = open(built_files[1], 'rb').read()
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
    s = np.concatenate([user_data(base), user_data(dusa1)])
    ops = delta(t, s)
    if apply(ops, s) != t.tobytes():
        sys.exit('error: the copy list does not make the data back')

    # the rebuilt data track, as the builder will make it
    rebuilt = bytearray(base[:nt * SECTOR] if nt <= nb else base + bytes((nt - nb) * SECTOR))
    tb = t.tobytes()
    for k, lba in enumerate(dirty):
        rebuilt[lba * SECTOR:(lba + 1) * SECTOR] = mode1_sector(lba, tb[k * USER:(k + 1) * USER])
    if bytes(rebuilt) != target:
        sys.exit('error: the rebuilt data track differs from the built one')

    cue = open(built_cue).read()
    for n, path in built_files.items():
        cue = cue.replace(f'FILE "{os.path.basename(path)}"', f'FILE "@{n:02d}@"')
    copied = sum(n for _, n, _ in ops)
    literal = sum(len(lit) for lit, _, _ in ops)
    header = {
        'format': 1,
        'title': 'Daytona USA Ultimate',
        'cce': {'name': 'Daytona USA - Circuit Edition (Japan)', 'product': 'GS-9100',
                'tracks': {str(n): info[('cce', n)] for n in sorted(cce)}},
        'dusa': {'name': 'Daytona USA (USA)', 'product': 'MK-81200',
                 'tracks': {str(n): info[('dusa', n)] for n in sorted(needed_dusa)}},
        'source': ['cce:1', 'dusa:1'],
        'track01': {'sectors': nt, 'dirty': runs, 'data': len(t), 'sha1': hashlib.sha1(target).hexdigest(),
                    'copied': copied, 'literal': literal},
        'layout': layout,
        'cue': cue,
    }
    body = bytearray()
    for lit, n, q in ops:
        body += varint(len(lit)) + lit + varint(n) + (varint(q) if n else b'')
    hj = json.dumps(header, indent=1).encode()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(b'DUSAULT\x01' + struct.pack('<I', len(hj)) + hj + zlib.compress(bytes(body), 9))
    print(f'{len(dirty)} of {nt} sectors rebuilt ({len(t) // 1024} KB of data): '
          f'{copied // 1024} KB copied from the discs, {literal // 1024} KB new; '
          f'patch {os.path.getsize(out) // 1024} KB')


if __name__ == '__main__':
    main()
