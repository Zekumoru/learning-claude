# 12 — Custom tools

Section 11 handed the agent **built-in** tools (`Read`, `Grep`, `Write`, …) and let the
SDK run the loop. This section adds the two things that make an agent *yours*: control
over **how hard it thinks**, and the ability to give it **tools you wrote** — Python
functions the agent can call, running in your own process.

Three scripts:

- **`thinking_effort.py`** — turns on **extended thinking** and runs the same question at
  two **`effort`** levels, streaming the thinking + answer live, so you can watch the
  reasoning depth (and token cost) change.
- **`custom_tool.py`** — the minimal custom tool: one **`@tool`** function, wrapped in an
  in-process **`create_sdk_mcp_server`**, that the agent calls to get something it can't
  know on its own (the current time in a timezone).
- **`text_tools.py`** — **two** custom tools in one server with **typed input *and*
  output** (a `TypedDict` for the args and a `TypedDict` for the result, serialized to
  JSON), doing real deterministic work the model fumbles freehand.

---

## Extended thinking + `effort` (`thinking_effort.py`)

Two options work together to control reasoning:

```python
ClaudeAgentOptions(
    thinking={"type": "adaptive", "display": "summarized"},
    effort=effort,  # EffortLevel: "low" | "medium" | "high" | ...
)
```

- **`thinking`** turns reasoning on. `"type": "adaptive"` lets the model decide how much to
  think per request (the current API shape — `budget_tokens` is gone on 4.6+ models).
  `"display": "summarized"` streams a readable summary of the reasoning rather than the raw
  chain.
- **`effort`** (typed `EffortLevel`) is the dial: higher effort → deeper reasoning → more
  thinking tokens → higher cost. `thinking_effort.py` runs the *same* prompt at `"low"`
  then `"high"` so the difference is visible in both the streamed reasoning and the
  recorded token counts.

### Watching thinking stream by

With `include_partial_messages=True` you get raw `StreamEvent`s, and thinking arrives as
its own block type — distinct event `type`s for the start marker and the text deltas:

```python
case "content_block_start" if event.get("content_block", {}).get("type") == "thinking":
    print(color("[Thinking]", YELLOW))
case "content_block_delta" if event.get("delta", {}).get("type") == "thinking_delta":
    print(event["delta"].get("thinking", ""), end="", flush=True)
```

Compare that with the **answer** deltas (`content_block` type `"text"`, delta type
`"text_delta"`) — same event shape, different type strings, so one `match` on
`event["type"]` + a guard on the inner type routes both.

---

## Custom tools: the mental model (`custom_tool.py`)

A custom tool is **your Python function, exposed to the agent as something it can call**.
The SDK ships it as an **in-process MCP server** — "MCP" is the tool protocol, but
`create_sdk_mcp_server` runs it **inside your Python process** (no subprocess, no IPC,
no network), so calling a tool is just an `await` on your coroutine.

Three pieces wire it up:

```python
@tool("current_time", "Current time in an IANA timezone", CurrentTimeArgs)
async def current_time(args):
    now = datetime.now(ZoneInfo(args["timezone"]))
    return {"content": [{"type": "text", "text": now.strftime("%Y-%m-%d %H:%M:%S %Z")}]}

server = create_sdk_mcp_server(name="time_tools", tools=[current_time])

ClaudeAgentOptions(
    mcp_servers={"time_tools": server},
    allowed_tools=["mcp__time_tools__current_time"],
)
```

### `@tool(name, description, input_schema)`

Decorates a coroutine into an SDK tool.

- **`name`** — the tool's identity (what the model calls).
- **`description`** — how the model decides *when* to call it. This is prompt text; write it
  like an instruction.
- **`input_schema`** — the shape of the arguments (see typing below).

### The handler contract

The function is **async**, takes a **single `args` dict**, and returns a dict with a
`content` list of blocks:

```python
return {"content": [{"type": "text", "text": ...}]}
```

Signal failure by adding `"is_error": True` to that return dict instead of raising.

### The naming rule that trips everyone up

The name the model must call is **`mcp__` + server-key + `__` + tool-name**:

| Piece | From | Example |
| --- | --- | --- |
| server-key | the key in `mcp_servers={...}` | `time_tools` |
| tool-name | the first arg to `@tool` | `current_time` |
| full name | `mcp__<key>__<tool>` | `mcp__time_tools__current_time` |

All three must line up — the `@tool` name, the entry in `tools=[...]`, and the string in
`allowed_tools`. A mismatch means the agent literally cannot see or call the tool.

---

## Typing the args: `@tool` defaults to `Any` — here's the fix

Checked in the SDK source: the `@tool` decorator types the handler as
`Callable[[Any], Awaitable[dict[str, Any]]]` and returns `SdkMcpTool[Any]`. So by default
`args` is `Any` — no field checking, no autocomplete.

The fix is to pass a **`TypedDict`** as `input_schema` and annotate the handler with it:

```python
class CurrentTimeArgs(TypedDict):
    timezone: Annotated[str, "IANA timezone name, e.g. 'Asia/Tokyo'"]

@tool("current_time", "Current time in an IANA timezone", CurrentTimeArgs)
async def current_time(args: CurrentTimeArgs):
    now = datetime.now(ZoneInfo(args["timezone"]))  # args["timezone"] is now typed str
    ...
```

`input_schema` accepts either a raw JSON-schema `dict` **or** a `TypedDict` class. When you
pass a class, the SDK's `_typeddict_to_json_schema` converts it:

- **`__required_keys__`** → the JSON schema's `"required"` array. A plain `str` field lands
  there automatically, so the model must supply it:
  ```json
  {"type": "object",
   "properties": {"timezone": {"type": "string", "description": "IANA timezone name, e.g. 'Asia/Tokyo'"}},
   "required": ["timezone"]}
  ```
- **`Annotated[str, "..."]`** → the per-field `"description"` (shown above) — this is how the
  model learns what each argument means.
- **`NotRequired[str]`** → drops the field out of `__required_keys__`, so it becomes optional
  in `"required"`.

Net: you get a checked `args` dict *and* a correct schema for the model, from one
`TypedDict` — no raw JSON schema, no `Any`.

---

## Real tools + typed output (`text_tools.py`)

`custom_tool.py` had one tool returning a bare string. `text_tools.py` pushes on three
things at once.

### 1. More than one tool in one server

`create_sdk_mcp_server(tools=[text_stats, longest_words])` registers a list; each tool
needs its own `mcp__text_tools__<name>` entry in `allowed_tools`. The model picks and
**chains** them itself — one prompt ("give me its stats *and* its three longest words")
drives two tool calls in a single turn.

### 2. Typed *output*, not just typed input

The new piece: define a `TypedDict` for the **result**, build it, annotate the local var so
the type checker enforces the shape, then `json.dumps` it into the text block:

```python
class TextStats(TypedDict):
    characters: int
    words: int
    sentences: int
    reading_seconds: int

async def text_stats(args: TextStatsArgs):
    words = args["text"].split()
    stats: TextStats = {
        "characters": len(args["text"]),
        "words": len(words),
        "sentences": len(re.findall(r"[.!?]+", args["text"])),
        "reading_seconds": round(len(words) / 200 * 60),
    }
    return {"content": [{"type": "text", "text": json.dumps(stats)}]}
```

The model receives structured JSON (`{"characters": 161, ...}`) instead of prose you
hand-formatted — machine-readable, and typed end to end (`TypedDict` in, `TypedDict` out).

### 3. Real deterministic work

Exact character/word/sentence counts and length-ranking are things Claude gets wrong
freehand — the perfect use for a tool. The tool *guarantees* the numbers; the model just
narrates them.

---

## Note: server-side tools (read-only)

The tools above run **in-process** — you write the handler. Anthropic also ships
**server-side** tools that run on *their* infrastructure; you opt in **by name**, no
handler and no `create_sdk_mcp_server`:

```python
ClaudeAgentOptions(allowed_tools=["WebSearch"])
```

Not wired up in these scripts — a live web search bills against the run, and the surface is
thin through the SDK. It's noted in `text_tools.py` as the spot where a server-side tool
would plug in.

---

## Observed: deferred tools & `ToolSearch`

When you run `text_tools.py`, the **first** tool call in the transcript is `ToolSearch`,
not one of yours. That's the SDK's **deferred-tool** mechanism: your MCP tools' full
schemas aren't loaded into the model's context up front — the model first calls
`ToolSearch` to fetch their definitions by name, *then* calls them. It's a context-saving
optimization, and it's why two tools produce three tool calls.

---

## Run them

```bash
PYTHONPATH="$(pwd)" uv run python -m playground.12_custom_tools.thinking_effort
PYTHONPATH="$(pwd)" uv run python -m playground.12_custom_tools.custom_tool
PYTHONPATH="$(pwd)" uv run python -m playground.12_custom_tools.text_tools
```

`PYTHONPATH="$(pwd)"` puts the repo root on Python's import path so the package-relative
imports (`from ..common...`) resolve; `-m` runs the file **as a module in its package** so
those `..` imports have a package context. All three stream live and record their run into
the shared usage ledger (subscription billing).
