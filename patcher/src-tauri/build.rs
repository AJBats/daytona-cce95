use std::path::Path;

fn main() {
    // the release patch goes inside the app; `make release-patch` makes it
    let patch = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../build/release/ultimate.patch");
    if !patch.exists() {
        panic!("{} is missing: run `make release-patch` first", patch.display());
    }
    println!("cargo:rerun-if-changed={}", patch.display());
    tauri_build::build()
}
