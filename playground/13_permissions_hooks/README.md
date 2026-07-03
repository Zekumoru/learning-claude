# 13 — Permissions & hooks

Section 12 gave the agent tools. This section is about **saying no** — and, more
precisely, about *who* gets to say no and *when*. Up to now tool access was decided by
**static** levers set once before the run:

- `allowed_tools=[...]` — the allowlist (what the agent is even offered)
- `permission_mode=...` — a blanket policy (`acceptEdits`, `bypassPermissions`, …)

Neither can see the **actual arguments** a tool is called with. "Allow `Bash`, but never
`rm`" is invisible to an allowlist — `Bash` is either offered or not. This section adds the
runtime machinery that *can* see the arguments and decide per-call: first the
**`can_use_tool`** callback, then dynamic `PermissionUpdate`s, then the full **hook**
system.

Scripts:

- **`permission_callback.py`** — the `can_use_tool` callback: one function the SDK invokes
  before *every* tool call, handed the tool name and its concrete arguments, returning
  allow-or-deny. Here it screens `Bash` commands and blocks destructive ones with a reason
  the model then works around.

---

## `can_use_tool`: the runtime gate (`permission_callback.py`)

`can_use_tool` is a **callback you pass to `ClaudeAgentOptions`**. The SDK calls it **once
per tool call, before the call runs**, so your own code — not a static list — owns the
yes/no, with the real arguments in hand.

### The signature

The SDK exports the exact type as `CanUseTool`:

```python
async def can_use_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    ...
```

- **`tool_name`** — `"Bash"`, `"Write"`, or a custom `"mcp__<server>__<tool>"`.
- **`tool_input`** — the arguments the model *actually chose* (`{"command": "rm -rf ."}`).
  This is the whole reason the callback beats a static allowlist: you inspect **values**,
  not just which tool.
- **`context`** — a `ToolPermissionContext`; carries SDK-side hints (`suggestions`,
  `tool_use_id`, `blocked_path`, …). Ignored here.
- **returns** — one of two dataclasses (both are the `PermissionResult` union):

| Return type | Meaning | Key fields |
| --- | --- | --- |
| `PermissionResultAllow` | let it run | `updated_input` — rewrite the args before they execute; `updated_permissions` |
| `PermissionResultDeny` | block it | `message` — why (fed back to the model); `interrupt` — hard-stop the run |

Two capabilities beyond a plain allow/deny fall out of those fields:

- **`PermissionResultAllow(updated_input={...})`** rewrites arguments on the fly — sanitize
  a path, clamp a number, strip a flag — then lets the (rewritten) call run.
- **`PermissionResultDeny(message=...)`** hands the model a *reason*. It arrives as the
  tool result, so the model can adapt its plan instead of failing blind.

### Wiring it up

Just a field on the options — no server, no decorator:

```python
ClaudeAgentOptions(
    allowed_tools=["Bash"],
    can_use_tool=can_use_tool,
)
```

`allowed_tools` and `can_use_tool` stack: the allowlist decides what's *offered*, the
callback decides, per call, what's *permitted*. A tool must pass both.

### The decision body

The pattern: short-circuit tools you don't screen, pull the argument that matters, match it
against a policy, deny-with-reason or allow.

```python
if tool_name != "Bash":
    return PermissionResultAllow()

command = tool_input.get("command", "")
if any(bad in command for bad in BLOCKED):
    print(color(f"\n[Denied] {command}", RED))
    return PermissionResultDeny(
        message=f"Blocked: '{command}' matches a destructive pattern. "
        "Do not use rm/sudo/etc. — suggest the command instead of running it.",
    )

return PermissionResultAllow()
```

- The callback fires for **every** tool, so lead with the short-circuit — only `Bash` has a
  `command` string worth screening; everything else waves through.
- `BLOCKED` is a small tuple of destructive substrings (`"rm "`, `"sudo"`, `"mkfs"`, …); the
  `any(bad in command ...)` scan is the actual policy.
- On a hit: the red `[Denied]` print lets *you* watch the gate fire, and the `message` is
  what the **model** sees — so it stops trying to run the command and suggests it instead.

### What the run shows

The prompt asks for two Bash calls — a harmless `pwd` and an `rm` on `.log` files. In the
transcript the `pwd` is **allowed** and its output streams back; the `rm` trips
**`[Denied]`** in red, the deny `message` lands as that call's tool result, and the agent
**pivots** — its final answer explains or suggests the deletion instead of executing it.
That pivot is the payoff: a denial with a reason steers the model, where a bare failure
would just stall it.

---

## Run it

```bash
PYTHONPATH="$(pwd)" uv run python -m playground.13_permissions_hooks.permission_callback
```

`PYTHONPATH="$(pwd)"` puts the repo root on Python's import path so the package-relative
imports (`from ..common...`) resolve; `-m` runs the file **as a module in its package** so
those `..` imports have a package context. The script streams live and records its run into
the shared usage ledger (subscription billing).
