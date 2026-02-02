//! Gorgon Desktop - Tauri backend library
//!
//! Provides native capabilities for the Gorgon desktop application:
//! - File system operations for self-improvement
//! - Git operations for code management
//! - Native notifications

mod commands;
mod error;
mod git;

pub use commands::*;
pub use error::Error;

use tauri::Manager;

/// Initialize and run the Tauri application
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            // File operations
            commands::read_file,
            commands::write_file,
            commands::list_directory,
            commands::file_exists,
            commands::create_directory,
            commands::delete_file,
            // Git operations
            commands::git_status,
            commands::git_diff,
            commands::git_commit,
            commands::git_branch,
            commands::git_checkout,
            commands::git_push,
            commands::git_pull,
            commands::git_log,
            commands::git_create_branch,
            // Notifications
            commands::send_notification,
            // System info
            commands::get_app_info,
        ])
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                let window = app.get_webview_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
