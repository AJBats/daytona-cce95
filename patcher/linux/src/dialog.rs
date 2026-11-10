//! The desktop's own dialogs for choosing a disc or a folder: the XDG desktop
//! portal (over D-Bus, in Rust: GNOME, KDE, SteamOS's desktop and most others),
//! else zenity or kdialog. With none of those the page says to build from a
//! terminal instead (--build).

use std::collections::HashMap;
use std::process::{Command, Stdio};

use zbus::blocking::{Connection, MessageIterator, Proxy};
use zbus::message::Type;
use zbus::zvariant::{OwnedObjectPath, OwnedValue, Value};
use zbus::MatchRule;

/// The answer when there's no dialog to show: the page points to --build.
pub const NO_DIALOG: &str = "nodialog";

const DISC_TITLE: &str = "Choose a disc: its .cue sheet, or a .zip of it";
const FOLDER_TITLE: &str = "Choose where to write Daytona USA Ultimate";
const DISC_NAME: &str = "Disc image (.cue, .zip)";
// Linux file names are case-sensitive, and rips come either way
const DISC_GLOBS: &[&str] = &["*.cue", "*.CUE", "*.zip", "*.ZIP", "*.bin", "*.BIN"];

pub fn pick_disc() -> Result<Option<String>, String> {
    choose(false)
}

pub fn pick_folder() -> Result<Option<String>, String> {
    choose(true)
}

/// Some(path), None if the player cancelled, NO_DIALOG if no dialog could be shown.
fn choose(folder: bool) -> Result<Option<String>, String> {
    if let Ok(r) = portal(folder) {
        return Ok(r);
    }
    if let Some(r) = zenity(folder) {
        return Ok(r);
    }
    if let Some(r) = kdialog(folder) {
        return Ok(r);
    }
    Err(NO_DIALOG.into())
}

/// org.freedesktop.portal.FileChooser.OpenFile, and the Response signal it ends with.
fn portal(folder: bool) -> zbus::Result<Option<String>> {
    let conn = Connection::session()?;
    let token = format!(
        "daytona{}",
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0)
    );
    // the request's path is known before the call, so its answer can't be missed
    let sender = conn.unique_name().ok_or(zbus::Error::Failure("no unique name".into()))?;
    let sender = sender.trim_start_matches(':').replace('.', "_");
    let request = format!("/org/freedesktop/portal/desktop/request/{sender}/{token}");
    let rule = MatchRule::builder()
        .msg_type(Type::Signal)
        .interface("org.freedesktop.portal.Request")?
        .member("Response")?
        .path(request.as_str())?
        .build();
    let answers = MessageIterator::for_match_rule(rule, &conn, Some(4))?;

    let mut options: HashMap<&str, Value> = HashMap::new();
    options.insert("handle_token", Value::from(token.as_str()));
    options.insert("modal", Value::from(true));
    if folder {
        options.insert("directory", Value::from(true));
    } else {
        let globs: Vec<(u32, &str)> = DISC_GLOBS.iter().map(|g| (0u32, *g)).collect();
        options.insert("filters", Value::from(vec![(DISC_NAME, globs)]));
    }
    let proxy = Proxy::new(
        &conn,
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.FileChooser",
    )?;
    let title = if folder { FOLDER_TITLE } else { DISC_TITLE };
    let _: OwnedObjectPath = proxy.call("OpenFile", &("", title, options))?;

    for msg in answers {
        let msg = msg?;
        let (code, results): (u32, HashMap<String, OwnedValue>) = msg.body().deserialize()?;
        if code != 0 {
            return Ok(None);
        }
        let first = match results.get("uris").map(|v| &**v) {
            Some(Value::Array(a)) => a.iter().find_map(|u| match u {
                Value::Str(s) => Some(s.to_string()),
                _ => None,
            }),
            _ => None,
        };
        return Ok(first.and_then(|u| file_path(&u)));
    }
    Err(zbus::Error::Failure("the portal never answered".into()))
}

/// file:///a%20b -> /a b
fn file_path(uri: &str) -> Option<String> {
    let rest = uri.strip_prefix("file://")?;
    let b = rest.as_bytes();
    let hex = |c: u8| (c as char).to_digit(16).map(|d| d as u8);
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            if let (Some(h), Some(l)) = (hex(b[i + 1]), hex(b[i + 2])) {
                out.push(h << 4 | l);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    Some(String::from_utf8_lossy(&out).into_owned())
}

/// Run a dialog program: Some(Some(path)) chosen, Some(None) cancelled, None not there.
fn run(program: &str, args: &[String]) -> Option<Option<String>> {
    let out = Command::new(program).args(args).stdin(Stdio::null()).stderr(Stdio::null()).output().ok()?;
    match out.status.code() {
        Some(0) => {
            let p = String::from_utf8_lossy(&out.stdout).trim_end_matches('\n').to_string();
            Some(if p.is_empty() { None } else { Some(p) })
        }
        Some(1) => Some(None),
        _ => None,
    }
}

fn zenity(folder: bool) -> Option<Option<String>> {
    let mut args = vec!["--file-selection".to_string()];
    if folder {
        args.extend(["--directory".into(), format!("--title={FOLDER_TITLE}")]);
    } else {
        args.extend([
            format!("--title={DISC_TITLE}"),
            format!("--file-filter={DISC_NAME} | {}", DISC_GLOBS.join(" ")),
            "--file-filter=All files | *".into(),
        ]);
    }
    run("zenity", &args)
}

fn kdialog(folder: bool) -> Option<Option<String>> {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/".into());
    let args = if folder {
        vec!["--title".into(), FOLDER_TITLE.into(), "--getexistingdirectory".into(), home]
    } else {
        vec![
            "--title".into(),
            DISC_TITLE.into(),
            "--getopenfilename".into(),
            home,
            format!("{}|{DISC_NAME}", DISC_GLOBS.join(" ")),
        ]
    };
    run("kdialog", &args)
}
