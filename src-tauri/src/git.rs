//! Git operations module

use git2::{DiffOptions, Repository, StatusOptions};
use serde::Serialize;

use crate::error::{Error, Result};

/// Git status entry
#[derive(Debug, Serialize)]
pub struct StatusEntry {
    pub path: String,
    pub status: String,
    pub staged: bool,
}

/// Git log entry
#[derive(Debug, Serialize)]
pub struct LogEntry {
    pub id: String,
    pub message: String,
    pub author: String,
    pub time: i64,
}

/// Git branch info
#[derive(Debug, Serialize)]
pub struct BranchInfo {
    pub name: String,
    pub is_current: bool,
    pub is_remote: bool,
}

/// Open a git repository at the given path
pub fn open_repo(path: &str) -> Result<Repository> {
    Repository::discover(path).map_err(|_| Error::NoRepository)
}

/// Get repository status
pub fn get_status(repo: &Repository) -> Result<Vec<StatusEntry>> {
    let mut opts = StatusOptions::new();
    opts.include_untracked(true)
        .recurse_untracked_dirs(true)
        .include_ignored(false);

    let statuses = repo.statuses(Some(&mut opts))?;
    let mut entries = Vec::new();

    for entry in statuses.iter() {
        let status = entry.status();
        let path = entry.path().unwrap_or("").to_string();

        let status_str = if status.is_index_new() {
            "new"
        } else if status.is_index_modified() || status.is_wt_modified() {
            "modified"
        } else if status.is_index_deleted() || status.is_wt_deleted() {
            "deleted"
        } else if status.is_index_renamed() || status.is_wt_renamed() {
            "renamed"
        } else if status.is_wt_new() {
            "untracked"
        } else if status.is_conflicted() {
            "conflicted"
        } else {
            "unknown"
        };

        let staged = status.is_index_new()
            || status.is_index_modified()
            || status.is_index_deleted()
            || status.is_index_renamed();

        entries.push(StatusEntry {
            path,
            status: status_str.to_string(),
            staged,
        });
    }

    Ok(entries)
}

/// Get diff of changes
pub fn get_diff(repo: &Repository, staged: bool) -> Result<String> {
    let mut opts = DiffOptions::new();
    opts.include_untracked(true);

    let diff = if staged {
        let head = repo.head()?.peel_to_tree()?;
        let index = repo.index()?;
        repo.diff_tree_to_index(Some(&head), Some(&index), Some(&mut opts))?
    } else {
        repo.diff_index_to_workdir(None, Some(&mut opts))?
    };

    let mut output = String::new();
    diff.print(git2::DiffFormat::Patch, |_delta, _hunk, line| {
        let prefix = match line.origin() {
            '+' => "+",
            '-' => "-",
            ' ' => " ",
            _ => "",
        };
        output.push_str(prefix);
        output.push_str(&String::from_utf8_lossy(line.content()));
        true
    })?;

    Ok(output)
}

/// Create a commit
pub fn create_commit(repo: &Repository, message: &str) -> Result<String> {
    let sig = repo.signature().map_err(|_| {
        Error::Custom(
            "Git user not configured. Run 'git config user.name' and 'git config user.email'"
                .to_string(),
        )
    })?;

    let mut index = repo.index()?;
    let tree_id = index.write_tree()?;
    let tree = repo.find_tree(tree_id)?;

    let parent = repo.head()?.peel_to_commit()?;
    let commit_id = repo.commit(Some("HEAD"), &sig, &sig, message, &tree, &[&parent])?;

    Ok(commit_id.to_string())
}

/// Get recent commits
pub fn get_log(repo: &Repository, count: usize) -> Result<Vec<LogEntry>> {
    let mut revwalk = repo.revwalk()?;
    revwalk.push_head()?;

    let mut entries = Vec::new();
    for (i, oid) in revwalk.enumerate() {
        if i >= count {
            break;
        }
        let oid = oid?;
        let commit = repo.find_commit(oid)?;

        entries.push(LogEntry {
            id: oid.to_string()[..8].to_string(),
            message: commit.summary().unwrap_or("").to_string(),
            author: commit.author().name().unwrap_or("").to_string(),
            time: commit.time().seconds(),
        });
    }

    Ok(entries)
}

/// List branches
pub fn list_branches(repo: &Repository) -> Result<Vec<BranchInfo>> {
    let branches = repo.branches(None)?;
    let head = repo.head().ok();
    let current_branch = head.as_ref().and_then(|h| h.shorthand()).unwrap_or("");

    let mut infos = Vec::new();
    for branch in branches {
        let (branch, branch_type) = branch?;
        let name = branch.name()?.unwrap_or("").to_string();
        let is_remote = matches!(branch_type, git2::BranchType::Remote);
        let is_current = !is_remote && name == current_branch;

        infos.push(BranchInfo {
            name,
            is_current,
            is_remote,
        });
    }

    Ok(infos)
}

/// Checkout a branch
pub fn checkout_branch(repo: &Repository, branch_name: &str) -> Result<()> {
    let branch = repo.find_branch(branch_name, git2::BranchType::Local)?;
    let reference = branch.into_reference();
    let tree = reference.peel_to_tree()?;

    repo.checkout_tree(tree.as_object(), None)?;
    repo.set_head(
        reference
            .name()
            .ok_or_else(|| Error::Custom("Invalid branch reference".to_string()))?,
    )?;

    Ok(())
}

/// Create a new branch
pub fn create_branch(repo: &Repository, branch_name: &str) -> Result<()> {
    let head = repo.head()?.peel_to_commit()?;
    repo.branch(branch_name, &head, false)?;
    Ok(())
}

/// Push to remote
pub fn push_branch(repo: &Repository, remote_name: &str, branch_name: &str) -> Result<()> {
    let mut remote = repo.find_remote(remote_name)?;
    let refspec = format!("refs/heads/{}:refs/heads/{}", branch_name, branch_name);

    // Create callbacks for authentication
    let mut callbacks = git2::RemoteCallbacks::new();
    callbacks.credentials(|_url, username_from_url, _allowed_types| {
        git2::Cred::ssh_key_from_agent(username_from_url.unwrap_or("git"))
    });

    let mut push_opts = git2::PushOptions::new();
    push_opts.remote_callbacks(callbacks);

    remote.push(&[&refspec], Some(&mut push_opts))?;
    Ok(())
}

/// Pull from remote
pub fn pull_branch(repo: &Repository, remote_name: &str, branch_name: &str) -> Result<()> {
    let mut remote = repo.find_remote(remote_name)?;

    // Create callbacks for authentication
    let mut callbacks = git2::RemoteCallbacks::new();
    callbacks.credentials(|_url, username_from_url, _allowed_types| {
        git2::Cred::ssh_key_from_agent(username_from_url.unwrap_or("git"))
    });

    let mut fetch_opts = git2::FetchOptions::new();
    fetch_opts.remote_callbacks(callbacks);

    remote.fetch(&[branch_name], Some(&mut fetch_opts), None)?;

    // Get the fetch head
    let fetch_head = repo.find_reference("FETCH_HEAD")?;
    let fetch_commit = repo.reference_to_annotated_commit(&fetch_head)?;

    // Perform merge
    let (analysis, _) = repo.merge_analysis(&[&fetch_commit])?;

    if analysis.is_fast_forward() {
        let refname = format!("refs/heads/{}", branch_name);
        let mut reference = repo.find_reference(&refname)?;
        reference.set_target(fetch_commit.id(), "Fast-forward")?;
        repo.checkout_head(Some(git2::build::CheckoutBuilder::default().force()))?;
    } else if analysis.is_normal() {
        return Err(Error::Custom(
            "Manual merge required - non-fast-forward".to_string(),
        ));
    }

    Ok(())
}
