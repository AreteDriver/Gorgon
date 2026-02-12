#!/bin/bash
# Upgrades the pinned skills version to the latest tag.

SKILLS_REPO=~/projects/gorgon-skills

if [ ! -d "$SKILLS_REPO" ]; then
  echo "Skills repo not found at $SKILLS_REPO"
  exit 1
fi

cd "$SKILLS_REPO" || exit 1
git fetch --tags origin
LATEST=$(git tag -l 'v*' --sort=-v:refname | head -1)

if [ -z "$LATEST" ]; then
  echo "No version tags found in skills repo"
  exit 1
fi

echo "Latest skills tag: $LATEST"
echo ""

# Show what changed since current pin
CURRENT=$(grep 'skills_version' ~/projects/Gorgon/pyproject.toml \
  | head -1 | sed 's/.*= *"\(.*\)"/\1/' 2>/dev/null)

if [ -n "$CURRENT" ]; then
  echo "Current pin: $CURRENT"
  echo "Changes since $CURRENT:"
  git log "$CURRENT..$LATEST" --oneline
  echo ""
fi

read -p "Upgrade to $LATEST? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
  sed -i "s/skills_version = \".*\"/skills_version = \"$LATEST\"/" \
    ~/projects/Gorgon/pyproject.toml
  echo "Updated pyproject.toml to $LATEST"
  echo "Run ./scripts/sync-skills.sh to apply"
fi
