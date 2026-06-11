# Usage Monitor

Exposes Claude Code's `/usage` output as an MCP tool so Claude can read token usage on your behalf.

## How it works

1. A **Stop hook** fires after every turn, sends `/usage` to your tmux pane, and saves the output to `.claude/cc-usage.txt`
2. An **MCP server** (`mcp-usage-server.py`) exposes a `get_usage` tool that reads that file
3. If tmux isn't running or the file is stale, the server falls back to parsing the session JSONL log directly

## Setup

```bash
brew install tmux
tmux new -s claude   # session must be named "claude"
claude               # run Claude Code inside this pane
```

The hook and MCP server are already registered for this project — no further config needed.

## Using the MCP tool

Ask Claude: **"show me my usage"**

Claude will call `get_usage` and return the current session's token stats:

```
Session Token Usage (12 turns)
──────────────────────────────────────
Input tokens:                  84,321
Output tokens:                 19,442
Cache creation (write):        61,200
Cache read:                 1,204,881
──────────────────────────────────────
Total tokens:               1,369,844
```

> **One-turn lag:** the output reflects usage up to the *previous* turn. The Stop hook runs after Claude finishes responding, so the current turn's tokens aren't captured until next time.

## Files

| File | Purpose |
|------|---------|
| `capture-usage.sh` | Stop hook — sends `/usage` to tmux, writes `.claude/cc-usage.txt` |
| `mcp-usage-server.py` | MCP server — exposes the `get_usage` tool |

## Troubleshooting

- **Stale or missing data** — confirm Claude Code is running inside a tmux session named `claude`
- **Inspect the capture file** — `cat .claude/cc-usage.txt` from the project root
- **Hook not firing** — run `/hooks` in Claude Code to reload config after settings changes
