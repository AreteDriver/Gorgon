#!/usr/bin/env bash
#
# Gorgon PostgreSQL Backup/Restore Script
#
# Usage:
#   ./backup.sh backup                     Create a new backup
#   ./backup.sh restore <backup_file>      Restore from a backup file
#   ./backup.sh list                       List available backups
#   ./backup.sh verify <backup_file>       Verify backup integrity
#
# Environment:
#   DATABASE_URL    PostgreSQL connection string (postgresql://user:pass@host:port/db)
#                   Falls back to .env file in project root
#   BACKUP_DIR      Directory to store backups (default: /var/backups/gorgon)
#   BACKUP_RETAIN   Number of backups to retain (default: 30)
#

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/gorgon}"
BACKUP_RETAIN="${BACKUP_RETAIN:-30}"
LOG_FILE="${BACKUP_DIR}/backup.log"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="gorgon_backup_${TIMESTAMP}.dump"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    local level="$1"; shift
    local msg
    msg="$(date '+%Y-%m-%d %H:%M:%S') [$level] $*"
    echo "$msg"
    if [[ -d "$BACKUP_DIR" ]]; then
        echo "$msg" >> "$LOG_FILE"
    fi
}

die() {
    log "ERROR" "$@"
    exit 1
}

load_database_url() {
    if [[ -n "${DATABASE_URL:-}" ]]; then
        return
    fi
    local env_file="$PROJECT_ROOT/.env"
    if [[ -f "$env_file" ]]; then
        DATABASE_URL="$(grep -E '^DATABASE_URL=' "$env_file" | head -1 | cut -d= -f2-)" || true
    fi
    if [[ -z "${DATABASE_URL:-}" ]]; then
        die "DATABASE_URL is not set and could not be found in $env_file"
    fi
}

ensure_backup_dir() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        mkdir -p "$BACKUP_DIR" || die "Cannot create backup directory: $BACKUP_DIR"
    fi
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
cmd_backup() {
    load_database_url
    ensure_backup_dir

    local dest="$BACKUP_DIR/$BACKUP_NAME"
    log "INFO" "Starting backup to $dest"

    if ! pg_dump -Fc -d "$DATABASE_URL" -f "$dest"; then
        rm -f "$dest"
        die "pg_dump failed"
    fi

    local size
    size="$(du -h "$dest" | cut -f1)"
    log "INFO" "Backup complete: $dest ($size)"

    # Retention: remove oldest backups beyond BACKUP_RETAIN
    local count
    count="$(find "$BACKUP_DIR" -maxdepth 1 -name 'gorgon_backup_*.dump' | wc -l)"
    if (( count > BACKUP_RETAIN )); then
        local to_remove=$(( count - BACKUP_RETAIN ))
        log "INFO" "Pruning $to_remove old backup(s) (retain=$BACKUP_RETAIN)"
        find "$BACKUP_DIR" -maxdepth 1 -name 'gorgon_backup_*.dump' -print0 \
            | sort -z \
            | head -z -n "$to_remove" \
            | xargs -0 rm -f --
    fi

    log "INFO" "Backup finished successfully"
}

cmd_restore() {
    local backup_file="${1:-}"
    local auto_yes="${2:-}"

    if [[ -z "$backup_file" ]]; then
        die "Usage: $0 restore <backup_file> [--yes]"
    fi

    # Resolve relative paths against BACKUP_DIR
    if [[ "$backup_file" != /* ]]; then
        if [[ -f "$BACKUP_DIR/$backup_file" ]]; then
            backup_file="$BACKUP_DIR/$backup_file"
        fi
    fi

    if [[ ! -f "$backup_file" ]]; then
        die "Backup file not found: $backup_file"
    fi

    load_database_url

    if [[ "$auto_yes" != "--yes" ]]; then
        echo "WARNING: This will overwrite the current database with:"
        echo "  $backup_file"
        echo ""
        read -rp "Continue? [y/N] " confirm
        if [[ "$confirm" != [yY] ]]; then
            echo "Aborted."
            exit 0
        fi
    fi

    log "INFO" "Restoring from $backup_file"

    if ! pg_restore --clean --if-exists -d "$DATABASE_URL" "$backup_file"; then
        die "pg_restore failed"
    fi

    log "INFO" "Restore complete"
}

cmd_list() {
    ensure_backup_dir

    local files
    files="$(find "$BACKUP_DIR" -maxdepth 1 -name 'gorgon_backup_*.dump' | sort)"

    if [[ -z "$files" ]]; then
        echo "No backups found in $BACKUP_DIR"
        return
    fi

    printf "%-45s %10s %s\n" "BACKUP FILE" "SIZE" "DATE"
    printf "%-45s %10s %s\n" "-------------------------------------------" "--------" "-------------------"

    while IFS= read -r f; do
        local name size mdate
        name="$(basename "$f")"
        size="$(du -h "$f" | cut -f1)"
        mdate="$(date -r "$f" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || stat -c '%y' "$f" 2>/dev/null | cut -d. -f1)"
        printf "%-45s %10s %s\n" "$name" "$size" "$mdate"
    done <<< "$files"

    echo ""
    echo "Total: $(echo "$files" | wc -l) backup(s) in $BACKUP_DIR"
}

cmd_verify() {
    local backup_file="${1:-}"

    if [[ -z "$backup_file" ]]; then
        die "Usage: $0 verify <backup_file>"
    fi

    if [[ "$backup_file" != /* ]]; then
        if [[ -f "$BACKUP_DIR/$backup_file" ]]; then
            backup_file="$BACKUP_DIR/$backup_file"
        fi
    fi

    if [[ ! -f "$backup_file" ]]; then
        die "Backup file not found: $backup_file"
    fi

    log "INFO" "Verifying $backup_file"

    if pg_restore --list "$backup_file" > /dev/null; then
        log "INFO" "Backup is valid: $backup_file"
        echo "Backup verified successfully."
    else
        die "Backup verification failed: $backup_file"
    fi
}

cmd_help() {
    cat <<'HELP'
Gorgon PostgreSQL Backup/Restore

Usage:
  backup.sh <command> [options]

Commands:
  backup                     Create a new database backup
  restore <file> [--yes]     Restore from a backup file (--yes skips confirmation)
  list                       List available backups with sizes and dates
  verify <file>              Verify backup file integrity
  help                       Show this help message

Environment Variables:
  DATABASE_URL               PostgreSQL connection string (required)
  BACKUP_DIR                 Backup storage directory (default: /var/backups/gorgon)
  BACKUP_RETAIN              Number of backups to keep (default: 30)

Examples:
  ./backup.sh backup
  ./backup.sh restore gorgon_backup_20260128_120000.dump
  ./backup.sh restore gorgon_backup_20260128_120000.dump --yes
  ./backup.sh list
  ./backup.sh verify gorgon_backup_20260128_120000.dump
HELP
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-help}" in
    backup)  cmd_backup ;;
    restore) cmd_restore "${2:-}" "${3:-}" ;;
    list)    cmd_list ;;
    verify)  cmd_verify "${2:-}" ;;
    help|-h|--help) cmd_help ;;
    *) die "Unknown command: $1. Run '$0 help' for usage." ;;
esac
