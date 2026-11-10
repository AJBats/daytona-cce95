//! The page (patcher/ui) goes inside the builder: the files git tracks there, so
//! sounds and art lying around untracked stay out. A new file needs `git add`.

use std::fmt::Write as _;
use std::path::Path;
use std::process::Command;

fn content_type(name: &str) -> &'static str {
    match name.rsplit('.').next().unwrap_or("") {
        "html" => "text/html; charset=utf-8",
        "js" => "text/javascript; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "jpg" | "jpeg" => "image/jpeg",
        "png" => "image/png",
        "svg" => "image/svg+xml",
        "ico" => "image/x-icon",
        "mp3" => "audio/mpeg",
        "md" | "txt" => "text/plain; charset=utf-8",
        _ => "application/octet-stream",
    }
}

fn main() {
    let patcher = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf();
    let out = Command::new("git")
        .args(["ls-files", "-z", "ui"])
        .current_dir(&patcher)
        .output()
        .expect("git, to list the page's files");
    assert!(out.status.success(), "git ls-files failed");
    let mut names: Vec<String> = String::from_utf8(out.stdout)
        .unwrap()
        .split('\0')
        .filter(|s| !s.is_empty())
        .map(|s| s.strip_prefix("ui/").unwrap().to_string())
        .collect();
    names.sort();
    assert!(names.iter().any(|n| n == "index.html"), "no ui/index.html");

    let mut code = String::from("pub static UI: &[(&str, &str, &[u8])] = &[\n");
    for n in &names {
        let path = patcher.join("ui").join(n);
        println!("cargo:rerun-if-changed={}", path.display());
        writeln!(code, "    ({n:?}, {:?}, include_bytes!({:?})),", content_type(n), path.display().to_string()).unwrap();
    }
    code.push_str("];\n");
    println!("cargo:rerun-if-changed={}", patcher.join("ui").display());
    println!("cargo:rerun-if-changed={}", patcher.parent().unwrap().join(".git/index").display());
    let dest = Path::new(&std::env::var("OUT_DIR").unwrap()).join("ui.rs");
    std::fs::write(dest, code).unwrap();
}
