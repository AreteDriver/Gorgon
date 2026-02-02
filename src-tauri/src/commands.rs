//! Tauri commands for IPC between frontend and backend

use std::fs;
use std::path::Path;

use serde::Serialize;
use tauri::command;

use crate::error::{Error, Result};
use crate::git::{self, BranchInfo, LogEntry, StatusEntry};

// ============================================================================
// File Operations
// ============================================================================

/// Read a file's contents
#[command]
pub async fn read_file(path: String) -> Result<String> {
    validate_path(&path)?;
    Ok(fs::read_to_string(&path)?)
}

/// Write content to a file
#[command]
pub async fn write_file(path: String, content: String) -> Result<()> {
    validate_path(&path)?;

    // Create parent directories if they don't exist
    if let Some(parent) = Path::new(&path).parent() {
        fs::create_dir_all(parent)?;
    }

    Ok(fs::write(&path, content)?)
}

/// List directory contents
#[command]
pub async fn list_directory(path: String) -> Result<Vec<DirectoryEntry>> {
    validate_path(&path)?;

    let mut entries = Vec::new();
    for entry in fs::read_dir(&path)? {
        let entry = entry?;
        let metadata = entry.metadata()?;
        entries.push(DirectoryEntry {
            name: entry.file_name().to_string_lossy().to_string(),
            path: entry.path().to_string_lossy().to_string(),
            is_directory: metadata.is_dir(),
            size: metadata.len(),
        });
    }

    // Sort: directories first, then alphabetically
    entries.sort_by(|a, b| match (a.is_directory, b.is_directory) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
    });

    Ok(entries)
}

/// Check if a file exists
#[command]
pub async fn file_exists(path: String) -> Result<bool> {
    Ok(Path::new(&path).exists())
}

/// Create a directory
#[command]
pub async fn create_directory(path: String) -> Result<()> {
    validate_path(&path)?;
    Ok(fs::create_dir_all(&path)?)
}

/// Delete a file or directory
#[command]
pub async fn delete_file(path: String) -> Result<()> {
    validate_path(&path)?;

    let p = Path::new(&path);
    if p.is_dir() {
        fs::remove_dir_all(p)?;
    } else {
        fs::remove_file(p)?;
    }

    Ok(())
}

#[derive(Debug, Serialize)]
pub struct DirectoryEntry {
    pub name: String,
    pub path: String,
    pub is_directory: bool,
    pub size: u64,
}

// ============================================================================
// Git Operations
// ============================================================================

/// Get git repository status
#[command]
pub async fn git_status(repo_path: String) -> Result<Vec<StatusEntry>> {
    let repo = git::open_repo(&repo_path)?;
    git::get_status(&repo)
}

/// Get git diff
#[command]
pub async fn git_diff(repo_path: String, staged: bool) -> Result<String> {
    let repo = git::open_repo(&repo_path)?;
    git::get_diff(&repo, staged)
}

/// Create a git commit
#[command]
pub async fn git_commit(repo_path: String, message: String) -> Result<String> {
    let repo = git::open_repo(&repo_path)?;
    git::create_commit(&repo, &message)
}

/// List git branches
#[command]
pub async fn git_branch(repo_path: String) -> Result<Vec<BranchInfo>> {
    let repo = git::open_repo(&repo_path)?;
    git::list_branches(&repo)
}

/// Checkout a branch
#[command]
pub async fn git_checkout(repo_path: String, branch_name: String) -> Result<()> {
    let repo = git::open_repo(&repo_path)?;
    git::checkout_branch(&repo, &branch_name)
}

/// Push to remote
#[command]
pub async fn git_push(
    repo_path: String,
    remote: Option<String>,
    branch: Option<String>,
) -> Result<()> {
    let repo = git::open_repo(&repo_path)?;
    let remote_name = remote.unwrap_or_else(|| "origin".to_string());

    // Get current branch if not specified
    let branch_name = match branch {
        Some(b) => b,
        None => {
            let head = repo.head()?;
            head.shorthand()
                .ok_or_else(|| Error::Custom("Cannot determine current branch".to_string()))?
                .to_string()
        }
    };

    git::push_branch(&repo, &remote_name, &branch_name)
}

/// Pull from remote
#[command]
pub async fn git_pull(
    repo_path: String,
    remote: Option<String>,
    branch: Option<String>,
) -> Result<()> {
    let repo = git::open_repo(&repo_path)?;
    let remote_name = remote.unwrap_or_else(|| "origin".to_string());

    // Get current branch if not specified
    let branch_name = match branch {
        Some(b) => b,
        None => {
            let head = repo.head()?;
            head.shorthand()
                .ok_or_else(|| Error::Custom("Cannot determine current branch".to_string()))?
                .to_string()
        }
    };

    git::pull_branch(&repo, &remote_name, &branch_name)
}

/// Get git log
#[command]
pub async fn git_log(repo_path: String, count: Option<usize>) -> Result<Vec<LogEntry>> {
    let repo = git::open_repo(&repo_path)?;
    git::get_log(&repo, count.unwrap_or(20))
}

/// Create a new branch
#[command]
pub async fn git_create_branch(repo_path: String, branch_name: String) -> Result<()> {
    let repo = git::open_repo(&repo_path)?;
    git::create_branch(&repo, &branch_name)
}

// ============================================================================
// Notifications
// ============================================================================

/// Send a native notification
#[command]
pub async fn send_notification(
    app_handle: tauri::AppHandle,
    title: String,
    body: String,
) -> Result<()> {
    use tauri_plugin_notification::NotificationExt;

    app_handle
        .notification()
        .builder()
        .title(&title)
        .body(&body)
        .show()
        .map_err(|e| Error::Custom(e.to_string()))?;

    Ok(())
}

// ============================================================================
// System Info
// ============================================================================

#[derive(Debug, Serialize)]
pub struct AppInfo {
    pub name: String,
    pub version: String,
    pub tauri_version: String,
}

/// Get application info
#[command]
pub async fn get_app_info() -> Result<AppInfo> {
    Ok(AppInfo {
        name: "Gorgon Desktop".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        tauri_version: tauri::VERSION.to_string(),
    })
}

// ============================================================================
// Helpers
// ============================================================================

/// Validate that a path is allowed
fn validate_path(path: &str) -> Result<()> {
    let path = Path::new(path);

    // Block access to sensitive paths
    let blocked_patterns = [
        "/.ssh/",
        "/.gnupg/",
        "/.config/",
        "/etc/",
        "/.env",
        ".env",
        "/credentials",
        "credentials.json",
        "/secrets",
    ];

    let path_str = path.to_string_lossy().to_lowercase();
    for pattern in blocked_patterns {
        if path_str.contains(pattern) {
            return Err(Error::NotAllowed(format!(
                "Access to path containing '{}' is not allowed",
                pattern
            )));
        }
    }

    Ok(())
}
