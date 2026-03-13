#!/usr/bin/env bash
# Claude Code lab capture script (LAB-RUN-001 / LAB-RUN-002).
# Usage: ./claude-code-capture.sh <baseline|phase1|phase2|phase4> [--with-monitors for phase2]
# Phase 3 (agentic session) is manual; see LAB-RUN-001 protocol.
# Install (npm install -g @anthropic-ai/claude-code) and launch+script are operator-driven.
# Supports macOS and Linux; tcpdump/strace require sudo and are not run by this script.
set -e

LAB_DIR="${LAB_DIR:-$HOME/claude-lab/LAB-RUN-001}"

phase="${1:-}"
WITH_MONITORS=""

for arg in "$@"; do
  [ "$arg" = "--with-monitors" ] && WITH_MONITORS=1
done

mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-launch,phase3-agentic,phase4-teardown}
mkdir -p ~/claude-lab-workspace 2>/dev/null || true

# Portable: use lsof for network (macOS and Linux); pstree if available else ps auxf
listening_ports() {
  if command -v ss >/dev/null 2>&1; then
    ss -tlnp > "$1" 2>/dev/null || true
  else
    lsof -i -nP 2>/dev/null | grep LISTEN > "$1" || true
  fi
}

active_connections() {
  if command -v ss >/dev/null 2>&1; then
    ss -tnp > "$1" 2>/dev/null || true
  else
    lsof -i -nP > "$1" 2>/dev/null || true
  fi
}

pstree_cmd() {
  if command -v pstree >/dev/null 2>&1; then
    pstree -p 2>/dev/null || ps auxf
  else
    ps auxf
  fi
}

run_baseline() {
  echo "Running baseline capture..."
  find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' 2>/dev/null > "$LAB_DIR/baseline/home-tree.txt" || true
  ls -la ~/.claude 2>&1 > "$LAB_DIR/baseline/claude-dir-check.txt" || true
  find ~ -name '*.claude*' -o -name '*anthropic*' 2>/dev/null > "$LAB_DIR/baseline/claude-artifact-scan.txt" || true
  ls -la /tmp/ > "$LAB_DIR/baseline/tmp-listing.txt" 2>/dev/null || true
  for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
    [ -f "$f" ] && cp "$f" "$LAB_DIR/baseline/$(basename "$f").bak" || true
  done
  ps auxww > "$LAB_DIR/baseline/ps-full.txt" 2>/dev/null || true
  pstree_cmd > "$LAB_DIR/baseline/pstree.txt" 2>/dev/null || true
  listening_ports "$LAB_DIR/baseline/listening-ports.txt" || true
  active_connections "$LAB_DIR/baseline/active-connections.txt" || true
  env | sort > "$LAB_DIR/baseline/env-vars.txt"
  env | grep -i anthropic > "$LAB_DIR/baseline/anthropic-env.txt" 2>/dev/null || true
  echo "Exit code: $?" >> "$LAB_DIR/baseline/anthropic-env.txt"
  npm list -g --depth=0 > "$LAB_DIR/baseline/npm-globals.txt" 2>&1 || true
  which claude > "$LAB_DIR/baseline/which-claude.txt" 2>&1 || true
  which claude-code >> "$LAB_DIR/baseline/which-claude.txt" 2>&1 || true
  echo "Exit code: $?" >> "$LAB_DIR/baseline/which-claude.txt"
  systemctl --user list-units --type=service > "$LAB_DIR/baseline/user-services.txt" 2>/dev/null || true
  crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1 || true
  ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null || true
  touch "$LAB_DIR/baseline/TIMESTAMP_MARKER"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/baseline/start-time.txt"
  shasum -a 256 "$LAB_DIR/baseline/"* 2>/dev/null > "$LAB_DIR/baseline/EVIDENCE-HASHES.txt" || true
  echo "Baseline complete."
}

run_phase1() {
  echo "Running Phase 1 (post-install capture). Run 'npm install -g @anthropic-ai/claude-code' and monitors per protocol first."
  npm list -g --depth=0 > "$LAB_DIR/phase1-install/npm-globals-post.txt" 2>&1 || true
  [ -f "$LAB_DIR/baseline/npm-globals.txt" ] && diff "$LAB_DIR/baseline/npm-globals.txt" "$LAB_DIR/phase1-install/npm-globals-post.txt" > "$LAB_DIR/phase1-install/npm-globals-diff.txt" 2>&1 || true
  which claude > "$LAB_DIR/phase1-install/which-claude.txt" 2>&1 || true
  which claude-code >> "$LAB_DIR/phase1-install/which-claude.txt" 2>&1 || true
  npm list -g @anthropic-ai/claude-code --json > "$LAB_DIR/phase1-install/claude-version.json" 2>&1 || true
  CLAUDE_BIN=$(which claude 2>/dev/null || which claude-code 2>/dev/null)
  if [ -n "$CLAUDE_BIN" ]; then
    ls -la "$CLAUDE_BIN" > "$LAB_DIR/phase1-install/binary-metadata.txt"
    file "$CLAUDE_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
    (readlink -f "$CLAUDE_BIN" 2>/dev/null || realpath "$CLAUDE_BIN" 2>/dev/null || echo "$CLAUDE_BIN") >> "$LAB_DIR/phase1-install/binary-metadata.txt"
    shasum -a 256 "$CLAUDE_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt" 2>/dev/null || true
  fi
  [ -f "$LAB_DIR/baseline/TIMESTAMP_MARKER" ] && find ~ -newer "$LAB_DIR/baseline/TIMESTAMP_MARKER" -not -path '*/claude-lab/*' -not -path '*/.cache/*' -not -path '*/node_modules/*' 2>/dev/null > "$LAB_DIR/phase1-install/new-files.txt" || true
  ls -laR ~/.claude 2>&1 > "$LAB_DIR/phase1-install/claude-dir-post.txt" || true
  for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
    base=$(basename "$f")
    if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
      diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase1-install/shellprofile-diff-$base.txt" 2>&1 || true
    fi
  done
  crontab -l > "$LAB_DIR/phase1-install/crontab-post.txt" 2>&1 || true
  [ -f "$LAB_DIR/baseline/crontab.txt" ] && diff "$LAB_DIR/baseline/crontab.txt" "$LAB_DIR/phase1-install/crontab-post.txt" > "$LAB_DIR/phase1-install/crontab-diff.txt" 2>&1 || true
  touch "$LAB_DIR/phase1-install/TIMESTAMP_MARKER"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase1-install/phase1-end-time.txt"
  shasum -a 256 "$LAB_DIR/phase1-install/"* 2>/dev/null > "$LAB_DIR/phase1-install/EVIDENCE-HASHES.txt" || true
  echo "Phase 1 complete."
}

run_phase2() {
  echo "Running Phase 2 (post-launch capture). Start 'script' and launch 'claude', complete auth, then run this."
  CLAUDE_PID=$(pgrep -f claude 2>/dev/null | head -1)
  if [ -n "$CLAUDE_PID" ]; then
    pstree_cmd > "$LAB_DIR/phase2-launch/claude-process-tree.txt" 2>/dev/null || true
    pstree -p "$CLAUDE_PID" 2>/dev/null > "$LAB_DIR/phase2-launch/claude-tree-idle.txt" || pstree_cmd > "$LAB_DIR/phase2-launch/claude-tree-idle.txt" 2>/dev/null || true
  fi
  ps auxww | grep -E 'claude|anthropic|open |xdg-open' 2>/dev/null | grep -v grep > "$LAB_DIR/phase2-launch/auth-processes.txt" || true
  listening_ports "$LAB_DIR/phase2-launch/listening-ports-during-auth.txt"
  active_connections "$LAB_DIR/phase2-launch/outbound-at-launch.txt"
  [ -f "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" ] && find ~ -newer "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" -not -path '*/claude-lab/*' 2>/dev/null > "$LAB_DIR/phase2-launch/new-files-at-launch.txt" || true
  ls -laR ~/.claude > "$LAB_DIR/phase2-launch/claude-dir-at-launch.txt" 2>&1 || true
  find ~/.claude -type f 2>/dev/null | while read -r f; do
    echo "=== $f ===" >> "$LAB_DIR/phase2-launch/claude-config-contents.txt"
    cat "$f" >> "$LAB_DIR/phase2-launch/claude-config-contents.txt" 2>/dev/null || true
    echo "" >> "$LAB_DIR/phase2-launch/claude-config-contents.txt"
  done
  touch "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase2-launch/phase2-end-time.txt"
  if [ -n "$WITH_MONITORS" ]; then
    while true; do
      echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/connections-stream.txt"
      if command -v ss >/dev/null 2>&1; then ss -tnp >> "$LAB_DIR/phase2-launch/connections-stream.txt" 2>/dev/null; else lsof -i -nP >> "$LAB_DIR/phase2-launch/connections-stream.txt" 2>/dev/null; fi
      sleep 2
    done &
    CONN_PID=$!
    while true; do
      echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/pstree-stream.txt"
      pstree_cmd >> "$LAB_DIR/phase2-launch/pstree-stream.txt" 2>/dev/null || true
      sleep 2
    done &
    PS_PID=$!
    echo "CONN_PID=$CONN_PID" > "$LAB_DIR/phase2-launch/monitor-pids.txt"
    echo "PS_PID=$PS_PID" >> "$LAB_DIR/phase2-launch/monitor-pids.txt"
    echo "Monitors started (PIDs $CONN_PID, $PS_PID). Run: $0 phase4 to stop them."
    return 0
  fi
  shasum -a 256 "$LAB_DIR/phase2-launch/"* 2>/dev/null > "$LAB_DIR/phase2-launch/EVIDENCE-HASHES.txt" || true
  echo "Phase 2 complete."
}

run_phase4() {
  echo "Running Phase 4 (teardown capture). Exit claude and script first, wait ~10s."
  if [ -f "$LAB_DIR/phase2-launch/monitor-pids.txt" ]; then
    # shellcheck source=/dev/null
    . "$LAB_DIR/phase2-launch/monitor-pids.txt"
    [ -n "$CONN_PID" ] && [ "$CONN_PID" -eq "$CONN_PID" ] 2>/dev/null && kill $CONN_PID 2>/dev/null || true
    [ -n "$PS_PID" ] && [ "$PS_PID" -eq "$PS_PID" ] 2>/dev/null && kill $PS_PID 2>/dev/null || true
    shasum -a 256 "$LAB_DIR/phase2-launch/"* 2>/dev/null > "$LAB_DIR/phase2-launch/EVIDENCE-HASHES.txt" || true
  fi
  ps auxww | grep -E 'claude|anthropic' | grep -v grep > "$LAB_DIR/phase4-teardown/remaining-processes.txt" 2>/dev/null || true
  echo "Matching processes: $(wc -l < "$LAB_DIR/phase4-teardown/remaining-processes.txt" 2>/dev/null)" >> "$LAB_DIR/phase4-teardown/remaining-processes.txt"
  pstree_cmd > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt" 2>/dev/null || true
  active_connections "$LAB_DIR/phase4-teardown/connections-post-exit.txt"
  [ -f "$LAB_DIR/baseline/active-connections.txt" ] && diff "$LAB_DIR/baseline/active-connections.txt" "$LAB_DIR/phase4-teardown/connections-post-exit.txt" > "$LAB_DIR/phase4-teardown/connections-diff.txt" 2>&1 || true
  listening_ports "$LAB_DIR/phase4-teardown/listening-ports-post.txt"
  ls -laR ~/.claude > "$LAB_DIR/phase4-teardown/claude-dir-final.txt" 2>&1 || true
  find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' 2>/dev/null > "$LAB_DIR/phase4-teardown/home-tree-final.txt"
  [ -f "$LAB_DIR/baseline/home-tree.txt" ] && diff "$LAB_DIR/baseline/home-tree.txt" "$LAB_DIR/phase4-teardown/home-tree-final.txt" > "$LAB_DIR/phase4-teardown/home-tree-diff.txt" 2>&1 || true
  find ~/.claude -type f -exec ls -la {} \; 2>/dev/null > "$LAB_DIR/phase4-teardown/claude-artifacts-detail.txt"
  find ~/.claude -type f -exec file {} \; 2>/dev/null >> "$LAB_DIR/phase4-teardown/claude-artifacts-detail.txt"
  for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
    base=$(basename "$f")
    if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
      diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase4-teardown/shellprofile-diff-$base.txt" 2>&1 || true
    fi
  done
  crontab -l > "$LAB_DIR/phase4-teardown/crontab-final.txt" 2>&1 || true
  [ -f "$LAB_DIR/baseline/crontab.txt" ] && diff "$LAB_DIR/baseline/crontab.txt" "$LAB_DIR/phase4-teardown/crontab-final.txt" > "$LAB_DIR/phase4-teardown/crontab-diff.txt" 2>&1 || true
  systemctl --user list-units --type=service > "$LAB_DIR/phase4-teardown/user-services-final.txt" 2>/dev/null || true
  [ -f "$LAB_DIR/baseline/user-services.txt" ] && diff "$LAB_DIR/baseline/user-services.txt" "$LAB_DIR/phase4-teardown/user-services-final.txt" > "$LAB_DIR/phase4-teardown/services-diff.txt" 2>&1 || true
  ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/phase4-teardown/launch-agents-final.txt" 2>/dev/null || true
  [ -f "$LAB_DIR/baseline/launch-agents.txt" ] && diff "$LAB_DIR/baseline/launch-agents.txt" "$LAB_DIR/phase4-teardown/launch-agents-final.txt" > "$LAB_DIR/phase4-teardown/launch-agents-diff.txt" 2>&1 || true
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase4-teardown/phase4-end-time.txt"
  shasum -a 256 "$LAB_DIR/phase4-teardown/"* 2>/dev/null > "$LAB_DIR/phase4-teardown/EVIDENCE-HASHES.txt" || true
  find "$LAB_DIR" -name 'EVIDENCE-HASHES.txt' -exec cat {} \; > "$LAB_DIR/MASTER-HASHES.txt"
  shasum -a 256 "$LAB_DIR/MASTER-HASHES.txt" >> "$LAB_DIR/MASTER-HASHES.txt"
  echo "Phase 4 complete. MASTER-HASHES.txt updated."
}

case "$phase" in
  baseline) run_baseline ;;
  phase1)  run_phase1 ;;
  phase2)  run_phase2 ;;
  phase4)  run_phase4 ;;
  *)
    echo "Usage: $0 <baseline|phase1|phase2|phase4> [--with-monitors]" >&2
    echo "  LAB_DIR defaults to $LAB_DIR" >&2
    echo "  Phase 3 (agentic session) is manual; see LAB-RUN-001 protocol." >&2
    echo "  For phase2 with connection/pstree stream monitors: $0 phase2 --with-monitors" >&2
    exit 1
    ;;
esac
