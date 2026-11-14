//! The builder's log: a text file beside the builder that a player can attach to an
//! issue. Every disc checked and every build adds to it: the track files found,
//! what the data track says it is, each track's SHA-1, and the answer the player saw.
//! The player's home folder is written as ~, since logs get posted publicly.
//! Writing it never stops the builder: a log that can't be written is skipped.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};

pub const NAME: &str = "Daytona USA Ultimate Builder log.txt";

/// A log past this size starts again.
const LIMIT: u64 = 1_000_000;

#[cfg(windows)]
const NL: &str = "\r\n";
#[cfg(not(windows))]
const NL: &str = "\n";

struct Log {
    path: PathBuf,
    home: Option<String>,
}

fn home() -> Option<PathBuf> {
    let var = if cfg!(windows) { "USERPROFILE" } else { "HOME" };
    std::env::var_os(var).map(PathBuf::from).filter(|p| p.is_dir())
}

/// Beside the builder, where the player finds it; else their Documents (Windows)
/// or home folder; else the temporary folder.
fn place() -> PathBuf {
    if let Some(d) = crate::builder::builder_dir() {
        return d.join(NAME);
    }
    if let Some(h) = home() {
        let docs = h.join("Documents");
        return if cfg!(windows) && docs.is_dir() { docs.join(NAME) } else { h.join(NAME) };
    }
    std::env::temp_dir().join(NAME)
}

fn log() -> &'static Log {
    static L: OnceLock<Log> = OnceLock::new();
    L.get_or_init(|| {
        let path = place();
        if fs::metadata(&path).map(|m| m.len() > LIMIT).unwrap_or(false) {
            let _ = fs::write(&path, b"");
        }
        Log { path, home: home().map(|h| h.display().to_string()) }
    })
}

/// Where the log is written.
pub fn path() -> &'static Path {
    &log().path
}

/// text with needle written as ~ (ignoring case on Windows, as its paths do).
fn replace_home(text: &str, needle: &str) -> String {
    let (hay, needle) = if cfg!(windows) {
        (text.to_ascii_lowercase(), needle.to_ascii_lowercase())
    } else {
        (text.to_string(), needle.to_string())
    };
    let mut out = String::with_capacity(text.len());
    let mut at = 0;
    while let Some(i) = hay[at..].find(&needle) {
        out.push_str(&text[at..at + i]);
        out.push('~');
        at += i + needle.len();
    }
    out.push_str(&text[at..]);
    out
}

/// text with the home folder written as ~, with either slash on Windows.
fn private(text: &str, home: &str) -> String {
    if home.len() < 2 {
        return text.to_string();
    }
    let text = replace_home(text, home);
    if cfg!(windows) {
        replace_home(&text, &home.replace('\\', "/"))
    } else {
        text
    }
}

/// Add a line (or several) to the log.
pub fn line(text: &str) {
    let l = log();
    let text = match &l.home {
        Some(h) => private(text, h),
        None => text.to_string(),
    };
    let mut s = String::new();
    for t in text.lines() {
        s.push_str(t);
        s.push_str(NL);
    }
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&l.path) {
        let _ = f.write_all(s.as_bytes());
    }
}

/// The time now, in UTC: "2026-11-13 18:04:11 UTC".
fn now() -> String {
    let secs = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
    let (days, rem) = ((secs / 86400) as i64, secs % 86400);
    // days since 1970-01-01 to a date (Howard Hinnant's civil_from_days)
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + if m <= 2 { 1 } else { 0 };
    format!("{y}-{m:02}-{d:02} {:02}:{:02}:{:02} UTC", rem / 3600, rem / 60 % 60, rem % 60)
}

/// The system, as far as it's cheap to tell: Linux's own name for itself.
fn system() -> String {
    let mut s = format!("{} {}", std::env::consts::OS, std::env::consts::ARCH);
    if let Ok(t) = fs::read_to_string("/etc/os-release") {
        if let Some(name) = t.lines().find_map(|l| l.strip_prefix("PRETTY_NAME=")) {
            s = format!("{} ({s})", name.trim_matches('"'));
        }
    }
    s
}

/// A run of the builder starts: which builder, which patch, and when. A panic
/// from here on is written to the log too.
pub fn start(builder: &str) {
    let h = crate::patch::header();
    line(&format!(
        "{NL}==== {} · {builder} · patch for track 01 SHA-1 {} · {}",
        now(),
        &h.track01.sha1[..8],
        system()
    ));
    line(&format!("Log: {}", path().display()));
    let default = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        line(&format!("The builder crashed: {info}"));
        default(info);
    }));
}
