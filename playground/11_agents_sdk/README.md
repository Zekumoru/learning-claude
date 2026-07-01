# 11 — Claude Agent SDK

Section 10 drew the line between **workflows** (you script the steps) and **agents**
(Claude plans its own steps from a goal + tools). This section builds agents with the
**Claude Agent SDK** (`claude-agent-sdk`) — the same engine that powers Claude Code,
exposed as a Python library. Instead of hand-writing the tool-use loop (call Claude →
run the tool it asked for → feed the result back → repeat), the SDK **runs that whole
loop for you** and hands back a stream of messages describing what happened.

So far this section covers two scripts:

- **`first_agent.py`** — the minimal agent: one `query()` call, iterate the messages.
- **`configured_agent.py`** — the same shape, but driven by a fully-specified
  `ClaudeAgentOptions` (restricted toolset, preset system prompt, budget guard).

---

## The core call: `query()`

```python
async for message in query(prompt=prompt, options=options):
    ...
```

`query()` is the whole SDK in one function. You give it a **prompt** and an **options**
object; it spins up the agent loop and **yields messages** as the agent works. Two things
to internalize:

- It's **async** — you `async for` over it, and the whole thing runs inside
  `asyncio.run(main())`. The agent does real work (spawning a subprocess, calling tools)
  between yields.
- Each yielded item is a **message**, not a chunk of text. You `match` on the message
  type to decide what to render. The loop ends when a terminal `ResultMessage` arrives.

This is the key mental shift from the plain Messages API: there you get **one response**
back from one call; here you get a **transcript of an entire multi-turn agent run** from
one call, because the SDK already ran every turn.

---

## The message model: what `query()` yields

The stream is a sequence of typed messages, each carrying typed **content blocks**. The
ones we handle:

| Message | Meaning | Blocks inside |
| --- | --- | --- |
| `AssistantMessage` | Claude's turn | `TextBlock` (prose), `ToolUseBlock` (a tool it wants to run), `ThinkingBlock` |
| `UserMessage` | fed *back into* Claude — this is how **tool results** re-enter the loop | `ToolResultBlock` |
| `ResultMessage` | the **terminal** message: the run is over | — |

The non-obvious one is **`UserMessage`**. In an agent loop, when a tool finishes, its
output has to go *back to Claude* as the next input — and the SDK models that as a
`UserMessage` containing a `ToolResultBlock`. So "user" here doesn't mean *you typed
something*; it means *this is what the model sees as its next user turn*.

Rendering pattern (nested `match`):

```python
match message:
    case AssistantMessage(content=content):
        for block in content:
            match block:
                case TextBlock(text=text): ...
                case ToolUseBlock(name=name, input=tool_input): ...
    case ResultMessage(...): ...
```

---

## `ResultMessage`: how a run ends

Every run terminates in exactly one `ResultMessage`. The fields worth knowing:

- **`subtype: str`** — *how* it ended. Four values the CLI emits:
  `"success"`, `"error_max_turns"`, `"error_max_budget_usd"`, `"error_during_execution"`.
- **`is_error: bool`** — `True` for the three non-success subtypes.
- **`num_turns: int`** — how many turns the agent took.
- **`total_cost_usd: float | None`** — the SDK's own cost figure for the whole run
  (it computes this itself; can be `None`).
- **`usage: dict[str, Any] | None`** — whole-run token totals
  (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`).

**Gotcha vs. the Messages API:** here `usage` is a plain **`dict`** and there's **no
`.model`** field on the message — unlike the Messages API, where usage is a Pydantic
object and the response carries `.model`. Read tokens with `.get(...)`, not attribute
access.

Because `subtype` is a plain string, you can pattern-match its *value* and split endings
cleanly — matching on the field **and** binding the whole object in one pattern:

```python
case ResultMessage(subtype="error_max_budget_usd", total_cost_usd=cost) as result: ...
case ResultMessage(subtype=subtype) as result if subtype != "success": ...   # other errors
case ResultMessage(num_turns=turns) as result: ...                            # success
```

**Order matters:** the specific budget case must precede the guarded generic-error case,
or the generic branch would swallow it.

---

## Configuring the agent: `ClaudeAgentOptions`

Everything about *how* the agent behaves lives in one dataclass. The many fields group
into four buckets.

### 1. What the agent can do — the tool surface

Three separate levers, easy to conflate:

- **`tools`** — the **base set** of built-in tools that even *exist* this session.
  `["Glob","Read","Grep"]`, or `[]` to disable all, or
  `{"type":"preset","preset":"claude_code"}` for the full kit.
- **`allowed_tools`** — of those, which **auto-run without a permission prompt**.
- **`disallowed_tools`** — removed from the model's context entirely.

> **The trap:** setting only `allowed_tools=[...]` does **not** restrict the toolbox — all
> built-ins are still present; those names just skip the prompt. To *genuinely* limit what
> the agent can reach, set **`tools`**. Rule of thumb: `tools` = "these exist";
> `allowed_tools` = "don't ask me about these".

### 2. Who the agent is — identity & knowledge

- **`system_prompt`** — three shapes:
  - a plain `str` → a **bare** agent (no Claude-Code scaffolding),
  - `{"type":"preset","preset":"claude_code"}` → Claude Code's full system prompt,
  - `{...,"append":"..."}` → that preset **plus** your extra instructions.
- **`setting_sources`** — which filesystem settings to load (`"user"`, `"project"`,
  `"local"`). **Gotcha:** to load your `CLAUDE.md`, the list **must include `"project"`**.
  Pass `[]` for full isolation.

### 3. Where it runs — filesystem scope

- **`cwd`** — the working directory the agent operates in.
- **`add_dirs`** — extra directories it may reach (absolute paths).

### 4. Guardrails — cost & loop control

- **`max_turns`** — hard cap on turns.
- **`max_budget_usd`** — **hard cost stop**; exceeding it ends the run with
  `subtype="error_max_budget_usd"`. (This ending only *exists* when you set the option.)
- **`permission_mode`** — how permission decisions resolve (see below).
- **`model`** / **`fallback_model`** — which model, and a backup.

---

## Permission modes

`permission_mode` controls what happens when a tool call would need approval:

| Mode | Behavior |
| --- | --- |
| `"default"` | Standard — prompts for dangerous operations. |
| `"acceptEdits"` | Auto-accept file edits. |
| `"plan"` | Planning only — no tools execute. |
| `"dontAsk"` | Never prompt; **deny** anything not pre-approved. |
| `"bypassPermissions"` | Skip all permission checks. |

The pairing used so far is **`allowed_tools=[read-only tools]` + `permission_mode="dontAsk"`** —
a silent, non-interactive, read-only agent: the allowed tools run without prompting, and
`dontAsk` denies everything else instead of blocking on a prompt that a script can't answer.

---

## Cheat-sheet

| Concept | One-liner |
| --- | --- |
| **Agent SDK** | Claude Code as a library — it runs the whole agent loop for you. |
| **`query()`** | `async for message in query(prompt=…, options=…)` — one call, a full run's worth of messages. |
| **`AssistantMessage`** | Claude's turn; holds `TextBlock` / `ToolUseBlock`. |
| **`UserMessage`** | Tool results fed *back* to Claude (a `ToolResultBlock`), not something you typed. |
| **`ResultMessage`** | Terminal message; `subtype` says how it ended, `usage` is a **dict**, no `.model`. |
| **`tools` vs `allowed_tools`** | `tools` = which exist; `allowed_tools` = which skip the prompt. Don't confuse them. |
| **`system_prompt` preset** | `str` = bare agent; `{"preset":"claude_code",...}` = full Claude Code prompt (+ `append`). |
| **`setting_sources`** | Must include `"project"` to load `CLAUDE.md`; `[]` = isolation. |
| **`max_budget_usd`** | Hard cost ceiling → `subtype="error_max_budget_usd"`. |
| **`dontAsk`** | Don't prompt; deny anything not pre-approved — the script-friendly mode. |

The throughline: the SDK turns "an agent" from *code you write around the Messages API*
into *one configured `query()` call*. Your job shifts from running the loop to **specifying
the agent** — its tools, identity, filesystem reach, and guardrails — through
`ClaudeAgentOptions`, then reading the message stream it produces.
