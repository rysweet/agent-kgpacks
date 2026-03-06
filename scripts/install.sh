#!/bin/bash
# Install /kg-pack skill in the current Claude Code project.
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/rysweet/agent-kgpacks/main/scripts/install.sh | bash
#
# What this does:
#   1. Creates .claude/skills/kg-pack/SKILL.md in your project
#   2. The /kg-pack command becomes available in your next Claude Code session
#   3. Use it to list, install, build, and query knowledge packs
#
set -e

SKILL_DIR=".claude/skills/kg-pack"
SKILL_URL="https://raw.githubusercontent.com/rysweet/agent-kgpacks/main/skills/kg-pack/SKILL.md"

echo "Installing /kg-pack skill for Claude Code..."
mkdir -p "$SKILL_DIR"

if command -v curl &> /dev/null; then
    curl -sL "$SKILL_URL" > "$SKILL_DIR/SKILL.md"
elif command -v wget &> /dev/null; then
    wget -qO "$SKILL_DIR/SKILL.md" "$SKILL_URL"
else
    echo "ERROR: curl or wget required" >&2
    exit 1
fi

if [ -s "$SKILL_DIR/SKILL.md" ]; then
    echo "Installed to $SKILL_DIR/SKILL.md"
    echo ""
    echo "Start a new Claude Code session, then:"
    echo "  /kg-pack list                        — 49 packs available"
    echo "  /kg-pack install rust-expert          — add Rust expertise"
    echo "  /kg-pack build \"my topic\"             — build a custom pack"
    echo "  /kg-pack query rust-expert \"question\" — query directly"
else
    echo "ERROR: Failed to download SKILL.md" >&2
    exit 1
fi
