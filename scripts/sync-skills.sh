#!/bin/bash
# Syncs ai-skills/gorgon-skills repos to ~/.gorgon/skills/ at a pinned version tag.
# Prevents breaking changes from landing in a running Gorgon instance.

SKILLS_REPO=~/projects/gorgon-skills
GORGON_SKILLS=~/.gorgon/skills
GORGON_PROMPTS=~/.gorgon/prompts
PROMPTS_REPO=~/projects/prompt-library

# Read pinned version from pyproject.toml (or default to latest tag)
PINNED_VERSION=$(grep 'skills_version' ~/projects/Gorgon/pyproject.toml \
  | head -1 | sed 's/.*= *"\(.*\)"/\1/' 2>/dev/null)

echo "=== Syncing skills to Gorgon ==="

if [ -d "$SKILLS_REPO" ]; then
  cd "$SKILLS_REPO" || exit 1
  git fetch --tags origin 2>/dev/null

  if [ -n "$PINNED_VERSION" ]; then
    echo "Pinned version: $PINNED_VERSION"
    git checkout "$PINNED_VERSION" 2>/dev/null
    if [ $? -ne 0 ]; then
      echo "Tag $PINNED_VERSION not found. Available tags:"
      git tag -l | tail -5
      echo "Falling back to main"
      git checkout main
      git pull origin main
    fi
  else
    echo "No pinned version found, using main"
    git checkout main
    git pull origin main
  fi

  # Sync skills
  mkdir -p "$GORGON_SKILLS"
  rsync -av --delete "$SKILLS_REPO/browser/" "$GORGON_SKILLS/browser/" 2>/dev/null
  rsync -av --delete "$SKILLS_REPO/email/" "$GORGON_SKILLS/email/" 2>/dev/null
  rsync -av --delete "$SKILLS_REPO/integrations/" "$GORGON_SKILLS/integrations/" 2>/dev/null
  rsync -av --delete "$SKILLS_REPO/system/" "$GORGON_SKILLS/system/" 2>/dev/null
  [ -f "$SKILLS_REPO/registry.yaml" ] && cp "$SKILLS_REPO/registry.yaml" "$GORGON_SKILLS/"

  echo "Skills synced to $GORGON_SKILLS"
  echo ""
else
  echo "Skills repo not found at $SKILLS_REPO — skipping"
fi

# Sync prompt-library
if [ -d "$PROMPTS_REPO" ]; then
  echo "=== Syncing prompt-library ==="
  cd "$PROMPTS_REPO" || exit 1
  git pull origin main 2>/dev/null
  mkdir -p "$GORGON_PROMPTS"
  rsync -av --delete "$PROMPTS_REPO/patterns/" "$GORGON_PROMPTS/patterns/" 2>/dev/null
  rsync -av --delete "$PROMPTS_REPO/templates/" "$GORGON_PROMPTS/templates/" 2>/dev/null
  echo "Prompts synced to $GORGON_PROMPTS"
fi

echo ""

# Validate if Gorgon CLI is available
if command -v gorgon &> /dev/null; then
  echo "Running skill validation..."
  gorgon skills validate
else
  echo "Gorgon CLI not installed — skipping validation"
fi
