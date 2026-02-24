#!/usr/bin/env bash
# Complete knowledge pack workflow demonstration
#
# This script demonstrates all 8 pack management commands in a complete workflow:
# 1. create - Build a knowledge pack from topics
# 2. validate - Check pack structure
# 3. install - Install pack from archive
# 4. list - List all installed packs
# 5. info - Show detailed pack information
# 6. eval - Evaluate pack quality
# 7. update - Update to new version
# 8. remove - Uninstall pack

set -e  # Exit on error

echo "=== WikiGR Knowledge Pack Complete Workflow ==="
echo

# Setup
WORK_DIR=$(mktemp -d)
PACK_NAME="demo-pack"
OUTPUT_DIR="$WORK_DIR/output"
TOPICS_FILE="$WORK_DIR/topics.txt"
EVAL_QUESTIONS="$WORK_DIR/eval.jsonl"

echo "Working directory: $WORK_DIR"
echo

# Create topics file
cat > "$TOPICS_FILE" << EOF
Mathematics
Computer Science
EOF

# Create evaluation questions
cat > "$EVAL_QUESTIONS" << EOF
{"question": "What is calculus?", "ground_truth": "Branch of mathematics studying continuous change"}
{"question": "What is an algorithm?", "ground_truth": "Step-by-step procedure for solving problems"}
EOF

# Step 1: Create a knowledge pack
echo "Step 1: Creating knowledge pack..."
wikigr pack create \
  --name "$PACK_NAME" \
  --source wikipedia \
  --topics "$TOPICS_FILE" \
  --target 50 \
  --eval-questions "$EVAL_QUESTIONS" \
  --output "$OUTPUT_DIR"

PACK_DIR="$OUTPUT_DIR/$PACK_NAME"
echo "  Created pack at: $PACK_DIR"
echo

# Step 2: Validate pack structure
echo "Step 2: Validating pack structure..."
wikigr pack validate "$PACK_DIR"
echo "  Pack is valid!"
echo

# Package the pack
echo "Packaging pack for distribution..."
ARCHIVE_PATH="$WORK_DIR/${PACK_NAME}.tar.gz"
cd "$OUTPUT_DIR"
tar -czf "$ARCHIVE_PATH" "$PACK_NAME"
echo "  Created archive: $ARCHIVE_PATH"
echo

# Step 3: Install pack
echo "Step 3: Installing pack..."
wikigr pack install "$ARCHIVE_PATH"
echo "  Pack installed!"
echo

# Step 4: List installed packs
echo "Step 4: Listing all installed packs..."
wikigr pack list
echo

# List in JSON format
echo "Listing in JSON format..."
wikigr pack list --format json
echo

# Step 5: Show pack information
echo "Step 5: Showing detailed pack information..."
wikigr pack info "$PACK_NAME"
echo

# Step 6: Evaluate pack quality (requires ANTHROPIC_API_KEY)
if [ -n "$ANTHROPIC_API_KEY" ]; then
  echo "Step 6: Evaluating pack quality..."
  wikigr pack eval "$PACK_NAME" --save-results
  echo

  # Show eval scores
  echo "Showing evaluation scores..."
  wikigr pack info "$PACK_NAME" --show-eval-scores
  echo
else
  echo "Step 6: Skipping evaluation (ANTHROPIC_API_KEY not set)"
  echo
fi

# Step 7: Create and install updated version
echo "Step 7: Creating and installing pack update..."
# Modify the pack (e.g., update version)
MANIFEST_PATH="$PACK_DIR/manifest.json"
if [ -f "$MANIFEST_PATH" ]; then
  # Update version to 1.1.0
  python3 << EOF
import json
with open("$MANIFEST_PATH") as f:
    manifest = json.load(f)
manifest["version"] = "1.1.0"
with open("$MANIFEST_PATH", "w") as f:
    json.dump(manifest, f, indent=2)
EOF

  # Repackage
  ARCHIVE_V2="$WORK_DIR/${PACK_NAME}-v1.1.0.tar.gz"
  cd "$OUTPUT_DIR"
  tar -czf "$ARCHIVE_V2" "$PACK_NAME"

  # Update installed pack
  wikigr pack update "$PACK_NAME" --from "$ARCHIVE_V2"
  echo "  Pack updated to v1.1.0!"
  echo
fi

# Step 8: Remove pack
echo "Step 8: Removing pack..."
wikigr pack remove "$PACK_NAME" --force
echo "  Pack removed!"
echo

# Verify removal
echo "Verifying pack was removed..."
if wikigr pack list | grep -q "$PACK_NAME"; then
  echo "  ERROR: Pack still listed after removal"
  exit 1
else
  echo "  Pack successfully removed (not in list)"
fi
echo

# Cleanup
echo "Cleaning up working directory..."
rm -rf "$WORK_DIR"

echo
echo "=== Workflow Complete ==="
echo
echo "All 8 pack management commands demonstrated successfully:"
echo "  1. pack create   - Build knowledge pack from topics"
echo "  2. pack validate - Check pack structure"
echo "  3. pack install  - Install from archive"
echo "  4. pack list     - List installed packs"
echo "  5. pack info     - Show pack details"
echo "  6. pack eval     - Evaluate pack quality"
echo "  7. pack update   - Update to new version"
echo "  8. pack remove   - Uninstall pack"
