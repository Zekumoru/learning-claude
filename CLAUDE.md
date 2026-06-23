# CLAUDE.md

This repository is a personal sandbox for learning Claude courses and experimenting with Claude Code features.

## Structure

```
experiments/
├── usage-monitor/   # MCP server: current-session token usage via /usage + tmux
└── token-harbor/    # MCP server: all-time token usage + cost estimates across sessions
playground/          # Course exercises and Agent SDK experiments
├── 01_first_request/   # First API request
├── 02_chat/            # Chat, system prompts, temperature
├── 03_streaming/       # Streaming and structured data
├── 04_evaluation/      # Evaluation workflow, dataset generation, HTML report
├── 05_prompt_engineering/  # PromptEvaluator class: dataset generation, concurrent grading, HTML report
├── 06_tools/           # Tool use chatbots (imports tools from common/)
├── 07_rag/             # RAG pipeline: chunking, search, and RAG-powered chatbot
├── 08_claude/          # Features of Claude: extended thinking, vision, PDF, citations, caching, code execution
├── 09_mcp/             # MCP: tools, resources, prompts, server inspector, client; Claude Code & computer use
├── 10_agent/           # Agents & workflows: parallelization, chaining, routing, tools, environment inspection
├── common/             # Shared utilities, tools, and RAG infrastructure
│   ├── chat.py             # Anthropic client, conversation loops, streaming
│   ├── rag/                # Chunking, embeddings (sentence-transformers), vector/BM25/hybrid search
│   └── tools/              # All tool definitions + unified run_tool handler
├── agent.ts            # TypeScript Claude Agent SDK experiment (pnpm start-agent)
├── agent.py            # Python Claude Agent SDK experiment (uv run playground/agent.py)
└── utils.ts
```

## Tooling

- **pnpm** — manages Node.js dependencies; `package.json` at repo root
- **uv** — manages Python dependencies; `pyproject.toml` at repo root

## Conventions

- Always use relative paths in scripts, config files, and any generated files — never absolute paths.
- Always use proper types from libraries/SDKs — prefer typed constructs (e.g. `ToolParam`, `ToolTextEditor20250728Param`) over untyped dicts.
- When guiding the user through code, present it step by step — explain what each piece does before moving on. "Guide me" means present the code for the user to type out, not ask the user to write it from scratch. The user will write code themselves when they have a feel for the concept — don't over-explain things they already grasp.
- Treat all code — including learning exercises — with the same quality standards as production code. No `any` types, no ignoring errors, no "it's just a demo" shortcuts. When encountering errors, find and fix the root cause — don't just silence the tooling. Search online if needed.

## Active infrastructure

Both MCP servers are registered via `.mcp.json` (project scope) using relative paths — portable across clones. Claude Code will prompt for approval on first launch.

- **usage-server** (`experiments/usage-monitor/mcp-usage-server.py`) — exposes `get_usage`, returns token stats for the current session; prefers tmux-captured `/usage` output and falls back to parsing the JSONL log
- **token-harbor** (`experiments/token-harbor/mcp-token-harbor.py`) — exposes `get_usage`, aggregates token usage and cost estimates across all sessions with optional date-range and project filtering
- **Stop hook** — `experiments/usage-monitor/capture-usage.sh` runs after every turn to capture `/usage` output via tmux into `.claude/cc-usage.txt`
