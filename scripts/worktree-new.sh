#!/bin/bash
# Usage: ./scripts/worktree-new.sh <feature-name> <scope-description>
#
# Creates a worktree, branch, and .claude/rules.md in one command.
# Example: ./scripts/worktree-new.sh skills 'src/test_ai/skills/ and tests/test_skills/'

FEATURE=$1
SCOPE=$2
REPO_ROOT=~/projects/Gorgon
TREE_DIR=~/projects/.trees/gorgon-$FEATURE

if [ -z "$FEATURE" ] || [ -z "$SCOPE" ]; then
  echo "Usage: ./scripts/worktree-new.sh <feature-name> <scope-description>"
  echo "Example: ./scripts/worktree-new.sh skills 'src/test_ai/skills/ and tests/test_skills/'"
  exit 1
fi

cd "$REPO_ROOT" || exit 1

# Create worktree directory parent if needed
mkdir -p ~/projects/.trees

# Create worktree + branch
git worktree add -b "feature/$FEATURE" "$TREE_DIR"
echo "Created worktree: $TREE_DIR on branch feature/$FEATURE"

# Create scope rules for Claude Code
mkdir -p "$TREE_DIR/.claude"
cat > "$TREE_DIR/.claude/rules.md" << EOF
# Scope: $FEATURE
- Read CLAUDE.md in the repo root for full project context
- Work ONLY on files in: $SCOPE
- Branch: feature/$FEATURE
- Safe to commit and push to origin/feature/$FEATURE
- Run tests before committing: pytest tests/ -v
- Do not modify files outside your scope
- Do NOT modify pyproject.toml or requirements.txt
- Document any new dependencies in DEPS_NEEDED.md at worktree root
  Format: - package_name >= version  # reason
EOF

# Create DEPS_NEEDED.md for dependency tracking
cat > "$TREE_DIR/DEPS_NEEDED.md" << EOF
# Dependencies Needed for feature/$FEATURE
# Agent: add entries here. Human merges to pyproject.toml on main.
# Format: - package_name >= version  # reason
EOF

echo "Agent rules written to $TREE_DIR/.claude/rules.md"
echo ""
echo "To start an agent:"
echo "  cd $TREE_DIR && claude"
