//! The release patch (tools/make_release_patch.py): which tracks of the two discs we
//! need and what our disc is made of.

use std::collections::BTreeMap;
use std::io::Read;

use serde::Deserialize;

static PATCH: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../build/release/ultimate.patch"));

/// A zlib stream after the header: [offset, length], counted from the header's end.
type Stream = [usize; 2];

#[derive(Deserialize, Clone)]
pub struct TrackInfo {
    pub size: u64,
    pub sha1: String,
}

#[derive(Deserialize)]
pub struct Fixup {
    /// the copy list that makes DUSA (USA)'s ranges from this dump's data-track bytes
    pub ops: Stream,
}

#[derive(Deserialize)]
pub struct Game {
    pub name: String,
    pub product: String,
    pub tracks: BTreeMap<String, TrackInfo>,
    /// a DUSA dump other than USA: how to make the bytes we read of USA's data track
    #[serde(default)]
    pub fixup: Option<Fixup>,
    /// a DUSA dump: the INDEX lines of the tracks we take, from its own cue sheet
    #[serde(default)]
    pub index: BTreeMap<String, Vec<String>>,
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

/// The bytes of DUSA (USA)'s data track that the copy list reads.
#[derive(Deserialize)]
pub struct Ranges {
    /// the size of USA's data-track bytes
    pub data: usize,
    /// [offset, length] in them
    pub ranges: Vec<[usize; 2]>,
    /// of the ranges' bytes, one after the other
    pub sha1: String,
}

#[derive(Deserialize)]
pub struct Track01 {
    pub sectors: usize,
    pub dirty: Vec<[usize; 2]>,
    pub data: usize,
    pub sha1: String,
    pub ops: Stream,
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
    /// the Daytona USA dumps we take, Daytona USA (USA) first
    pub dusa: Vec<Game>,
    pub dusa_ranges: Ranges,
    pub track01: Track01,
    pub layout: Vec<Layout>,
    pub cue: String,
}

fn split() -> (&'static [u8], &'static [u8]) {
    assert_eq!(&PATCH[..8], b"DUSAULT\x02", "not a release patch");
    let n = u32::from_le_bytes(PATCH[8..12].try_into().unwrap()) as usize;
    (&PATCH[12..12 + n], &PATCH[12 + n..])
}

pub fn header() -> &'static Header {
    static H: std::sync::OnceLock<Header> = std::sync::OnceLock::new();
    H.get_or_init(|| {
        let h: Header = serde_json::from_slice(split().0).expect("the patch's header");
        assert_eq!(h.format, 2, "a patch made for another version of the builder");
        h
    })
}

fn stream(at: Stream) -> Result<Vec<u8>, String> {
    let z = split().1.get(at[0]..at[0] + at[1]).ok_or("the patch ends early")?;
    let mut out = Vec::new();
    flate2::read::ZlibDecoder::new(z).read_to_end(&mut out).map_err(|e| format!("the patch is damaged: {e}"))?;
    Ok(out)
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

/// The want bytes that the copy list ops makes from source. progress gets the fraction done.
fn apply(ops: &[u8], source: &[u8], want: usize, mut progress: impl FnMut(f64)) -> Result<Vec<u8>, String> {
    let mut out = Vec::with_capacity(want);
    let mut at = 0;
    let mut tick = 0;
    while out.len() < want {
        let n = varint(ops, &mut at)?;
        out.extend_from_slice(ops.get(at..at + n).ok_or("the patch ends early")?);
        at += n;
        let m = varint(ops, &mut at)?;
        if m > 0 {
            let q = varint(ops, &mut at)?;
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

/// The data bytes of the rebuilt sectors, copied from source (CCE's then DUSA (USA)'s
/// data-track bytes) and filled in from the patch. progress gets the fraction done.
pub fn rebuild_data(source: &[u8], progress: impl FnMut(f64)) -> Result<Vec<u8>, String> {
    let t = &header().track01;
    apply(&stream(t.ops)?, source, t.data, progress)
}

/// The ranges' bytes of DUSA (USA)'s data track, one after the other, made by a
/// dump's fixup from that dump's data-track bytes.
pub fn fixup(f: &Fixup, user: &[u8]) -> Result<Vec<u8>, String> {
    let want = header().dusa_ranges.ranges.iter().map(|r| r[1]).sum();
    apply(&stream(f.ops)?, user, want, |_| {})
}

/// Those bytes at their places in DUSA (USA)'s data-track bytes, zeros between.
pub fn place_ranges(bytes: &[u8]) -> Vec<u8> {
    let r = &header().dusa_ranges;
    let mut out = vec![0; r.data];
    let mut at = 0;
    for &[o, n] in &r.ranges {
        out[o..o + n].copy_from_slice(&bytes[at..at + n]);
        at += n;
    }
    out
}
