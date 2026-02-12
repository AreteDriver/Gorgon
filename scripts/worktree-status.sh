#!/bin/bash
# Show status of all active worktrees for Gorgon

REPO_ROOT=~/projects/Gorgon

echo "=== Active Gorgon Worktrees ==="
echo ""

cd "$REPO_ROOT" || exit 1
git worktree list --porcelain | while IFS= read -r line; do
  case "$line" in
    worktree\ *)
      path="${line#worktree }"
      echo "  $path"
      ;;
    branch\ *)
      branch="${line#branch refs/heads/}"
      echo "   Branch: $branch"
      # Show uncommitted changes count
      changes=$(cd "$path" 2>/dev/null && git status --porcelain | wc -l)
      if [ "$changes" -gt 0 ]; then
        echo "   Uncommitted changes: $changes files"
      else
        echo "   Clean"
      fi
      # Show commit count ahead of main
      ahead=$(cd "$path" 2>/dev/null && git rev-list main.."$branch" --count 2>/dev/null || echo "0")
      echo "   Commits ahead of main: $ahead"
      echo ""
      ;;
  esac
done
