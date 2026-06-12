# CLAUDE.md

This repository is a personal sandbox for learning and experimenting with Claude Code features.

## Structure

```
experiments/
├── usage-monitor/   # MCP server: current-session token usage via /usage + tmux
└── token-harbor/    # MCP server: all-time token usage + cost estimates across sessions
playground/          # Scratch files for testing Claude Code and Agent SDK
├── agent.ts         # TypeScript Claude Agent SDK experiment (pnpm start-agent)
├── agent.py         # Python Claude Agent SDK experiment (uv run playground/agent.py)
└── utils.ts
```

## Tooling

- **pnpm** — manages Node.js dependencies; `package.json` at repo root
- **uv** — manages Python dependencies; `pyproject.toml` at repo root

## Conventions

- Always use relative paths in scripts, config files, and any generated files — never absolute paths.

## Active infrastructure

Both MCP servers are registered via `.mcp.json` (project scope) using relative paths — portable across clones. Claude Code will prompt for approval on first launch.

- **usage-server** (`experiments/usage-monitor/mcp-usage-server.py`) — exposes `get_usage`, returns token stats for the current session; prefers tmux-captured `/usage` output and falls back to parsing the JSONL log
- **token-harbor** (`experiments/token-harbor/mcp-token-harbor.py`) — exposes `get_usage`, aggregates token usage and cost estimates across all sessions with optional date-range and project filtering
- **Stop hook** — `experiments/usage-monitor/capture-usage.sh` runs after every turn to capture `/usage` output via tmux into `.claude/cc-usage.txt`
