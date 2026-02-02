/**
 * Tauri IPC wrapper for desktop functionality
 *
 * Provides file system, git, and notification capabilities
 * when running in the Tauri desktop environment.
 */

// Types for Tauri commands
type InvokeFunction = <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;

// Dynamic import of Tauri API - only available when running in Tauri
let invokeInternal: InvokeFunction | null = null;

// Try to load Tauri API if available
async function loadTauriApi() {
  try {
    // @ts-expect-error - Tauri API may not be available
    const { invoke } = await import('@tauri-apps/api/core');
    invokeInternal = invoke as InvokeFunction;
  } catch {
    // Not running in Tauri environment
    invokeInternal = null;
  }
}

// Initialize on module load
loadTauriApi();

// Helper to invoke Tauri commands
async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!invokeInternal) {
    throw new Error('Tauri API not available - not running in desktop environment');
  }
  return invokeInternal<T>(cmd, args);
}

// ============================================================================
// Types
// ============================================================================

export interface DirectoryEntry {
  name: string;
  path: string;
  is_directory: boolean;
  size: number;
}

export interface GitStatusEntry {
  path: string;
  status: 'new' | 'modified' | 'deleted' | 'renamed' | 'untracked' | 'conflicted' | 'unknown';
  staged: boolean;
}

export interface GitLogEntry {
  id: string;
  message: string;
  author: string;
  time: number;
}

export interface GitBranchInfo {
  name: string;
  is_current: boolean;
  is_remote: boolean;
}

export interface AppInfo {
  name: string;
  version: string;
  tauri_version: string;
}

// ============================================================================
// Environment Detection
// ============================================================================

/**
 * Check if running in Tauri desktop environment
 */
export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

// ============================================================================
// File Operations
// ============================================================================

/**
 * Read a file's contents
 */
export async function readFile(path: string): Promise<string> {
  return invoke<string>('read_file', { path });
}

/**
 * Write content to a file
 */
export async function writeFile(path: string, content: string): Promise<void> {
  return invoke('write_file', { path, content });
}

/**
 * List directory contents
 */
export async function listDirectory(path: string): Promise<DirectoryEntry[]> {
  return invoke<DirectoryEntry[]>('list_directory', { path });
}

/**
 * Check if a file exists
 */
export async function fileExists(path: string): Promise<boolean> {
  return invoke<boolean>('file_exists', { path });
}

/**
 * Create a directory
 */
export async function createDirectory(path: string): Promise<void> {
  return invoke('create_directory', { path });
}

/**
 * Delete a file or directory
 */
export async function deleteFile(path: string): Promise<void> {
  return invoke('delete_file', { path });
}

// ============================================================================
// Git Operations
// ============================================================================

/**
 * Get git repository status
 */
export async function gitStatus(repoPath: string): Promise<GitStatusEntry[]> {
  return invoke<GitStatusEntry[]>('git_status', { repoPath });
}

/**
 * Get git diff
 */
export async function gitDiff(repoPath: string, staged = false): Promise<string> {
  return invoke<string>('git_diff', { repoPath, staged });
}

/**
 * Create a git commit
 */
export async function gitCommit(repoPath: string, message: string): Promise<string> {
  return invoke<string>('git_commit', { repoPath, message });
}

/**
 * List git branches
 */
export async function gitBranch(repoPath: string): Promise<GitBranchInfo[]> {
  return invoke<GitBranchInfo[]>('git_branch', { repoPath });
}

/**
 * Checkout a branch
 */
export async function gitCheckout(repoPath: string, branchName: string): Promise<void> {
  return invoke('git_checkout', { repoPath, branchName });
}

/**
 * Push to remote
 */
export async function gitPush(
  repoPath: string,
  remote?: string,
  branch?: string
): Promise<void> {
  return invoke('git_push', { repoPath, remote, branch });
}

/**
 * Pull from remote
 */
export async function gitPull(
  repoPath: string,
  remote?: string,
  branch?: string
): Promise<void> {
  return invoke('git_pull', { repoPath, remote, branch });
}

/**
 * Get git log
 */
export async function gitLog(repoPath: string, count?: number): Promise<GitLogEntry[]> {
  return invoke<GitLogEntry[]>('git_log', { repoPath, count });
}

/**
 * Create a new branch
 */
export async function gitCreateBranch(repoPath: string, branchName: string): Promise<void> {
  return invoke('git_create_branch', { repoPath, branchName });
}

// ============================================================================
// Notifications
// ============================================================================

/**
 * Send a native notification
 */
export async function sendNotification(title: string, body: string): Promise<void> {
  return invoke('send_notification', { title, body });
}

// ============================================================================
// System Info
// ============================================================================

/**
 * Get application info
 */
export async function getAppInfo(): Promise<AppInfo> {
  return invoke<AppInfo>('get_app_info');
}

// ============================================================================
// Convenience Exports
// ============================================================================

export const tauri = {
  isTauri,
  // File operations
  readFile,
  writeFile,
  listDirectory,
  fileExists,
  createDirectory,
  deleteFile,
  // Git operations
  gitStatus,
  gitDiff,
  gitCommit,
  gitBranch,
  gitCheckout,
  gitPush,
  gitPull,
  gitLog,
  gitCreateBranch,
  // Notifications
  sendNotification,
  // System info
  getAppInfo,
};

export default tauri;
