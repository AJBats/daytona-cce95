//! The player's discs as they come: a cue sheet with its track files, a zip of
//! them, or a folder of track files. Tracks are told apart by size (and checked
//! by SHA-1 later), so renamed files are fine.

use std::collections::BTreeMap;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};

use crate::patch::Game;

pub enum Loc {
    File(PathBuf),
    Zip { archive: PathBuf, index: usize },
}

pub struct Bin {
    pub name: String,
    pub size: u64,
    pub loc: Loc,
}

impl Bin {
    pub fn read(&self) -> Result<Vec<u8>, String> {
        let mut v = Vec::with_capacity(self.size as usize);
        match &self.loc {
            Loc::File(p) => {
                File::open(p).and_then(|mut f| f.read_to_end(&mut v)).map_err(|e| format!("{}: {e}", p.display()))?;
            }
            Loc::Zip { archive, index } => {
                let mut z = open_zip(archive)?;
                let mut f = z.by_index(*index).map_err(|e| format!("{}: {e}", self.name))?;
                f.read_to_end(&mut v).map_err(|e| format!("{}: {e}", self.name))?;
            }
        }
        Ok(v)
    }

    /// The first n bytes (fewer if the file is shorter).
    pub fn head(&self, n: usize) -> Result<Vec<u8>, String> {
        let mut v = Vec::with_capacity(n);
        match &self.loc {
            Loc::File(p) => {
                File::open(p)
                    .and_then(|f| f.take(n as u64).read_to_end(&mut v))
                    .map_err(|e| format!("{}: {e}", p.display()))?;
            }
            Loc::Zip { archive, index } => {
                let mut z = open_zip(archive)?;
                let f = z.by_index(*index).map_err(|e| format!("{}: {e}", self.name))?;
                f.take(n as u64).read_to_end(&mut v).map_err(|e| format!("{}: {e}", self.name))?;
            }
        }
        Ok(v)
    }
}

fn open_zip(path: &Path) -> Result<zip::ZipArchive<File>, String> {
    let f = File::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
    zip::ZipArchive::new(f).map_err(|e| format!("{} isn't a zip we can read: {e}", path.display()))
}

fn ext(p: &Path) -> String {
    p.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default()
}

fn folder_bins(dir: &Path) -> Vec<Bin> {
    let mut out = Vec::new();
    if let Ok(rd) = std::fs::read_dir(dir) {
        for e in rd.flatten() {
            let p = e.path();
            if ext(&p) == "bin" {
                if let Ok(m) = e.metadata() {
                    out.push(Bin { name: e.file_name().to_string_lossy().into(), size: m.len(), loc: Loc::File(p) });
                }
            }
        }
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    out
}

/// Every track file that path stands for.
pub fn bins(path: &Path) -> Result<Vec<Bin>, String> {
    if path.is_dir() {
        return Ok(folder_bins(path));
    }
    let dir = path.parent().unwrap_or(Path::new("."));
    match ext(path).as_str() {
        "zip" => {
            let mut z = open_zip(path)?;
            let mut out = Vec::new();
            for i in 0..z.len() {
                let f = z.by_index(i).map_err(|e| e.to_string())?;
                if f.is_file() && ext(Path::new(f.name())) == "bin" {
                    out.push(Bin { name: f.name().into(), size: f.size(), loc: Loc::Zip { archive: path.into(), index: i } });
                }
            }
            Ok(out)
        }
        "cue" => {
            // the files the sheet names, if they're all there; any track files beside it if not
            let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
            let mut listed = Vec::new();
            for line in text.lines() {
                let line = line.trim();
                if let Some(rest) = line.strip_prefix("FILE ") {
                    let name = match rest.strip_prefix('"') {
                        Some(r) => r.split('"').next().unwrap_or(""),
                        None => rest.split_whitespace().next().unwrap_or(""),
                    };
                    listed.push(dir.join(name));
                }
            }
            if !listed.is_empty() && listed.iter().all(|p| p.is_file()) {
                Ok(listed
                    .into_iter()
                    .map(|p| {
                        let size = std::fs::metadata(&p).map(|m| m.len()).unwrap_or(0);
                        Bin { name: p.file_name().unwrap().to_string_lossy().into(), size, loc: Loc::File(p) }
                    })
                    .collect())
            } else {
                Ok(folder_bins(dir))
            }
        }
        "bin" => Ok(folder_bins(dir)),
        "" => Err(format!("{} isn't a disc image", path.display())),
        e => Err(format!(
            "Can't read .{e} files. Pick the disc's .cue sheet (with its .bin track files beside it) or a .zip of them."
        )),
    }
}

/// For each of the game's tracks, the file of that size, if any.
pub fn match_tracks(bins: Vec<Bin>, game: &Game) -> BTreeMap<u32, Bin> {
    let mut out = BTreeMap::new();
    let mut pool: Vec<Option<Bin>> = bins.into_iter().map(Some).collect();
    for n in game.numbers() {
        let want = game.track(n).unwrap().size;
        let tag = format!("track {n:02}");
        let pick = pool
            .iter()
            .position(|b| b.as_ref().is_some_and(|b| b.size == want && b.name.to_lowercase().contains(&tag)))
            .or_else(|| pool.iter().position(|b| b.as_ref().is_some_and(|b| b.size == want)));
        if let Some(i) = pick {
            out.insert(n, pool[i].take().unwrap());
        }
    }
    out
}

/// What a Saturn data track says it is: (title, product number).
pub fn saturn_id(bins: &[Bin]) -> Option<(String, String)> {
    for b in bins {
        if b.size % 2352 != 0 {
            continue;
        }
        let Ok(h) = b.head(2352) else { continue };
        if h.len() < 2352 || h[..12] != [0, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0] {
            continue;
        }
        let ip = &h[16..16 + 2048];
        if &ip[..16] != b"SEGA SEGASATURN " {
            continue;
        }
        let text = |r: std::ops::Range<usize>| String::from_utf8_lossy(&ip[r]).trim().to_string();
        return Some((text(0x60..0xD0), text(0x20..0x2A)));
    }
    None
}
