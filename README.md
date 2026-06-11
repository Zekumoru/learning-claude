# Learning Claude

A personal sandbox for experimenting with Claude Code features, with two MCP servers included.

## Requirements

- **Python 3** — required for both MCP servers
- **tmux** *(optional)* — enables real-time usage capture for `usage-server`; without it, the server falls back to JSONL parsing and the last turn will be one behind

## Getting started

Clone the repo and open it in Claude Code. Both MCP servers activate automatically — no extra setup needed.

```bash
git clone https://github.com/Zekumoru/learning-claude.git
cd learning-claude
claude .
```

For real-time usage tracking, run Claude Code inside a tmux session named `"claude"`:

```bash
brew install tmux          # skip if already installed
tmux new -s claude         # session must be named "claude"
claude .                   # run Claude Code inside this pane
```

A stop hook in `.claude/settings.json` automatically runs `capture-usage.sh` after every turn — it sends `/usage` to the tmux pane and saves the output so `usage-server` can read it instantly.

## MCP servers

### usage-server

Reports token usage for the **current session**.

Ask Claude: *"show me my usage"*

```
Session Token Usage (12 turns)
──────────────────────────────────────
Input tokens:                  84,321
Output tokens:                 19,442
Cache creation (write):        61,200
Cache read:               1,204,881
──────────────────────────────────────
Total tokens:             1,369,844
```

### token-harbor

Reports token usage and **estimated cost** across all sessions, with optional filtering.

Ask Claude: *"how much have I spent this month?"* or *"show usage for today"*

```
Token Usage & Cost Summary (all time, all projects)
Sessions: 42  |  Turns: 318  |  Projects: 5
──────────────────────────────────────────────────────────────────────────
Model                      Input      Output   Cache↑       Cache↓       Cost
──────────────────────────────────────────────────────────────────────────
claude-sonnet-4-6      1,204,881     284,032  921,044  18,204,881    $84.1234
──────────────────────────────────────────────────────────────────────────
TOTAL                  1,204,881     284,032  921,044  18,204,881    $84.1234
──────────────────────────────────────────────────────────────────────────
Prices: live (LiteLLM)  |  As of: 2026-06-11T08:00:00Z
```

Supported parameters: `start_date`, `end_date` (YYYY-MM-DD), and `project` (`"all"`, `"current"`, or a slug).

## Structure

```
experiments/
├── usage-monitor/   # usage-server — current-session stats via tmux + JSONL fallback
│   ├── mcp-usage-server.py
│   └── capture-usage.sh
└── token-harbor/    # token-harbor — all-time cost dashboard
    └── mcp-token-harbor.py
playground/          # scratch files
```
