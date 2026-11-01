// No console window behind the app in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod builder;
mod cdrom;
mod disc;
mod patch;

use std::path::Path;

use tauri::{AppHandle, Emitter};
use tauri_plugin_dialog::DialogExt;

/// Where the disc goes unasked: a folder of its own beside the app. Not if the app
/// can't write there, or runs from the temporary folder (opened straight out of a
/// zip, Windows unpacks it there and clears it later).
#[tauri::command]
fn out_dir() -> Option<String> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    if let Ok(tmp) = std::env::temp_dir().canonicalize() {
        if dir.canonicalize().map(|d| d.starts_with(&tmp)).unwrap_or(false) {
            return None;
        }
    }
    let probe = dir.join(".daytona-ultimate-write-test");
    std::fs::write(&probe, b"").ok()?;
    let _ = std::fs::remove_file(&probe);
    Some(dir.join(builder::OUT_NAME).display().to_string())
}

/// Ask where the disc should go: it's written into a folder of its own in the one chosen.
#[tauri::command]
async fn pick_out_dir(app: AppHandle) -> Option<String> {
    tauri::async_runtime::spawn_blocking(move || {
        app.dialog().file().set_title("Choose where to write Daytona USA Ultimate").blocking_pick_folder()
    })
    .await
    .ok()
    .flatten()
    .and_then(|f| f.into_path().ok())
    .map(|p| p.join(builder::OUT_NAME).display().to_string())
}

#[tauri::command]
async fn pick(app: AppHandle) -> Option<String> {
    tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title("Choose a disc: its .cue sheet, or a .zip of it")
            .add_filter("Disc image (.cue, .zip)", &["cue", "zip", "bin"])
            .blocking_pick_file()
    })
    .await
    .ok()
    .flatten()
    .and_then(|f| f.into_path().ok())
    .map(|p| p.display().to_string())
}

#[tauri::command]
async fn inspect(path: String) -> Result<builder::Report, String> {
    tauri::async_runtime::spawn_blocking(move || builder::inspect(Path::new(&path)))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn build(app: AppHandle, cce: String, dusa: String, out: String) -> Result<builder::Done, String> {
    tauri::async_runtime::spawn_blocking(move || {
        builder::build(Path::new(&cce), Path::new(&dusa), Path::new(&out), |p| {
            let _ = app.emit("build-progress", p);
        })
    })
    .await
    .map_err(|e| e.to_string())?
}

/// Show the file in the system's file browser.
#[tauri::command]
fn reveal(path: String) -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        std::process::Command::new("explorer").raw_arg(format!("/select,\"{path}\"")).spawn().map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "macos")]
    std::process::Command::new("open").args(["-R", &path]).spawn().map_err(|e| e.to_string())?;
    #[cfg(all(unix, not(target_os = "macos")))]
    std::process::Command::new("xdg-open")
        .arg(Path::new(&path).parent().unwrap_or(Path::new(".")))
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}

/// `--inspect <disc>` and `--build <cce> <dusa> <out dir>`, without the window.
fn cli(args: &[String]) -> Option<i32> {
    match args.first().map(String::as_str) {
        Some("--inspect") if args.len() == 2 => Some(match builder::inspect(Path::new(&args[1])) {
            Ok(r) => {
                println!("{}: {}", r.game, r.name);
                0
            }
            Err(e) => {
                eprintln!("{e}");
                1
            }
        }),
        Some("--build") if args.len() == 4 => {
            let r = builder::build(Path::new(&args[1]), Path::new(&args[2]), Path::new(&args[3]), |p| {
                if let Some(l) = p.log {
                    println!("{:5.1}%  {l}", p.fraction * 100.0);
                }
            });
            Some(match r {
                Ok(d) => {
                    println!("{}", d.cue);
                    0
                }
                Err(e) => {
                    eprintln!("{e}");
                    1
                }
            })
        }
        _ => None,
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let Some(code) = cli(&args) {
        std::process::exit(code);
    }
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![pick, inspect, out_dir, pick_out_dir, build, reveal])
        .run(tauri::generate_context!())
        .expect("the app failed to start");
}
