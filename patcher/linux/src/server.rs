//! The page and its calls, over HTTP on 127.0.0.1 only.
//!
//! The calls are the Windows app's commands (src-tauri/src/main.rs): out_dir,
//! pick, pick_out_dir, inspect, build and reveal, each a POST of its arguments
//! as JSON answered with {"ok": value} or {"err": message}. build answers line
//! by line as it goes, {"progress": ...} until the last. alive is held open by
//! the page while it's there, a newline every two seconds, so the builder knows
//! when the page has gone.
//!
//! Other pages in the same browser can reach 127.0.0.1 too, so a call needs the
//! token from the page's address in an X-Token header (which a page from
//! anywhere else can't send here), and the Host header must be this address
//! (against a name that resolves to 127.0.0.1).

use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::Path;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

use daytona_ultimate_core::builder;
use serde_json::{json, Value};

use crate::dialog;

mod ui {
    include!(concat!(env!("OUT_DIR"), "/ui.rs"));
}

#[derive(Default)]
pub struct State {
    alive: AtomicUsize,
    seen: AtomicBool,
    building: AtomicBool,
}

impl State {
    /// The page is open, or a build is running.
    pub fn busy(&self) -> bool {
        self.alive.load(Ordering::SeqCst) > 0 || self.building.load(Ordering::SeqCst)
    }

    /// The page has been here.
    pub fn seen(&self) -> bool {
        self.seen.load(Ordering::SeqCst)
    }
}

pub struct Server {
    listener: TcpListener,
    host: String,
    token: String,
    state: Arc<State>,
}

/// 128 random bits, as hex.
fn token() -> io::Result<String> {
    let mut b = [0u8; 16];
    std::fs::File::open("/dev/urandom")?.read_exact(&mut b)?;
    Ok(b.iter().map(|x| format!("{x:02x}")).collect())
}

impl Server {
    /// On port, or any free one if that's taken.
    pub fn start(port: u16) -> io::Result<Server> {
        let listener = TcpListener::bind(("127.0.0.1", port)).or_else(|_| TcpListener::bind(("127.0.0.1", 0)))?;
        let host = format!("127.0.0.1:{}", listener.local_addr()?.port());
        Ok(Server { listener, host, token: token()?, state: Arc::default() })
    }

    pub fn url(&self) -> String {
        format!("http://{}/?t={}", self.host, self.token)
    }

    pub fn state(&self) -> Arc<State> {
        self.state.clone()
    }

    pub fn run(self) {
        let shared = Arc::new((self.host, self.token));
        for stream in self.listener.incoming().flatten() {
            let shared = shared.clone();
            let state = self.state.clone();
            std::thread::spawn(move || {
                let _ = handle(stream, &shared.0, &shared.1, &state);
            });
        }
    }
}

struct Request {
    method: String,
    path: String,
    host: String,
    token: String,
    body: Vec<u8>,
}

fn read_request(stream: &TcpStream) -> io::Result<Request> {
    let bad = |m: &str| io::Error::new(io::ErrorKind::InvalidData, m.to_string());
    let mut r = BufReader::new(stream.take(1 << 20));
    let mut line = String::new();
    r.read_line(&mut line)?;
    let mut parts = line.split_whitespace();
    let method = parts.next().ok_or_else(|| bad("no method"))?.to_string();
    let target = parts.next().ok_or_else(|| bad("no path"))?;
    let path = target.split('?').next().unwrap_or("/").to_string();
    let (mut host, mut token, mut length) = (String::new(), String::new(), 0usize);
    loop {
        line.clear();
        if r.read_line(&mut line)? == 0 {
            return Err(bad("headers cut short"));
        }
        let l = line.trim_end();
        if l.is_empty() {
            break;
        }
        if let Some((k, v)) = l.split_once(':') {
            let v = v.trim();
            match k.trim().to_ascii_lowercase().as_str() {
                "host" => host = v.to_string(),
                "x-token" => token = v.to_string(),
                "content-length" => length = v.parse().map_err(|_| bad("content-length"))?,
                _ => {}
            }
        }
    }
    if length > 1 << 16 {
        return Err(bad("body too big"));
    }
    let mut body = vec![0; length];
    r.read_exact(&mut body)?;
    Ok(Request { method, path, host, token, body })
}

fn respond(mut s: &TcpStream, status: &str, ctype: &str, body: &[u8]) -> io::Result<()> {
    write!(
        s,
        "HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {}\r\nCache-Control: no-store\r\n\
         X-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n",
        body.len()
    )?;
    s.write_all(body)?;
    s.flush()
}

/// An answer written as it comes, a chunk at a time.
struct Chunked<'a>(&'a TcpStream);

impl Chunked<'_> {
    fn start(s: &TcpStream) -> io::Result<Chunked<'_>> {
        let mut w = s;
        write!(
            w,
            "HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\nTransfer-Encoding: chunked\r\n\
             Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n"
        )?;
        w.flush()?;
        Ok(Chunked(s))
    }

    fn line(&mut self, v: &Value) -> io::Result<()> {
        let mut text = v.to_string();
        text.push('\n');
        self.raw(text.as_bytes())
    }

    fn raw(&mut self, data: &[u8]) -> io::Result<()> {
        let mut w = self.0;
        write!(w, "{:x}\r\n", data.len())?;
        w.write_all(data)?;
        w.write_all(b"\r\n")?;
        w.flush()
    }

    fn end(self) -> io::Result<()> {
        let mut w = self.0;
        w.write_all(b"0\r\n\r\n")?;
        w.flush()
    }
}

fn result<T: serde::Serialize>(r: Result<T, String>) -> Value {
    match r {
        Ok(v) => json!({ "ok": v }),
        Err(e) => json!({ "err": e }),
    }
}

fn arg(args: &Value, name: &str) -> Result<String, String> {
    args.get(name).and_then(Value::as_str).map(str::to_string).ok_or_else(|| format!("no {name} given"))
}

fn handle(stream: TcpStream, host: &str, token: &str, state: &State) -> io::Result<()> {
    stream.set_read_timeout(Some(Duration::from_secs(30)))?;
    let req = read_request(&stream)?;
    if req.host != host {
        return respond(&stream, "403 Forbidden", "text/plain", b"");
    }
    if let Some(call) = req.path.strip_prefix("/api/") {
        if req.token != token {
            return respond(&stream, "403 Forbidden", "text/plain", b"");
        }
        let args: Value = serde_json::from_slice(&req.body).unwrap_or(Value::Null);
        let answer = match (req.method.as_str(), call) {
            ("GET", "alive") => return alive(&stream, state),
            ("POST", "build") => return build(&stream, &args, state),
            ("POST", "out_dir") => json!({ "ok": builder::default_out_dir() }),
            ("POST", "pick") => result(dialog::pick_disc()),
            ("POST", "pick_out_dir") => {
                result(dialog::pick_folder().map(|d| d.map(|d| Path::new(&d).join(builder::OUT_NAME).display().to_string())))
            }
            ("POST", "inspect") => result(arg(&args, "path").and_then(|p| builder::inspect(Path::new(&p)))),
            ("POST", "reveal") => result(arg(&args, "path").and_then(|p| reveal(&p))),
            _ => return respond(&stream, "404 Not Found", "text/plain", b""),
        };
        return respond(&stream, "200 OK", "application/json", answer.to_string().as_bytes());
    }
    if req.method != "GET" {
        return respond(&stream, "405 Method Not Allowed", "text/plain", b"");
    }
    let name = match req.path.as_str() {
        "/" => "index.html",
        p => p.trim_start_matches('/'),
    };
    match ui::UI.iter().find(|(n, _, _)| *n == name) {
        Some((_, ctype, data)) => respond(&stream, "200 OK", ctype, data),
        None => respond(&stream, "404 Not Found", "text/plain", b""),
    }
}

/// Held open while the page is there.
fn alive(stream: &TcpStream, state: &State) -> io::Result<()> {
    state.alive.fetch_add(1, Ordering::SeqCst);
    state.seen.store(true, Ordering::SeqCst);
    let r = (|| -> io::Result<()> {
        let mut c = Chunked::start(stream)?;
        loop {
            c.raw(b"\n")?;
            std::thread::sleep(Duration::from_secs(2));
        }
    })();
    state.alive.fetch_sub(1, Ordering::SeqCst);
    r
}

/// The build, its progress a line at a time. It runs to the end even if the
/// page goes, so the disc is never left half written.
fn build(stream: &TcpStream, args: &Value, state: &State) -> io::Result<()> {
    let (cce, dusa, out) = match (arg(args, "cce"), arg(args, "dusa"), arg(args, "out")) {
        (Ok(c), Ok(d), Ok(o)) => (c, d, o),
        (c, d, o) => {
            let e = [c, d, o].into_iter().find_map(Result::err).unwrap();
            return respond(stream, "200 OK", "application/json", json!({ "err": e }).to_string().as_bytes());
        }
    };
    if state.building.swap(true, Ordering::SeqCst) {
        let e = json!({ "err": "A disc is being built already." });
        return respond(stream, "200 OK", "application/json", e.to_string().as_bytes());
    }
    let mut c = Chunked::start(stream).ok();
    let r = builder::build(Path::new(&cce), Path::new(&dusa), Path::new(&out), |p| {
        if let Some(w) = c.as_mut() {
            if w.line(&json!({ "progress": p })).is_err() {
                c = None;
            }
        }
    });
    state.building.store(false, Ordering::SeqCst);
    match c {
        Some(mut w) => {
            w.line(&result(r))?;
            w.end()
        }
        None => Ok(()),
    }
}

/// Show the folder the file is in, in the desktop's file manager.
fn reveal(path: &str) -> Result<(), String> {
    let dir = Path::new(path).parent().unwrap_or(Path::new("."));
    crate::browser::spawn_quiet("xdg-open", &[dir.as_os_str()]).map(|_| ()).map_err(|e| format!("Can't open {}: {e}", dir.display()))
}
