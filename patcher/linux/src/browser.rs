//! Opening the page as a window of its own, as the Windows app's: no tabs, no
//! address bar.
//!
//! Chrome, Chromium, Edge, Brave and Vivaldi have an app mode (--app) for that,
//! installed as programs or as Flatpaks (as on a Steam Deck). Firefox has none,
//! so it gets a profile of ours whose toolbars are hidden (userChrome.css). Each
//! runs with a profile of its own, kept in the cache: a window apart from the
//! player's browsing, which remembers the page's settings. With none of those,
//! the page opens as a tab of the default browser (xdg-open).
//!
//! DAYTONA_BROWSER=chromium|firefox|tab picks one way, for testing.

use std::ffi::{OsStr, OsString};
use std::io;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

#[derive(PartialEq, Eq, Clone, Copy)]
pub enum Opened {
    /// in a window of its own, of this browser
    Window(&'static str),
    /// in the default browser, likely a tab
    Tab,
    No,
}

/// (program, its name)
const CHROMIUMS: &[(&str, &str)] = &[
    ("google-chrome-stable", "Chrome"),
    ("google-chrome", "Chrome"),
    ("chromium", "Chromium"),
    ("chromium-browser", "Chromium"),
    ("microsoft-edge-stable", "Edge"),
    ("microsoft-edge", "Edge"),
    ("brave-browser", "Brave"),
    ("brave", "Brave"),
    ("vivaldi-stable", "Vivaldi"),
    ("vivaldi", "Vivaldi"),
];

/// (Flatpak app id, its name)
const CHROMIUM_FLATPAKS: &[(&str, &str)] = &[
    ("com.google.Chrome", "Chrome"),
    ("org.chromium.Chromium", "Chromium"),
    ("com.microsoft.Edge", "Edge"),
    ("com.brave.Browser", "Brave"),
    ("com.vivaldi.Vivaldi", "Vivaldi"),
    ("io.github.ungoogled_software.ungoogled_chromium", "Chromium"),
];

const FIREFOX_FLATPAK: &str = "org.mozilla.firefox";

/// Our folder in a cache.
const DIR: &str = "daytona-usa-ultimate";
/// The window's class (X11) or app id (Wayland).
const CLASS: &str = "daytona-usa-ultimate";

pub fn spawn_quiet<S: AsRef<OsStr>>(program: &str, args: &[S]) -> io::Result<Child> {
    Command::new(program).args(args).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).spawn()
}

fn home() -> PathBuf {
    std::env::var_os("HOME").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("/tmp"))
}

fn cache_home() -> PathBuf {
    std::env::var_os("XDG_CACHE_HOME").map(PathBuf::from).filter(|p| p.is_absolute()).unwrap_or_else(|| home().join(".cache"))
}

fn which(name: &str) -> Option<PathBuf> {
    use std::os::unix::fs::PermissionsExt;
    let path = std::env::var_os("PATH")?;
    std::env::split_paths(&path)
        .map(|d| d.join(name))
        .find(|p| p.metadata().map(|m| m.is_file() && m.permissions().mode() & 0o111 != 0).unwrap_or(false))
}

fn flatpak_has(id: &str) -> bool {
    which("flatpak").is_some()
        && [PathBuf::from("/var/lib/flatpak/app"), home().join(".local/share/flatpak/app")]
            .iter()
            .any(|d| d.join(id).join("current").exists())
}

/// The snap a program runs as, if it does (Ubuntu's Chromium and Firefox): a
/// snap sees no hidden folders in the home, so its profile goes in its own.
fn snap_of(program: &str) -> Option<&'static str> {
    let snap = match program {
        "chromium" | "chromium-browser" => "chromium",
        "firefox" => "firefox",
        _ => return None,
    };
    Path::new("/snap").join(snap).join("current").exists().then_some(snap)
}

/// Where a browser keeps our profile: somewhere it can see.
fn profile_dir(flatpak: Option<&str>, program: Option<&str>, kind: &str) -> PathBuf {
    if let Some(id) = flatpak {
        return home().join(".var/app").join(id).join("cache").join(DIR);
    }
    if let Some(snap) = program.and_then(snap_of) {
        return home().join("snap").join(snap).join("common").join(DIR);
    }
    cache_home().join(DIR).join(kind)
}

/// Started, and still running a moment later or handed over to a browser already running.
fn launch(mut cmd: Command) -> bool {
    let Ok(mut child) = cmd.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).spawn() else {
        return false;
    };
    let t = Instant::now();
    while t.elapsed() < Duration::from_secs(3) {
        match child.try_wait() {
            Ok(Some(status)) => return status.success(),
            Ok(None) => std::thread::sleep(Duration::from_millis(100)),
            Err(_) => return false,
        }
    }
    std::thread::spawn(move || {
        let _ = child.wait();
    });
    true
}

fn command(flatpak: Option<&str>, program: &str) -> Command {
    match flatpak {
        Some(id) => {
            let mut c = Command::new("flatpak");
            c.args(["run", id]);
            c
        }
        None => Command::new(program),
    }
}

fn chromium(url: &str, flatpak: Option<&str>, program: &str) -> bool {
    let profile = profile_dir(flatpak, Some(program), "chromium");
    if std::fs::create_dir_all(&profile).is_err() {
        return false;
    }
    let mut c = command(flatpak, program);
    c.arg(format!("--app={url}"))
        .arg(OsString::from(format!("--user-data-dir={}", profile.display())))
        .args([
            "--no-first-run",
            "--no-default-browser-check",
            "--password-store=basic",
            "--autoplay-policy=no-user-gesture-required",
            "--window-size=1280,800",
            "--disable-features=Translate",
        ])
        .arg(format!("--class={CLASS}"));
    launch(c)
}

/// A Firefox profile that shows the page alone: no toolbars, no first-run pages
/// or prompts, sound without a click first.
const FIREFOX_PREFS: &str = r#"user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
user_pref("browser.tabs.inTitlebar", 0);
user_pref("browser.toolbars.bookmarks.visibility", "never");
user_pref("sidebar.revamp", false);
user_pref("sidebar.verticalTabs", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.startup.firstrunSkipsHomepage", true);
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("startup.homepage_override_url", "");
user_pref("browser.aboutwelcome.enabled", false);
user_pref("trailhead.firstrun.didSeeAboutWelcome", true);
user_pref("datareporting.policy.firstRunURL", "");
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.disableResetPrompt", true);
user_pref("browser.uitour.enabled", false);
user_pref("browser.translations.automaticallyPopup", false);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.warnOnQuit", false);
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.blocking_policy", 0);
user_pref("signon.rememberSignons", false);
user_pref("extensions.pocket.enabled", false);
"#;

const FIREFOX_CHROME_CSS: &str = "#navigator-toolbox, #sidebar-main, #sidebar-box { visibility: collapse !important; }\n";

fn firefox(url: &str, flatpak: Option<&str>) -> bool {
    let program = "firefox";
    if flatpak.is_none() && which(program).is_none() {
        return false;
    }
    let profile = profile_dir(flatpak, Some(program), "firefox");
    let made = std::fs::create_dir_all(profile.join("chrome"))
        .and_then(|_| std::fs::write(profile.join("user.js"), FIREFOX_PREFS))
        .and_then(|_| std::fs::write(profile.join("chrome/userChrome.css"), FIREFOX_CHROME_CSS));
    if made.is_err() {
        return false;
    }
    let mut c = command(flatpak, program);
    c.arg("--new-instance")
        .arg("--profile")
        .arg(&profile)
        .args(["--name", CLASS, "--class", CLASS, "--width", "1280", "--height", "800"])
        .arg(url);
    launch(c)
}

pub fn open(url: &str) -> Opened {
    let only = std::env::var("DAYTONA_BROWSER").unwrap_or_default();
    let any = only.is_empty();
    if any || only == "chromium" {
        for &(program, name) in CHROMIUMS {
            if which(program).is_some() && chromium(url, None, program) {
                return Opened::Window(name);
            }
        }
        for &(id, name) in CHROMIUM_FLATPAKS {
            if flatpak_has(id) && chromium(url, Some(id), id) {
                return Opened::Window(name);
            }
        }
    }
    if any || only == "firefox" {
        if firefox(url, None) {
            return Opened::Window("Firefox");
        }
        if flatpak_has(FIREFOX_FLATPAK) && firefox(url, Some(FIREFOX_FLATPAK)) {
            return Opened::Window("Firefox");
        }
    }
    if (any || only == "tab") && which("xdg-open").is_some() {
        let mut c = Command::new("xdg-open");
        c.arg(url);
        if launch(c) {
            return Opened::Tab;
        }
    }
    Opened::No
}
