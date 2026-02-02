//! Gorgon Desktop Application
//!
//! Entry point for the Tauri desktop application.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

fn main() {
    gorgon_desktop_lib::run()
}
