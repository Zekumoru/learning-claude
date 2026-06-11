#!/bin/bash
TMUX_SESSION="claude"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
while [ "$PROJECT_ROOT" != "/" ] && [ ! -f "$PROJECT_ROOT/CLAUDE.md" ]; do
  PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done
OUTPUT_FILE="$PROJECT_ROOT/.claude/cc-usage.txt"

# Exit silently if the tmux session doesn't exist
tmux has-session -t "$TMUX_SESSION" 2>/dev/null || exit 0

# Wait for Claude Code to settle into idle state after the turn
sleep 0.3

# Invoke /usage in the Claude Code pane
tmux send-keys -t "$TMUX_SESSION" '/usage' Enter

# Wait for the output to render
sleep 0.5

# Capture visible terminal buffer and extract the usage block
tmux capture-pane -t "$TMUX_SESSION" -p | grep -A 8 "Total cost:" > "$OUTPUT_FILE" 2>/dev/null || true
