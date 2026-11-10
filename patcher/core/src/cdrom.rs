//! Mode 1 raw sectors (2352 bytes): sync, header, 2048 data bytes, EDC, ECC.
//! The same arithmetic as tools/cdimage.py.

use std::sync::OnceLock;

pub const SECTOR: usize = 2352;
pub const USER: usize = 2048;
pub const HDR: usize = 16;

struct Tables {
    ecc_f: [u8; 256],
    ecc_b: [u8; 256],
    edc: [u32; 256],
}

fn tables() -> &'static Tables {
    static T: OnceLock<Tables> = OnceLock::new();
    T.get_or_init(|| {
        let mut t = Tables { ecc_f: [0; 256], ecc_b: [0; 256], edc: [0; 256] };
        for i in 0..256usize {
            let j = (i << 1) ^ if i & 0x80 != 0 { 0x11D } else { 0 };
            t.ecc_f[i] = (j & 0xFF) as u8;
            t.ecc_b[i ^ (j & 0xFF)] = i as u8;
            let mut e = i as u32;
            for _ in 0..8 {
                e = (e >> 1) ^ if e & 1 != 0 { 0xD801_8001 } else { 0 };
            }
            t.edc[i] = e;
        }
        t
    })
}

fn edc(data: &[u8]) -> u32 {
    let t = tables();
    data.iter().fold(0u32, |e, &b| (e >> 8) ^ t.edc[((e ^ b as u32) & 0xFF) as usize])
}

fn ecc_pq(sec: &mut [u8], major_count: usize, minor_count: usize, major_mult: usize, minor_inc: usize, out: usize) {
    let t = tables();
    let size = major_count * minor_count;
    for major in 0..major_count {
        let mut index = (major >> 1) * major_mult + (major & 1);
        let (mut a, mut b) = (0u8, 0u8);
        for _ in 0..minor_count {
            let v = sec[0xC + index];
            index += minor_inc;
            if index >= size {
                index -= size;
            }
            a ^= v;
            b ^= v;
            a = t.ecc_f[a as usize];
        }
        a = t.ecc_b[(t.ecc_f[a as usize] ^ b) as usize];
        sec[out + major] = a;
        sec[out + major + major_count] = a ^ b;
    }
}

/// The raw Mode 1 sector at lba (counted from the track's start) holding payload.
pub fn mode1_sector(lba: usize, payload: &[u8], sec: &mut [u8]) {
    let bcd = |v: usize| ((v / 10) << 4 | v % 10) as u8;
    let abs = lba + 150;
    let (m, s, f) = (abs / (75 * 60), abs / 75 % 60, abs % 75);
    sec[..12].copy_from_slice(&[0, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0]);
    sec[12..16].copy_from_slice(&[bcd(m), bcd(s), bcd(f), 1]);
    sec[HDR..HDR + USER].copy_from_slice(payload);
    let e = edc(&sec[..0x810]);
    sec[0x810..0x814].copy_from_slice(&e.to_le_bytes());
    sec[0x814..0x81C].fill(0);
    ecc_pq(sec, 86, 24, 2, 86, 0x81C);
    ecc_pq(sec, 52, 43, 86, 88, 0x8C8);
}

/// The 2048 data bytes of every sector of a raw track, one after the other.
pub fn user_data(raw: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(raw.len() / SECTOR * USER);
    for sec in raw.chunks_exact(SECTOR) {
        out.extend_from_slice(&sec[HDR..HDR + USER]);
    }
    out
}
