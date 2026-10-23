"""DUSA's LZSS decompressor (06028654), for textures in TEX_PL.BIN and others.

Flags byte, low bit first: 1 = literal byte; 0 = two bytes b1, b2:
offset = ((b2 | 0xF0) << 8 | b1) + position (12-bit ring), length =
(b2 >> 4) + 3. b1 = b2 = 0 ends the stream. The ring starts at position 0
and is filled with zeros.
"""


def decompress(data, start=0, limit=None):
    out = bytearray()
    ring = bytearray(4096)
    pos = 0
    i = start
    flags = 0
    while limit is None or len(out) < limit:
        flags >>= 1
        if not flags & 0x100:
            flags = data[i] | 0xFF00
            i += 1
        if flags & 1:
            b = data[i]
            i += 1
            out.append(b)
            ring[pos] = b
            pos = (pos + 1) & 0xFFF
        else:
            b1, b2 = data[i], data[i + 1]
            i += 2
            if b1 == 0 and b2 == 0:
                break
            src = (((b2 | 0xF0) << 8) | b1) + pos
            for k in range((b2 >> 4) + 3):
                b = ring[(src + k) & 0xFFF]
                out.append(b)
                ring[pos] = b
                pos = (pos + 1) & 0xFFF
    return bytes(out), i
