#!/bin/bash
# LAB-RUN-001 Cleanup Script
# Reverses all changes from the Claude Code lab run
# Run with: bash lab-cleanup.sh

set -e

echo "=== LAB-RUN-001 Cleanup ==="
echo "This will remove Claude Code and all lab artifacts."
echo ""
read -p "Press Enter to continue (Ctrl+C to abort)..."

echo ""
echo "[1/6] Uninstalling Claude Code..."
npm uninstall -g @anthropic-ai/claude-code 2>/dev/null && echo "  ✓ Removed npm package" || echo "  - Already removed"

echo ""
echo "[2/6] Removing ~/.claude/ directory..."
if [ -d ~/.claude ]; then
  rm -rf ~/.claude
  echo "  ✓ Removed ~/.claude/"
else
  echo "  - Already removed"
fi

echo ""
echo "[3/6] Removing hello_world test project..."
if [ -d ~/hello_world ]; then
  rm -rf ~/hello_world
  echo "  ✓ Removed ~/hello_world/"
else
  echo "  - Already removed"
fi

echo ""
echo "[4/6] Cleaning npm cache for anthropic packages..."
npm cache clean --force 2>/dev/null && echo "  ✓ npm cache cleared" || echo "  - Cache clean skipped"

echo ""
echo "[5/6] Verifying removal..."
echo "  claude binary: $(which claude 2>&1)"
echo "  ~/.claude dir: $(ls -d ~/.claude 2>&1)"
echo "  npm globals:"
npm list -g --depth=0 2>&1 | grep -i claude || echo "    (no claude packages)"

echo ""
echo "[6/6] Lab evidence directory..."
if [ -d ~/claude-lab ]; then
  echo "  ~/claude-lab/ still exists ($(du -sh ~/claude-lab 2>/dev/null | cut -f1))"
  read -p "  Delete lab evidence too? (y/N): " DELETE_LAB
  if [ "$DELETE_LAB" = "y" ] || [ "$DELETE_LAB" = "Y" ]; then
    rm -rf ~/claude-lab
    echo "  ✓ Removed ~/claude-lab/"
  else
    echo "  - Kept ~/claude-lab/ for reference"
  fi
else
  echo "  - Already removed"
fi

echo ""
echo "=== Cleanup complete ==="
echo "Remaining: lab protocol + results docs in ~/Documents/Cursor/"
