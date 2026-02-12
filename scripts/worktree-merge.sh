#!/bin/bash
# Usage: ./scripts/worktree-merge.sh <feature-name>
#
# Merges a feature branch, runs tests, cleans up worktree.

FEATURE=$1
REPO_ROOT=~/projects/Gorgon
TREE_DIR=~/projects/.trees/gorgon-$FEATURE

if [ -z "$FEATURE" ]; then
  echo "Usage: ./scripts/worktree-merge.sh <feature-name>"
  exit 1
fi

cd "$REPO_ROOT" || exit 1

echo "=== Merging feature/$FEATURE into main ==="

# Check for dependency requirements first
DEPS_FILE="$TREE_DIR/DEPS_NEEDED.md"
if [ -f "$DEPS_FILE" ]; then
  DEPS_COUNT=$(grep -c "^- " "$DEPS_FILE" 2>/dev/null || echo "0")
  if [ "$DEPS_COUNT" -gt 0 ]; then
    echo ""
    echo "This feature requires new dependencies:"
    grep "^- " "$DEPS_FILE"
    echo ""
    read -p "Have you added these to pyproject.toml on main? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Add dependencies to pyproject.toml first, then re-run merge."
      exit 1
    fi
  fi
fi

# Ensure main is up to date
git checkout main
git pull origin main

# Merge
git merge "feature/$FEATURE" --no-ff -m "Merge feature/$FEATURE: completed"

# Run tests
echo ""
echo "Running tests..."
pytest tests/ -v
TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
  echo ""
  echo "Tests failed! Aborting merge."
  git merge --abort
  exit 1
fi

echo ""
echo "Tests passed. Pushing..."
git push origin main

# Clean up
echo "Cleaning up worktree and branch..."
git worktree remove "$TREE_DIR"
git branch -d "feature/$FEATURE"

echo ""
echo "feature/$FEATURE merged and cleaned up."
