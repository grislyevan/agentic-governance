#!/usr/bin/env bash
# Claude Cowork lab capture script (LAB-RUN-014).
# Usage: ./cowork-capture.sh <baseline|phase1|phase2|phase4> [--with-monitors for phase2]
# Phase 3 (session analysis) is manual; see protocol.
set -e

LAB_DIR="${LAB_DIR:-$HOME/cowork-lab/LAB-RUN-014}"
CLAUDE_SUPPORT="$HOME/Library/Application Support/Claude"

phase="${1:-}"
WITH_MONITORS=""

for arg in "$@"; do
  [ "$arg" = "--with-monitors" ] && WITH_MONITORS=1
done

mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-onboard,phase3a-basic,phase3b-agentic,phase3c-selfmod,phase4-teardown}
mkdir -p "$HOME/cowork-lab-workspace"

run_baseline() {
  echo "Running baseline capture..."
  find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' 2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"
  ls -laR "$CLAUDE_SUPPORT/" > "$LAB_DIR/baseline/claude-desktop-dir.txt" 2>&1
  ls -laR ~/.claude/ > "$LAB_DIR/baseline/claude-cli-dir.txt" 2>&1
  cat "$CLAUDE_SUPPORT/claude_desktop_config.json" > "$LAB_DIR/baseline/claude-desktop-config.txt" 2>&1
  cat "$CLAUDE_SUPPORT/Preferences" > "$LAB_DIR/baseline/claude-desktop-preferences.txt" 2>&1
  ls -la "$CLAUDE_SUPPORT/Claude Extensions/" > "$LAB_DIR/baseline/claude-extensions.txt" 2>&1
  ls -la "$CLAUDE_SUPPORT/Claude Extensions Settings/" > "$LAB_DIR/baseline/claude-extensions-settings.txt" 2>&1
  ls -la /tmp/ > "$LAB_DIR/baseline/tmp-listing.txt"
  for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
    [ -f "$f" ] && cp "$f" "$LAB_DIR/baseline/$(basename "$f").bak"
  done
  ps auxww > "$LAB_DIR/baseline/ps-full.txt"
  pstree > "$LAB_DIR/baseline/pstree.txt" 2>/dev/null || true
  ps auxww | grep -iE 'claude|anthropic|cowork' | grep -v grep > "$LAB_DIR/baseline/claude-process-check.txt" 2>&1 || true
  lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt"
  lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt"
  env | sort > "$LAB_DIR/baseline/env-vars.txt"
  env | grep -iE 'anthropic|claude|openai|cowork' > "$LAB_DIR/baseline/ai-env.txt" 2>/dev/null || true
  crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1 || true
  ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null || true
  ls ~/Library/LaunchAgents/ 2>/dev/null | grep -iE 'claude|anthropic|cowork' > "$LAB_DIR/baseline/claude-plist-check.txt" 2>&1 || true
  touch "$LAB_DIR/baseline/TIMESTAMP_MARKER"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/baseline/start-time.txt"
  shasum -a 256 "$LAB_DIR/baseline/"* 2>/dev/null > "$LAB_DIR/baseline/EVIDENCE-HASHES.txt" || true
  echo "Baseline complete."
}

run_phase1() {
  echo "Running Phase 1 (installation state)..."
  file /Applications/Claude.app/Contents/MacOS/Claude > "$LAB_DIR/phase1-install/binary-metadata.txt"
  ls -la /Applications/Claude.app/Contents/MacOS/Claude >> "$LAB_DIR/phase1-install/binary-metadata.txt"
  shasum -a 256 /Applications/Claude.app/Contents/MacOS/Claude >> "$LAB_DIR/phase1-install/binary-metadata.txt"
  codesign -dvvv /Applications/Claude.app > "$LAB_DIR/phase1-install/code-signing.txt" 2>&1
  plutil -p /Applications/Claude.app/Contents/Info.plist > "$LAB_DIR/phase1-install/info-plist.txt"
  codesign -d --entitlements :- /Applications/Claude.app > "$LAB_DIR/phase1-install/entitlements.txt" 2>&1
  ls -laR "$CLAUDE_SUPPORT/Claude Extensions/" > "$LAB_DIR/phase1-install/claude-extensions-listing.txt" 2>&1 || true
  cat "$CLAUDE_SUPPORT/Claude Extensions/ant.dir.ant.anthropic.chrome-control/manifest.json" > "$LAB_DIR/phase1-install/chrome-control-manifest.txt" 2>&1 || true
  cat "$CLAUDE_SUPPORT/Claude Extensions/ant.dir.ant.anthropic.notes/manifest.json" > "$LAB_DIR/phase1-install/notes-manifest.txt" 2>&1 || true
  ls -laR "$CLAUDE_SUPPORT/vm_bundles/" > "$LAB_DIR/phase1-install/vm-bundles.txt" 2>&1 || true
  cat "$CLAUDE_SUPPORT/vm_bundles/claudevm.bundle/macAddress" > "$LAB_DIR/phase1-install/vm-mac-address.txt" 2>&1 || true
  cat "$CLAUDE_SUPPORT/vm_bundles/claudevm.bundle/vmIP" > "$LAB_DIR/phase1-install/vm-ip.txt" 2>&1 || true
  cat "$CLAUDE_SUPPORT/vm_bundles/claudevm.bundle/machineIdentifier" > "$LAB_DIR/phase1-install/vm-machine-id.txt" 2>&1 || true
  du -sh /Applications/Claude.app "$CLAUDE_SUPPORT" ~/.claude/ > "$LAB_DIR/phase1-install/app-disk-footprint.txt" 2>&1 || true
  du -sh "$CLAUDE_SUPPORT"/*/ 2>/dev/null | sort -rh > "$LAB_DIR/phase1-install/app-support-breakdown.txt" || true
  ls -laR "$CLAUDE_SUPPORT/local-agent-mode-sessions/" > "$LAB_DIR/phase1-install/local-agent-sessions.txt" 2>&1 || true
  touch "$LAB_DIR/phase1-install/TIMESTAMP_MARKER"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase1-install/phase1-end-time.txt"
  shasum -a 256 "$LAB_DIR/phase1-install/"* 2>/dev/null > "$LAB_DIR/phase1-install/EVIDENCE-HASHES.txt" || true
  echo "Phase 1 complete."
}

run_phase2() {
  echo "Running Phase 2 (post-launch capture). Ensure Claude Desktop is running."
  ps auxww | grep -iE 'claude|anthropic|Virtualization' | grep -v grep > "$LAB_DIR/phase2-onboard/all-claude-processes.txt" 2>&1 || true
  ps auxww | grep -iE 'claude|Virtualization.VirtualMachine' | grep -v grep | awk '{sum += $6} END {printf "Total RSS: %.1f MB\n", sum/1024}' >> "$LAB_DIR/phase2-onboard/all-claude-processes.txt" 2>/dev/null || true
  lsof -i -nP 2>/dev/null | grep -i claude > "$LAB_DIR/phase2-onboard/claude-network-post-launch.txt" 2>&1 || true
  for ip in 160.79.104.10 34.200.175.163 34.36.57.103 18.97.36.61 57.144.104.128 98.87.131.13 35.190.46.17; do
    echo "$ip -> $(host "$ip" 2>/dev/null | head -1)"
  done > "$LAB_DIR/phase2-onboard/dns-resolution.txt"
  cat "$CLAUDE_SUPPORT/claude_desktop_config.json" > "$LAB_DIR/phase2-onboard/claude-config-running.txt" 2>&1 || true
  cat "$CLAUDE_SUPPORT/Preferences" > "$LAB_DIR/phase2-onboard/preferences-running.txt" 2>&1 || true
  touch "$LAB_DIR/phase2-onboard/TIMESTAMP_MARKER"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase2-onboard/phase2-end-time.txt"
  if [ -n "$WITH_MONITORS" ]; then
    while true; do
      echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-onboard/connections-stream.txt"
      lsof -i -nP 2>/dev/null | grep -i claude >> "$LAB_DIR/phase2-onboard/connections-stream.txt"
      sleep 2
    done &
    CONN_PID=$!
    while true; do
      echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-onboard/pstree-stream.txt"
      ps auxww | grep -iE 'claude|anthropic|Virtualization' | grep -v grep >> "$LAB_DIR/phase2-onboard/pstree-stream.txt"
      sleep 2
    done &
    PS_PID=$!
    echo "CONN_PID=$CONN_PID" > "$LAB_DIR/phase2-onboard/monitor-pids.txt"
    echo "PS_PID=$PS_PID" >> "$LAB_DIR/phase2-onboard/monitor-pids.txt"
    echo "Monitors started (PIDs $CONN_PID, $PS_PID). Run: $0 phase4 to stop them."
    return 0
  fi
  shasum -a 256 "$LAB_DIR/phase2-onboard/"* 2>/dev/null > "$LAB_DIR/phase2-onboard/EVIDENCE-HASHES.txt" || true
  echo "Phase 2 complete."
}

run_phase4() {
  echo "Running Phase 4 (teardown capture). Stop Claude Desktop first if still running."
  if [ -f "$LAB_DIR/phase2-onboard/monitor-pids.txt" ]; then
    # shellcheck source=/dev/null
    . "$LAB_DIR/phase2-onboard/monitor-pids.txt"
    [ -n "$CONN_PID" ] && [ "$CONN_PID" -eq "$CONN_PID" ] 2>/dev/null && kill "$CONN_PID" 2>/dev/null || true
    [ -n "$PS_PID" ] && [ "$PS_PID" -eq "$PS_PID" ] 2>/dev/null && kill "$PS_PID" 2>/dev/null || true
    shasum -a 256 "$LAB_DIR/phase2-onboard/"* 2>/dev/null > "$LAB_DIR/phase2-onboard/EVIDENCE-HASHES.txt" || true
  fi
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase4-teardown/phase4-end-time.txt"
  shasum -a 256 "$LAB_DIR/phase4-teardown/"* 2>/dev/null > "$LAB_DIR/phase4-teardown/EVIDENCE-HASHES.txt" || true
  find "$LAB_DIR" -name 'EVIDENCE-HASHES.txt' -exec cat {} \; > "$LAB_DIR/MASTER-HASHES.txt"
  shasum -a 256 "$LAB_DIR/MASTER-HASHES.txt" >> "$LAB_DIR/MASTER-HASHES.txt"
  echo "Phase 4 complete. MASTER-HASHES.txt updated."
}

case "$phase" in
  baseline)  run_baseline ;;
  phase1)    run_phase1 ;;
  phase2)   run_phase2 ;;
  phase4)   run_phase4 ;;
  *)
    echo "Usage: $0 <baseline|phase1|phase2|phase4> [--with-monitors]" >&2
    echo "  LAB_DIR defaults to $LAB_DIR" >&2
    echo "  Phase 3 (session analysis) is manual; see LAB-RUN-014 protocol." >&2
    echo "  For phase2 with connection/pstree stream monitors: $0 phase2 --with-monitors" >&2
    exit 1
    ;;
esac
