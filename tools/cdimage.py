"""Mode 1 / 2352 CD image access: ISO9660 walking, file extraction, in-place
file replacement with EDC/ECC regeneration."""
import struct

SECTOR = 2352
USER = 2048
HDR = 16

# ---------------------------------------------------------------- EDC / ECC

def _build_tables():
    ecc_f = [0] * 256
    ecc_b = [0] * 256
    edc = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        ecc_f[i] = j & 0xFF
        ecc_b[i ^ j & 0xFF] = i
        e = i
        for _ in range(8):
            e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
        edc[i] = e
    return ecc_f, ecc_b, edc

ECC_F, ECC_B, EDC_T = _build_tables()


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC_T[(e ^ b) & 0xFF]
    return e


def _ecc_pq(sec, major_count, minor_count, major_mult, minor_inc, out_off):
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            temp = sec[0xC + index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= temp
            b ^= temp
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        sec[out_off + major] = a
        sec[out_off + major + major_count] = a ^ b


def fix_sector(sec):
    """Recompute EDC and ECC of a Mode 1 raw sector (bytearray, in place)."""
    struct.pack_into('<I', sec, 0x810, edc(sec[0:0x810]))
    sec[0x814:0x81C] = bytes(8)
    _ecc_pq(sec, 86, 24, 2, 86, 0x81C)
    _ecc_pq(sec, 52, 43, 86, 88, 0x8C8)
    return sec

# ---------------------------------------------------------------- ISO9660

class Image:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.raw = bytearray(f.read())
        self.dirty = set()

    def read(self, lba, n=1):
        return b''.join(self.raw[(lba + i) * SECTOR + HDR:(lba + i) * SECTOR + HDR + USER]
                        for i in range(n))

    def write(self, lba, data):
        nsec = (len(data) + USER - 1) // USER
        for i in range(nsec):
            chunk = data[i * USER:(i + 1) * USER]
            off = (lba + i) * SECTOR + HDR
            self.raw[off:off + len(chunk)] = chunk
            self.dirty.add(lba + i)

    def files(self):
        """Yield (path, lba, size) for every file, depth-first."""
        pvd = self.read(16)
        root = pvd[156:156 + 34]
        yield from self._walk(struct.unpack_from('<I', root, 2)[0],
                              struct.unpack_from('<I', root, 10)[0], '')

    def _walk(self, lba, size, prefix):
        data = self.read(lba, (size + USER - 1) // USER)
        pos = 0
        while pos < size:
            ln = data[pos]
            if ln == 0:
                pos = (pos // USER + 1) * USER
                continue
            rec = data[pos:pos + ln]
            flba = struct.unpack_from('<I', rec, 2)[0]
            fsize = struct.unpack_from('<I', rec, 10)[0]
            flags = rec[25]
            name = rec[33:33 + rec[32]]
            pos += ln
            if name in (b'\x00', b'\x01'):
                continue
            name = name.decode('ascii').split(';')[0]
            if flags & 2:
                yield from self._walk(flba, fsize, prefix + name + '/')
            else:
                yield prefix + name, flba, fsize

    def save(self, path):
        for lba in self.dirty:
            sec = bytearray(self.raw[lba * SECTOR:(lba + 1) * SECTOR])
            fix_sector(sec)
            self.raw[lba * SECTOR:(lba + 1) * SECTOR] = sec
        with open(path, 'wb') as f:
            f.write(self.raw)
