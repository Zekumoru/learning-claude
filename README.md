# Learning Claude

A personal sandbox for experimenting with Claude Code features, with two MCP servers included.

## MCP servers

Both servers are pre-configured in `.claude/settings.json` and activate automatically when you open this project in Claude Code. All you need is Python 3.

### usage-server

Reports token usage for the **current session**.

Ask Claude: *"show me my usage"*

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

For the tmux-based live capture (more accurate, no one-turn lag):

```bash
brew install tmux
tmux new -s claude   # session must be named "claude"
claude               # run Claude Code inside this pane
```

Without tmux, the server falls back to parsing the session JSONL log directly — the last turn will be one behind.

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
