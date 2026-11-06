//! Checking the player's discs and building ours from them.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use serde::Serialize;
use sha1::{Digest, Sha1};

use crate::cdrom::{self, SECTOR, USER};
use crate::disc::{self, Bin};
use crate::patch::{self, Game, Header};

#[derive(Serialize, Clone)]
pub struct Progress {
    /// what's being done now
    pub stage: String,
    /// a detail of it, if any
    pub detail: String,
    /// of the whole build
    pub fraction: f64,
    /// a line for the log, when a step finishes
    pub log: Option<String>,
}

#[derive(Serialize)]
pub struct Report {
    /// "cce" or "dusa"
    pub game: String,
    pub name: String,
    pub path: String,
}

#[derive(Serialize)]
pub struct Done {
    pub cue: String,
    pub dir: String,
}

pub const OUT_NAME: &str = "Daytona USA Ultimate";

fn sha1_hex(data: &[u8]) -> String {
    Sha1::digest(data).iter().map(|b| format!("{b:02x}")).collect()
}

fn mb(n: u64) -> String {
    format!("{:.1} MB", n as f64 / 1_000_000.0)
}

struct Disc<'a> {
    key: &'static str,
    game: &'a Game,
    tracks: BTreeMap<u32, Bin>,
}

/// Daytona USA as this takes it, from the dumps' names: "Daytona USA (USA, Europe or Japan)".
fn dusa_wanted(h: &Header) -> String {
    let mut regions: Vec<&str> = Vec::new();
    for g in &h.dusa {
        if let Some(r) = g.name.split(" (").nth(1).map(|r| r.trim_end_matches(')')) {
            if !regions.contains(&r) {
                regions.push(r);
            }
        }
    }
    let first = &h.dusa[0].name;
    match regions.split_last() {
        Some((last, rest)) if !rest.is_empty() => {
            format!("{} ({} or {last})", first.split(" (").next().unwrap(), rest.join(", "))
        }
        _ => first.clone(),
    }
}

/// The disc at path: which game it is (for Daytona USA, which dump), and its track files.
fn open(path: &Path) -> Result<Disc<'static>, String> {
    let h = patch::header();
    let bins = disc::bins(path)?;
    if bins.is_empty() {
        return Err("There are no .bin track files there.".into());
    }
    // every game or dump whose tracks are all there by size; else the nearest, to say what's missing
    let mut found = Vec::new();
    let mut near: Option<(&Game, Vec<u32>)> = None;
    for (key, game) in std::iter::once(("cce", &h.cce)).chain(h.dusa.iter().map(|g| ("dusa", g))) {
        let first = game.track(1).unwrap().size;
        if !bins.iter().any(|b| b.size == first) {
            continue;
        }
        let tracks = disc::match_tracks(&bins, game);
        let missing: Vec<u32> = game.numbers().into_iter().filter(|n| !tracks.contains_key(n)).collect();
        if missing.is_empty() {
            found.push(Disc { key, game, tracks });
        } else if near.as_ref().map_or(true, |(_, m)| missing.len() < m.len()) {
            near = Some((game, missing));
        }
    }
    if found.len() > 1 {
        // dumps whose tracks are the same sizes, told apart by SHA-1: the one with fewest tracks wrong
        let mut sums: BTreeMap<String, String> = BTreeMap::new();
        let mut wrong = Vec::new();
        for d in &found {
            let mut n = 0;
            for (t, bin) in &d.tracks {
                if !sums.contains_key(&bin.name) {
                    sums.insert(bin.name.clone(), sha1_hex(&bin.read()?));
                }
                if sums[&bin.name] != d.game.track(*t).unwrap().sha1 {
                    n += 1;
                }
            }
            wrong.push(n);
        }
        let best = *wrong.iter().min().unwrap();
        let tied: Vec<&str> = found.iter().zip(&wrong).filter(|(_, &n)| n == best).map(|(d, _)| d.game.name.as_str()).collect();
        if tied.len() > 1 {
            return Err(format!(
                "This looks like {}, but its tracks don't match {} (their SHA-1s differ). \
                 It needs the Redump dump of the disc; this may be another printing or a damaged rip.",
                tied.join(" or "),
                if tied.len() == 2 { "either" } else { "any of them" },
            ));
        }
        return Ok(found.swap_remove(wrong.iter().position(|&n| n == best).unwrap()));
    }
    if let Some(d) = found.pop() {
        return Ok(d);
    }
    if let Some((game, missing)) = near {
        let missing: Vec<String> = missing.iter().map(|n| format!("{n:02}")).collect();
        return Err(format!(
            "This looks like {}, but track{} {} {} missing or not the size {} should be.",
            game.name,
            if missing.len() > 1 { "s" } else { "" },
            missing.join(", "),
            if missing.len() > 1 { "are" } else { "is" },
            if missing.len() > 1 { "they" } else { "it" },
        ));
    }
    let known = |product: &str| std::iter::once(&h.cce).chain(&h.dusa).any(|g| g.product == product);
    Err(match disc::saturn_id(&bins) {
        Some((title, product)) if known(&product) => format!(
            "That's {title} ({product}), but its tracks aren't the sizes of any dump this knows. \
             It needs the Redump dump of the disc; this may be another printing or a damaged rip."
        ),
        Some((title, product)) => format!(
            "That's {title} ({product}). This needs {} and {} ({}).",
            dusa_wanted(h),
            h.cce.name,
            h.cce.product
        ),
        None => format!("That isn't a Saturn disc this can use. It needs {} and {}.", dusa_wanted(h), h.cce.name),
    })
}

/// Read a track and check it's the one the patch was made from.
fn checked(d: &Disc, n: u32) -> Result<Vec<u8>, String> {
    let data = d.tracks[&n].read()?;
    let want = d.game.track(n).unwrap();
    if sha1_hex(&data) != want.sha1 {
        return Err(format!(
            "Track {n:02} of your {} isn't the one this was made for (its SHA-1 differs). \
             It needs the Redump dump of the disc; this may be another printing or a damaged rip.",
            d.game.name
        ));
    }
    Ok(data)
}

/// Which game the disc at path is, its data track checked.
pub fn inspect(path: &Path) -> Result<Report, String> {
    let d = open(path)?;
    checked(&d, 1)?;
    if d.key == "dusa" {
        for n in d.game.numbers() {
            if n != 1 {
                checked(&d, n)?;
            }
        }
    }
    Ok(Report { game: d.key.into(), name: d.game.name.clone(), path: path.display().to_string() })
}

/// Build our disc into out_dir from the two discs; -> the cue sheet's path.
pub fn build(cce_path: &Path, dusa_path: &Path, out_dir: &Path, mut progress: impl FnMut(Progress)) -> Result<Done, String> {
    let h = patch::header();
    let cce = open(cce_path)?;
    let dusa = open(dusa_path)?;
    if cce.key != "cce" || dusa.key != "dusa" {
        return Err("Those are the wrong way round: one of each disc, please.".into());
    }
    let disc_of = |k: &str| if k == "cce" { &cce } else { &dusa };

    // work, in bytes: every track read, track 01 rebuilt and checked
    let out01 = (h.track01.sectors * SECTOR) as u64;
    let reads: u64 = h.layout.iter().filter_map(|l| l.src.map(|s| disc_of(&l.from).game.track(s).unwrap().size)).sum::<u64>()
        + cce.game.track(1).unwrap().size
        + dusa.game.track(1).unwrap().size;
    let total = (reads + 3 * out01) as f64;
    let mut done = 0u64;
    let mut say = |stage: &str, detail: String, done: u64, log: Option<String>| {
        progress(Progress { stage: stage.into(), detail, fraction: (done as f64 / total).min(1.0), log });
    };

    // the data tracks: checked, then the patch's sectors made from them
    say("Checking Circuit Edition", format!("track 01 · {}", mb(cce.game.track(1).unwrap().size)), done, None);
    let base = checked(&cce, 1)?;
    done += base.len() as u64;
    say("Checking Circuit Edition", "track 01".into(), done, Some(format!("CCE track 01 · SHA-1 {} ✓", &cce.game.track(1).unwrap().sha1[..8])));
    say("Checking Daytona USA", format!("track 01 · {}", mb(dusa.game.track(1).unwrap().size)), done, None);
    let dusa1 = checked(&dusa, 1)?;
    done += dusa1.len() as u64;
    say("Checking Daytona USA", "track 01".into(), done, Some(format!("DUSA track 01 · SHA-1 {} ✓", &dusa.game.track(1).unwrap().sha1[..8])));

    // the copy list reads DUSA (USA)'s data-track bytes: another dump's are laid out like them
    let mut source = cdrom::user_data(&base);
    let mut dusa_user = cdrom::user_data(&dusa1);
    drop(dusa1);
    if let Some(f) = &dusa.game.fixup {
        let bytes = patch::fixup(f, &dusa_user)?;
        let sha = sha1_hex(&bytes);
        if sha != h.dusa_ranges.sha1 {
            return Err(format!(
                "What we need from your {} came out wrong (its SHA-1 differs from ours). Please report this.",
                dusa.game.name
            ));
        }
        dusa_user = patch::place_ranges(&bytes);
        say("Checking Daytona USA", "track 01".into(), done, Some(format!("DUSA track 01 · laid out like the USA disc · SHA-1 {} ✓", &sha[..8])));
    }
    source.extend(dusa_user);
    let data = patch::rebuild_data(&source, |f| {
        say("Unpacking the patch", format!("{} of {}", mb((f * h.track01.data as f64) as u64), mb(h.track01.data as u64)), done + (f * out01 as f64) as u64, None)
    })?;
    drop(source);
    done += out01;
    let sectors: Vec<usize> = h.track01.dirty.iter().flat_map(|[s, n]| *s..*s + *n).collect();
    say("Unpacking the patch", String::new(), done, Some(format!("Patch unpacked · {} of data for {} sectors", mb(data.len() as u64), sectors.len())));

    let mut track = base;
    track.resize(out01 as usize, 0);
    for (k, &lba) in sectors.iter().enumerate() {
        cdrom::mode1_sector(lba, &data[k * USER..(k + 1) * USER], &mut track[lba * SECTOR..(lba + 1) * SECTOR]);
        if k % 64 == 0 || k + 1 == sectors.len() {
            let f = (k + 1) as f64 / sectors.len() as f64;
            say("Rebuilding track 01", format!("sector {} of {} · EDC/ECC", lba, h.track01.sectors), done + (f * out01 as f64) as u64, None);
        }
    }
    done += out01;
    say("Rebuilding track 01", String::new(), done, Some(format!("Track 01 · {} sectors rebuilt, EDC/ECC written", sectors.len())));
    let sha = sha1_hex(&track);
    if sha != h.track01.sha1 {
        return Err("Track 01 came out wrong (its SHA-1 differs from ours). Please report this.".into());
    }

    fs::create_dir_all(out_dir).map_err(|e| format!("Can't make {}: {e}", out_dir.display()))?;
    let file = |n: u32| format!("{OUT_NAME} (Track {n:02}).bin");
    let write = |n: u32, data: &[u8]| {
        let p = out_dir.join(file(n));
        fs::write(&p, data).map_err(|e| format!("Can't write {}: {e}", p.display()))
    };
    write(1, &track)?;
    done += out01;
    say("Writing track 01", String::new(), done, Some(format!("Track 01 · SHA-1 {} ✓ matches", &sha[..8])));
    drop(track);

    // the audio tracks, copied and checked
    for l in &h.layout {
        let Some(src) = l.src else { continue };
        let d = disc_of(&l.from);
        let what = if l.from == "cce" { "Circuit Edition".to_string() } else { "Daytona USA".to_string() };
        let size = d.game.track(src).unwrap().size;
        say(&format!("Copying track {:02}", l.track), format!("from {what} track {src:02} · {}", mb(size)), done, None);
        let data = checked(d, src)?;
        write(l.track, &data)?;
        done += size;
        say(
            &format!("Copying track {:02}", l.track),
            String::new(),
            done,
            Some(format!("Track {:02} ← {} {src:02} · SHA-1 {} ✓", l.track, if l.from == "cce" { "CCE" } else { "DUSA" }, &d.game.track(src).unwrap().sha1[..8])),
        );
    }

    // the tracks from Daytona USA keep that dump's INDEX lines: the pregaps differ between dumps
    let mut cue = h.cue.clone();
    for l in &h.layout {
        if let (Some(src), "dusa") = (l.src, l.from.as_str()) {
            let lines = dusa.game.index.get(&src.to_string()).ok_or("The patch has no cue lines for that disc. Please report this.")?;
            let lines: Vec<String> = lines.iter().map(|x| format!("    {x}")).collect();
            cue = cue.replace(&format!("@{:02}:INDEX@", l.track), &lines.join("\n"));
        }
        cue = cue.replace(&format!("@{:02}@", l.track), &file(l.track));
    }
    if cue.contains('@') {
        return Err("The cue sheet came out wrong. Please report this.".into());
    }
    let cue_path = out_dir.join(format!("{OUT_NAME}.cue"));
    fs::write(&cue_path, cue.replace("\r\n", "\n").replace('\n', "\r\n")).map_err(|e| format!("Can't write {}: {e}", cue_path.display()))?;
    say("Done", String::new(), total as u64, Some(format!("{OUT_NAME}.cue written")));
    Ok(Done { cue: cue_path.display().to_string(), dir: out_dir.display().to_string() })
}
