//! The release patch (tools/make_release_patch.py): which tracks of the two discs we
//! need and what our disc is made of.

use std::collections::BTreeMap;
use std::io::Read;

use serde::Deserialize;

static PATCH: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../build/release/ultimate.patch"));

#[derive(Deserialize, Clone)]
pub struct TrackInfo {
    pub size: u64,
    pub sha1: String,
}

#[derive(Deserialize)]
pub struct Game {
    pub name: String,
    pub product: String,
    pub tracks: BTreeMap<String, TrackInfo>,
}

impl Game {
    pub fn track(&self, n: u32) -> Option<&TrackInfo> {
        self.tracks.get(&n.to_string())
    }

    pub fn numbers(&self) -> Vec<u32> {
        let mut v: Vec<u32> = self.tracks.keys().filter_map(|k| k.parse().ok()).collect();
        v.sort();
        v
    }
}

#[derive(Deserialize)]
pub struct Track01 {
    pub sectors: usize,
    pub dirty: Vec<[usize; 2]>,
    pub data: usize,
    pub sha1: String,
}

#[derive(Deserialize)]
pub struct Layout {
    pub track: u32,
    pub from: String,
    pub src: Option<u32>,
}

#[derive(Deserialize)]
pub struct Header {
    pub format: u32,
    pub cce: Game,
    pub dusa: Game,
    pub track01: Track01,
    pub layout: Vec<Layout>,
    pub cue: String,
}

fn split() -> (&'static [u8], &'static [u8]) {
    assert_eq!(&PATCH[..8], b"DUSAULT\x01", "not a release patch");
    let n = u32::from_le_bytes(PATCH[8..12].try_into().unwrap()) as usize;
    (&PATCH[12..12 + n], &PATCH[12 + n..])
}

pub fn header() -> &'static Header {
    static H: std::sync::OnceLock<Header> = std::sync::OnceLock::new();
    H.get_or_init(|| {
        let h: Header = serde_json::from_slice(split().0).expect("the patch's header");
        assert_eq!(h.format, 1, "a patch made for another version of the builder");
        h
    })
}

fn varint(b: &[u8], at: &mut usize) -> Result<usize, String> {
    let mut v = 0usize;
    let mut shift = 0;
    loop {
        let byte = *b.get(*at).ok_or("the patch ends early")?;
        *at += 1;
        v |= ((byte & 0x7F) as usize) << shift;
        if byte & 0x80 == 0 {
            return Ok(v);
        }
        shift += 7;
    }
}

/// The data bytes of the rebuilt sectors, copied from source (CCE's then DUSA's
/// data-track bytes) and filled in from the patch. progress gets the fraction done.
pub fn rebuild_data(source: &[u8], mut progress: impl FnMut(f64)) -> Result<Vec<u8>, String> {
    let mut ops = Vec::new();
    flate2::read::ZlibDecoder::new(split().1)
        .read_to_end(&mut ops)
        .map_err(|e| format!("the patch is damaged: {e}"))?;
    let want = header().track01.data;
    let mut out = Vec::with_capacity(want);
    let mut at = 0;
    let mut tick = 0;
    while out.len() < want {
        let n = varint(&ops, &mut at)?;
        out.extend_from_slice(ops.get(at..at + n).ok_or("the patch ends early")?);
        at += n;
        let m = varint(&ops, &mut at)?;
        if m > 0 {
            let q = varint(&ops, &mut at)?;
            out.extend_from_slice(source.get(q..q + m).ok_or("the patch copies past the discs")?);
        }
        if out.len() >> 18 != tick {
            tick = out.len() >> 18;
            progress(out.len() as f64 / want as f64);
        }
    }
    if out.len() != want {
        return Err("the patch makes the wrong amount of data".into());
    }
    Ok(out)
}
