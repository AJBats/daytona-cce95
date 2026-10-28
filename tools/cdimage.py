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
        for path, lba, size, _ in self.records():
            yield path, lba, size

    def records(self):
        """Yield (path, lba, size, (directory sector, offset)) for every file."""
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
            at = (lba + pos // USER, pos % USER)
            pos += ln
            if name in (b'\x00', b'\x01'):
                continue
            name = name.decode('ascii').split(';')[0]
            if flags & 2:
                yield from self._walk(flba, fsize, prefix + name + '/')
            else:
                yield prefix + name, flba, fsize, at

    def directories(self):
        """{path: (lba, size)} of every directory, the root as ''."""
        pvd = self.read(16)
        root = pvd[156:156 + 34]
        out = {'': (struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0])}
        todo = ['']
        while todo:
            path = todo.pop()
            lba, size = out[path]
            data = self.read(lba, (size + USER - 1) // USER)
            pos = 0
            while pos < size:
                ln = data[pos]
                if ln == 0:
                    pos = (pos // USER + 1) * USER
                    continue
                rec = data[pos:pos + ln]
                name = rec[33:33 + rec[32]]
                if rec[25] & 2 and name not in (b'\x00', b'\x01'):
                    sub = path + name.decode('ascii') + '/'
                    out[sub] = (struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0])
                    todo.append(sub)
                pos += ln
        return out

    def add_record(self, directory, name, lba, size):
        """A file record for name (lba, size bytes) after the last record of
        the directory (path as directories() gives it), in its last sector,
        dated and flagged as that record is. -> the record's (sector, offset)."""
        dlba, dsize = self.directories()[directory]
        last = dlba + (dsize + USER - 1) // USER - 1
        sec = self.read(last)
        pos = prev = 0
        while pos < USER and sec[pos]:
            prev = pos
            pos += sec[pos]
        ident = name.encode('ascii') + b';1'
        ln = 33 + len(ident) + (1 - len(ident) % 2)
        if pos + ln > USER:
            raise ValueError(f'no room for {name} in the last sector of {directory or "the root"}')
        rec = bytearray(sec[prev:prev + sec[prev]][:33])
        rec[0] = ln
        rec[25] = 0
        rec[32] = len(ident)
        rec += ident + bytes(ln - 33 - len(ident))
        base = last * SECTOR + HDR + pos
        self.raw[base:base + ln] = rec
        self.dirty.add(last)
        self.set_extent((last, pos), lba, size)
        return last, pos

    def set_extent(self, at, lba, size):
        """Point the directory record at (sector, offset) at lba, size bytes (both byte orders)."""
        sec, off = at
        base = sec * SECTOR + HDR + off
        struct.pack_into('<I', self.raw, base + 2, lba)
        struct.pack_into('>I', self.raw, base + 6, lba)
        struct.pack_into('<I', self.raw, base + 10, size)
        struct.pack_into('>I', self.raw, base + 14, size)
        self.dirty.add(sec)

    def volume_size(self, sectors=None):
        """The volume space size in the primary volume descriptor; set it if given."""
        base = 16 * SECTOR + HDR
        if sectors is not None:
            struct.pack_into('<I', self.raw, base + 80, sectors)
            struct.pack_into('>I', self.raw, base + 84, sectors)
            self.dirty.add(16)
        return struct.unpack_from('<I', self.raw, base + 80)[0]

    def extend(self, sectors):
        """Grow the track to this many sectors: Mode 1 sectors, zero data."""
        old = len(self.raw) // SECTOR
        for lba in range(old, sectors):
            m, s = divmod(lba + 150, 75 * 60)
            s, f = divmod(s, 75)
            bcd = lambda v: (v // 10) << 4 | v % 10
            sec = bytearray(SECTOR)
            sec[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
            sec[12:16] = bytes([bcd(m), bcd(s), bcd(f), 1])
            self.raw += sec
            self.dirty.add(lba)

    def save(self, path):
        for lba in self.dirty:
            sec = bytearray(self.raw[lba * SECTOR:(lba + 1) * SECTOR])
            fix_sector(sec)
            self.raw[lba * SECTOR:(lba + 1) * SECTOR] = sec
        with open(path, 'wb') as f:
            f.write(self.raw)
