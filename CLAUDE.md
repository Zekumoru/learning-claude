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
├── 11_agents_sdk/      # Claude Agent SDK (Python): options, multi-turn, streaming, interrupts, plan/permission modes
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
- Always use proper types from libraries/SDKs — prefer typed constructs (e.g. `ToolParam`, `ToolTextEditor20250728Param`) over untyped dicts. Never use `object` or `Any` as lazy type annotations — find the correct specific type and annotate variables explicitly.
- When guiding the user through code, present it step by step — explain what each piece does before moving on. "Guide me" means present the code for the user to type out, not ask the user to write it from scratch. The user will write code themselves when they have a feel for the concept — don't over-explain things they already grasp.
- Treat all code — including learning exercises — with the same quality standards as production code. No `any` types, no ignoring errors, no "it's just a demo" shortcuts. When encountering errors, find and fix the root cause — don't just silence the tooling. Search online if needed.
- **Teach concepts before code.** For each new sub-section, explain briefly what we're building and why *before* writing anything, so the user holds the idea in mind while coding.
- **Scaffold split.** Guide the user to write only the genuinely-new, concept-bearing lines. For anything already written in a prior exercise (imports, `ClaudeAgentOptions` block, stream/drain loop, usage-tracker wiring, `main()` skeleton), hand it over as ready-made scaffold with a clearly marked `# YOU: ...` hole for the new part — don't make the user retype boilerplate. **Before generating scaffold, first state what it will contain and wait for the user's okay.**
- **Default every Agent SDK script to streaming** (`include_partial_messages=True`) and always wire in the usage tracker (`init_db` + `record_result`) — both go into the scaffold automatically.

## Learning progress & syllabus

**Section 11 (Claude Agent SDK, Python) — COMPLETE.** Covered `ClaudeAgentOptions`, `query()` vs `ClaudeSDKClient`, multi-turn, streaming, interrupts, and plan/permission modes. Scripts live in `playground/11_agents_sdk/`.

**Next up — sections 12–16 (self-directed Agent SDK deep dive).** Spine is ordered; each builds on the last. 23 sub-sections total.

- **12 — Custom tools:** 12a thinking/effort warm-up · 12b first `@tool` · 12c real tools + typed I/O (with a read-only note on server-side tool blocks) · *(server tools demoted to a note — under-documented through the SDK, needs a paid live run to confirm)*
- **13 — Permissions & hooks:** 13a `can_use_tool` · 13b dynamic `PermissionUpdate` · 13c/13d hooks (Pre/PostToolUse, then the rest) · 13e `PreCompact` · 13f `DeferredToolUse`
- **14 — Subagents:** 14a `AgentDefinition`/`agents` · 14b task lifecycle messages · 14c `list_subagents`/`get_subagent_messages` · 14d skills & plugins
- **15 — Sessions:** 15a resume/continue · 15b `fork_session` · 15c session store · 15d rename/tag/delete/summarize
- **16 — Production hardening:** 16a sandbox (bash, macOS/Linux) · 16b budgets & rate limits · 16c `fallback_model` + errors · 16d `get_context_usage()` · 16e custom `Transport` (optional)

## Active infrastructure

Both MCP servers are registered via `.mcp.json` (project scope) using relative paths — portable across clones. Claude Code will prompt for approval on first launch.

- **usage-server** (`experiments/usage-monitor/mcp-usage-server.py`) — exposes `get_usage`, returns token stats for the current session; prefers tmux-captured `/usage` output and falls back to parsing the JSONL log
- **token-harbor** (`experiments/token-harbor/mcp-token-harbor.py`) — exposes `get_usage`, aggregates token usage and cost estimates across all sessions with optional date-range and project filtering
- **Stop hook** — `experiments/usage-monitor/capture-usage.sh` runs after every turn to capture `/usage` output via tmux into `.claude/cc-usage.txt`
