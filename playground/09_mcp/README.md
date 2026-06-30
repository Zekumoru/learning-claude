# 09 — MCP (Model Context Protocol)

A self-contained MCP document app: a **server** that exposes documents, a **client**
that connects to it over stdio, and a **CLI host** that wires the server's
capabilities into a streaming Claude conversation — including an `@`-mention file
dropdown and `/`-command prompts.

```
server.py    # FastMCP server: tools, resources, prompts (the capabilities)
client.py    # MCPClient: connects to a server over stdio, calls into it
commands.py  # /-command UX: completer, parser, prompt → message expansion
mentions.py  # @-mention UX: completer, resource → context injection
main.py      # the host: streaming chat loop that ties it all together
```

Run it: `uv run python -m playground.09_mcp.main`
Inspect it: `./inspect playground/09_mcp/server.py` (Inspector UI; see the gotcha below).

---

## What MCP actually is

MCP is a **protocol for connecting an LLM application to external capabilities** —
think "USB-C for AI context." Instead of every app hard-coding its own integrations,
a server advertises a standard set of capabilities and any MCP-aware host can consume
them. The win is decoupling: the server author and the host author don't need to know
about each other.

Three roles:

- **Server** — exposes capabilities (our `server.py`). Owns the data/logic.
- **Client** — a connection object that talks to exactly one server (our `MCPClient`).
- **Host** — the LLM application that owns one or more clients and decides how their
  capabilities reach the model (our `main.py`).

A host can hold many clients; each client speaks to one server.

---

## Transports: stdio

We use the **stdio transport**. The key consequence: **the client launches the server
as a subprocess** and talks to it over the process's stdin/stdout. They are not two
separately-started programs — `stdio_client(params)` in `client.py` spawns
`uv run playground/09_mcp/server.py` for us. That's why the server's
`if __name__ == "__main__": mcp.run(transport="stdio")` is the only entry point it
needs, and why `main.py` never starts the server by hand.

(The other transport is Streamable HTTP, for servers that run as independent network
services. Same primitives, different plumbing.)

---

## The three server primitives

This is the heart of the section. A server exposes three kinds of capability, and the
distinction that matters is **who is in control of invoking each one.**

### 1. Tools — *model-controlled*

```python
@mcp.tool(name="read_doc_contents", description="...")
def read_document(doc_id: Annotated[str, Field(description="Id of the document...")]) -> str:
```

A tool is something **Claude decides to call** during a turn. The host advertises the
tool list to the model; the model emits a `tool_use`; the host routes it to the client
(`client.call_tool(...)`) and feeds the result back. Tools are for *actions the model
chooses to take* — reading or editing a document here.

`edit_document` shows a robustness idea worth keeping: branch on
`content.count(old_str)` — `0` → "not found", `1` → replace, `_` → "not unique, give
more context." A tool that fails loudly with a useful message is better than one that
silently does the wrong edit.

### 2. Resources — *application/user-controlled*

```python
@mcp.resource("docs://documents", mime_type="application/json")   # direct
@mcp.resource("docs://documents/{doc_id}", mime_type="text/plain")  # templated
```

A resource is **data the app pulls in and pushes into context** — the model does not
decide to fetch it. Two flavors:

- **Direct** (`docs://documents`) — a fixed URI returning a list of doc ids.
- **Templated** (`docs://documents/{doc_id}`) — a URI with a parameter; reading
  `docs://documents/report.pdf` returns that document's content.

This is exactly the opposite control direction from tools: with a tool *Claude* reaches
out; with a resource *the application* (driven by the user) reaches out. That's what
powers the `@`-mention feature below.

### 3. Prompts — *user-controlled*

```python
@mcp.prompt(name="format", description="...")
def format_document(doc_id: ...) -> list[base.Message]:
    return [base.UserMessage(prompt)]
```

A prompt is a **reusable, parameterized message template** the user invokes
deliberately — surfaced as a `/`-command. The server returns ready-made conversation
messages (`base.UserMessage(...)`), the host drops them into the message list, and the
turn runs. Prompts let the server ship "good prompts" for its own domain rather than
making every user reinvent them.

> Import-path drift to remember: prompt message types live at
> `from mcp.server.fastmcp.prompts import base`, **not** `from mcp.server.fastmcp`.

---

## The client: connection lifecycle

`MCPClient` wraps the messy async setup behind `async with`:

```python
async with MCPClient(command="uv", args=["run", "playground/09_mcp/server.py"]) as mcp:
    tools = await mcp.list_tools()
```

What happens on `connect()`:

1. `stdio_client(params)` spawns the server and yields a `(read, write)` stream pair.
2. `ClientSession(read, write)` wraps that pair in the protocol session.
3. `session.initialize()` performs the MCP handshake (capability negotiation).

Both `stdio_client(...)` and `ClientSession(...)` are **async context managers** that
must stay open for the whole session and be closed in reverse order. Manually nesting
`async with` blocks would force all our logic to live inside them. **`AsyncExitStack`**
solves this: `enter_async_context(...)` registers each one and keeps it open; a single
`exit_stack.aclose()` in `cleanup()` unwinds them in the right order. That's how
`connect()`/`cleanup()` can be plain methods while still honoring context-manager
guarantees — and it's why `MCPClient` is itself a context manager (`__aenter__` →
`connect`, `__aexit__` → `cleanup`).

The session methods (`list_tools`, `call_tool`, `read_resource`, `list_prompts`,
`get_prompt`) are thin typed wrappers. `read_resource` is the one with logic: it reads
`result.contents[0]`, and for `application/json` resources `json.loads` the text,
otherwise returns it raw — so callers get a `list[str]` of ids from `docs://documents`
and a `str` from `docs://documents/{id}`.

---

## Errors cross the process boundary as `McpError`

A subtle but important lesson. When the server raises `ValueError("Doc ... not found")`,
that exception does **not** arrive at the client as a `ValueError` — it's serialized,
sent across the stdio boundary, and re-raised on the client side as **`McpError`**
(`from mcp import McpError`). So `inject_mentions` guards with `except McpError`, not
`except ValueError`, to skip `@mentions` that aren't real document ids. You cannot catch
the server's native exception type on the client; you catch the protocol's.

---

## Wiring capabilities into the host (`main.py`)

The host is an async streaming chat loop. Each piece maps to a primitive:

- **Tools → the model.** `to_anthropic_tool` converts each MCP `Tool` into the
  Anthropic `ToolParam` shape (`name`, `description`, `input_schema = tool.inputSchema`).
  The streaming turn (`run_turn`) collects `tool_use` blocks, calls `mcp.call_tool`,
  joins the `TextContent` results, and loops until the model stops requesting tools.
- **Resources → `@`mentions.** (below)
- **Prompts → `/`commands.** (below)

The completers are merged so a single prompt understands both `@` and `/`:

```python
completer = merge_completers([
    DocumentCompleter(doc_ids),
    CommandCompleter([p.name for p in prompts], doc_ids),
])
```

### `@`-mentions = resources surfaced as a dropdown

Built with **prompt_toolkit**:

- `DocumentCompleter.get_completions` runs on **every keystroke**. It regex-matches an
  unfinished `@prefix` at the cursor and `yield`s a `Completion` for each doc id that
  starts with that prefix. The dropdown is just whatever the generator yields right now.
- `start_position=-len(prefix)` is the key detail: it tells prompt_toolkit to **replace
  the already-typed prefix** (negative = how many chars left of the cursor to overwrite),
  so accepting `report.pdf` after typing `@rep` doesn't produce `@repreport.pdf`. The
  assertion `start_position <= 0` is why it must be negative.
- On submit, `inject_mentions` extracts every `@id`, calls `read_resource(
  "docs://documents/{id}")` for each, and **prepends the contents as
  `<document>` blocks** before the user's text. The model sees the file contents without
  ever "deciding" to fetch them — that's the resource control model in action.

### `/`-commands = prompts with arguments

- `CommandCompleter` has two modes: completing the **command name** after `/`, and —
  once a known command is typed — completing its **argument** from the doc ids.
- `parse_command` returns `(command, args)`; `expand_command` looks up the prompt,
  fills arguments **positionally** from what was typed, and **sub-prompts** for any
  missing ones (`session.prompt_async("  arg: ")`). It then calls `get_prompt` and
  converts each `PromptMessage` into an Anthropic `MessageParam`, which the loop appends
  before running the turn.

So `/format report.pdf` → server's `format` prompt with `doc_id=report.pdf` →
ready-made user message → Claude reformats the doc via `edit_document`.

---

## Schemas: `Annotated[str, Field(...)]`

Tool/prompt parameters carry descriptions that become the JSON schema the model sees.
The modern, type-checker-clean way is `Annotated[str, Field(description="...")]` — the
parameter's real type stays `str`, and `Field` rides along as metadata. The older course
style `doc_id: str = Field(...)` makes the *default value* a `Field` object, which Pyright
(rightly) flags as a type mismatch. Prefer `Annotated`.

---

## Tooling gotcha: the Inspector vs. pnpm

`uv run mcp dev server.py` and the MCP Inspector both shell out to `npx`. This repo's
root `package.json` pins `devEngines.packageManager: pnpm`, so any `npx` invocation here
dies with **`EBADDEVENGINES`**. The fix is the repo-root **`./inspect`** script, which
runs `npx @modelcontextprotocol/inspector` from a throwaway temp dir (escaping the
`devEngines` check) while pointing `uv run --directory` back at the repo:

```
./inspect playground/09_mcp/server.py
```

---

## Concept cheat-sheet

| Primitive | Who invokes it | Direction | Surfaced as | Defined with |
|-----------|----------------|-----------|-------------|--------------|
| **Tool** | the model | model → app | `tool_use` blocks | `@mcp.tool()` |
| **Resource** | the app/user | app → model context | `@`-mentions | `@mcp.resource(uri)` |
| **Prompt** | the user | user → conversation | `/`-commands | `@mcp.prompt()` |

Other things worth carrying forward:

- **stdio = client spawns the server**; the host never starts it separately.
- **`AsyncExitStack`** keeps nested async context managers open across method calls and
  tears them down in reverse — the clean way to wrap a session lifecycle.
- **Server exceptions arrive as `McpError`**, not their original Python type.
- **`start_position=-len(prefix)`** replaces the typed prefix in a prompt_toolkit
  completion; completers run per-keystroke and yield the current candidate set.
- **`Annotated[str, Field(...)]`** for parameter metadata, not `= Field(...)`.
- Prompt message types live under `mcp.server.fastmcp.prompts.base`.

---

## Using this server with Claude Code (a second host)

Everything above wires the server into **our own** host (`main.py`). But **Claude Code
is also an MCP host** — it has an MCP client built in. So the same `server.py` plugs
straight into Claude Code with **zero edits**. That's the whole point of the protocol:
the server is the portable unit; hosts are interchangeable.

What we did *not* write this time: no `to_anthropic_tool`, no `run_turn` loop, no `@`
completer, no `/` expansion, no Anthropic client. All of that is the host's job, and
Claude Code already does it. We only registered the server.

### Register it (local scope)

```bash
claude mcp add --scope local docs -- uv run playground/09_mcp/server.py
```

- `--scope local` keeps it private to you in this project (stored in `~/.claude.json`),
  not committed — right for a learning exercise. (Project scope would write to
  `.mcp.json` and be shared/committed; user scope is global.)
- `--` separates Claude Code's flags from the **command that launches the server**.
- Use `uv run` (not bare `python3`) so the server's `mcp` + `pydantic` deps resolve
  from the project's uv environment. cwd is the repo root, same as `.mcp.json` entries.
- `claude mcp get docs` shows **`Status: ✔ Connected`** once it handshakes — that alone
  proves the server is valid under Claude Code's client.
- A server added mid-session isn't loaded until you **restart Claude Code** (which then
  prompts to approve the local server).
- Remove when done: `claude mcp remove docs -s local`.

### How our three primitives surface in Claude Code

| Primitive (`server.py`) | In Claude Code |
|---|---|
| tools | `mcp__docs__read_doc_contents`, `mcp__docs__edit_document` — tools Claude calls |
| prompt `format` | slash command `/mcp__docs__format <doc_id>` |
| resource `docs://documents` | `@`-mentionable (type `@`, then `docs`) |

`/mcp` lists the server with its tools/resources/prompts.

### The `@`-mention gotchas (important)

Two things bite people here:

1. **The trigger is `@`, not `docs://`.** Typing `docs://` does nothing. You start with
   `@` — which opens a picker that merges *local files* **and** *MCP resources*. Type
   `@` then `docs` to filter down to the MCP resource; selecting it inserts
   `@docs:docs://documents`.
2. **Only the direct resource is mentionable, not individual docs.** The `@` picker is
   populated by MCP's `resources/list`, which returns only **concrete** resources —
   `docs://documents`. The **templated** `docs://documents/{doc_id}` lives behind a
   separate `resources/templates/list` call and is **not** enumerated, so there's no
   per-file dropdown. Mentioning `docs://documents` injects the **JSON index of
   filenames**, not any single document's text.

This is the key contrast with our own host: in `main.py` we *invented* the convention
"`@report.pdf` → read `docs://documents/report.pdf`" inside `inject_mentions`. That was
**host-specific glue**, not a server capability — Claude Code knows nothing about it.
Same server, different host, different `@` behavior.

To pull a specific document's contents in Claude Code, don't use `@` — just ask
("read spec.txt") and Claude calls the **`read_doc_contents` tool**. If you wanted real
per-file `@`-mentions there, you'd change the **server** to expose each document as its
own concrete resource instead of a template.

### One persistence caveat

`docs` is an in-memory dict, and each Claude Code session spawns its own server
subprocess. So `edit_document` changes (e.g. running `/mcp__docs__format report.pdf`)
last for the session but reset to the original stub on restart — nothing is written to
disk.
