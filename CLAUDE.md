# CLAUDE.md

This repository is a personal sandbox for learning and experimenting with Claude Code features.

## Structure

```
sample/
├── experiments/       # Self-contained Claude Code experiments
│   └── usage-monitor/ # MCP server that exposes token usage as a callable tool
└── playground/        # Scratch files for testing Claude Code capabilities
    └── utils.ts       # Sample TypeScript code
```

## Active infrastructure

- **MCP server** — `experiments/usage-monitor/mcp-usage-server.py` is registered for this project and exposes a `get_usage` tool
- **Stop hook** — `experiments/usage-monitor/capture-usage.sh` runs after every turn to capture `/usage` output via tmux
