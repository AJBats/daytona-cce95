//! The disc builder's work, shared by the Windows app (src-tauri) and the Linux
//! one (linux): checking the player's discs and building ours from them.

pub mod builder;
mod cdrom;
mod disc;
mod patch;
