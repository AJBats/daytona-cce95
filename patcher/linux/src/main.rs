//! The Linux disc builder: one static file with nothing to install. It serves the
//! builder's page (the same patcher/ui the Windows app shows) to a browser on this
//! machine only, opened as a window of its own where the browser allows it
//! (browser.rs), and does the page's work: the desktop's file dialogs (dialog.rs),
//! checking discs and building ours (daytona_ultimate_core). It exits when the
//! page is closed.
//!
//! `--inspect <disc>` and `--build <cce> <dusa> <out dir>` run without the page;
//! `--no-browser` prints the page's address instead of opening it.

mod browser;
mod dialog;
mod server;

use std::path::Path;
use std::time::{Duration, Instant};

use daytona_ultimate_core::builder;

/// The page's port when it's free: one port keeps the page's own settings (the
/// sound switch) from one run to the next.
const PORT: u16 = 29095;

/// `--inspect <disc>` and `--build <cce> <dusa> <out dir>`, without the page.
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
        Some("--help") | Some("-h") => {
            println!(
                "Daytona USA Ultimate disc builder {}\n\n\
                 Run it with no arguments to open the builder's window.\n\n\
                 --inspect <disc>                 say which game a disc is, and check it\n\
                 --build <cce> <dusa> <out dir>   build the disc without the window\n\
                 --no-browser                     print the window's address instead of opening it",
                env!("CARGO_PKG_VERSION")
            );
            Some(0)
        }
        _ => None,
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if let Some(code) = cli(&args) {
        std::process::exit(code);
    }
    let no_browser = args.iter().any(|a| a == "--no-browser");
    if let Some(a) = args.iter().find(|a| a.as_str() != "--no-browser") {
        eprintln!("Unknown argument {a}: see --help");
        std::process::exit(2);
    }

    let server = match server::Server::start(PORT) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("Can't start the builder's page: {e}");
            std::process::exit(1);
        }
    };
    let url = server.url();
    let state = server.state();
    std::thread::spawn(move || server.run());

    let opened = if no_browser { browser::Opened::No } else { browser::open(&url) };
    match opened {
        browser::Opened::Window(name) => println!("Daytona USA Ultimate builder: opened in a {name} window."),
        browser::Opened::Tab => println!("Daytona USA Ultimate builder: opened in your web browser."),
        browser::Opened::No => {}
    }
    println!("The builder's page is at {url}\nIt closes when that page does.");

    // Gone when the page has been closed a few seconds (a reload comes straight
    // back) and no build is running. A page that never arrives, from a browser
    // that was opened: given up on after two minutes.
    let start = Instant::now();
    let mut last_seen = Instant::now();
    loop {
        std::thread::sleep(Duration::from_millis(500));
        if state.busy() {
            last_seen = Instant::now();
        } else if state.seen() {
            if last_seen.elapsed() > Duration::from_secs(6) {
                break;
            }
        } else if opened != browser::Opened::No && start.elapsed() > Duration::from_secs(120) {
            eprintln!("The page never opened. Open {url} in a web browser, or run this with --no-browser.");
            break;
        }
    }
}
