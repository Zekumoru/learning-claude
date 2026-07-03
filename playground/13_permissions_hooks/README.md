# 13 — Permissions & hooks

Section 12 gave the agent tools. This section is about **saying no** — and, more
precisely, about *who* gets to say no and *when*. Up to now tool access was decided by
**static** levers set once before the run:

- `allowed_tools=[...]` — an **auto-approve** list (tools that run without asking)
- `permission_mode=...` — a blanket policy (`default`, `acceptEdits`, `bypassPermissions`, …)

Neither can see the **actual arguments** a tool is called with. "Allow `Bash`, but never
`rm`" is invisible to an allowlist. This section adds the runtime machinery that *can* see
the arguments and decide per-call: first the **`can_use_tool`** callback, then dynamic
`PermissionUpdate`s, then (later) the full **hook** system.

Scripts:

- **`permission_callback.py`** — the `can_use_tool` callback: a function the SDK invokes
  when a tool call would otherwise prompt, handed the tool name and its concrete arguments,
  returning allow-or-deny. Here it screens `Bash` commands and blocks destructive ones with
  a reason the model then works around.
- **`dynamic_permission.py`** — the callback returning **`updated_permissions`** to change
  the session's permission policy on the fly, by applying the CLI's own
  **`context.suggestions`** so subsequent calls stop asking.

---

## `can_use_tool`: the runtime gate (`permission_callback.py`)

`can_use_tool` is a **callback you pass to `ClaudeAgentOptions`**. When a tool call needs a
permission decision, the SDK calls your function — so your own code, not a static list,
owns the yes/no, with the real arguments in hand.

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
- **`context`** — a `ToolPermissionContext`; carries SDK-side hints. Its `suggestions` field
  is the star of `dynamic_permission.py` (below).
- **returns** — one of two dataclasses (both are the `PermissionResult` union):

| Return type | Meaning | Key fields |
| --- | --- | --- |
| `PermissionResultAllow` | let it run | `updated_input` — rewrite the args before they execute; `updated_permissions` — change the policy |
| `PermissionResultDeny` | block it | `message` — why (fed back to the model); `interrupt` — hard-stop the run |

- **`PermissionResultAllow(updated_input={...})`** rewrites arguments on the fly — sanitize
  a path, clamp a number, strip a flag — then lets the (rewritten) call run.
- **`PermissionResultDeny(message=...)`** hands the model a *reason*. It arrives as the
  tool result, so the model can adapt its plan instead of failing blind.

### When is the callback actually consulted? (the part that bites)

`can_use_tool` is **not** called for every tool. It fires only when a call would *otherwise
prompt*. It is **skipped** — the tool just runs — in three cases (all verified by running
this script):

1. **The tool is on `allowed_tools`.** That list is *auto-approve*, not "offer". A tool on
   it never reaches a prompt, so the callback never sees it. → **Do not** put a tool you
   want to gate in `allowed_tools`. (An earlier version of this script had `allowed_tools=["Bash"]`
   and the callback silently never fired.)
2. **A `permissions.allow` rule in settings matches.** The SDK's subprocess reads your real
   settings (`~/.claude`, `.claude/settings.json`, `.claude/settings.local.json`). This
   repo's local file has `"Bash(git *)"`, so *every* git command is pre-approved and bypasses
   the callback. → Pass **`setting_sources=[]`** (isolation mode) so no stray rule leaks in.
3. **The command is auto-classified "safe."** In `default` mode, read-only commands
   (`git status`, `git log`, `git branch`) are approved without prompting; only mutating /
   dangerous ones (`mkdir`, `rm`, `dd`, a piped `ls | grep`) reach the callback. → Drive the
   demo with **mutating** commands.

So the wiring that actually lets the callback run:

```python
ClaudeAgentOptions(
    permission_mode="default",   # prompt for non-safe operations
    setting_sources=[],          # don't inherit allow-rules from settings files
    can_use_tool=can_use_tool,   # ...which routes those prompts here
    # note: Bash is deliberately NOT in allowed_tools
)
```

### The decision body

The pattern: short-circuit tools you don't screen, pull the argument that matters, match it
against a policy, deny-with-reason or allow.

```python
if tool_name != "Bash":
    return PermissionResultAllow()

command = tool_input.get("command", "")
print(color(f"\n[Screening] {command}", CYAN))
if any(bad in command for bad in BLOCKED):
    print(color(f"[Denied] {command}", RED))
    return PermissionResultDeny(
        message=f"Blocked: '{command}' matches a destructive pattern. "
        "Do not use rm/sudo/etc. — suggest the command instead of running it.",
    )

return PermissionResultAllow()
```

- `BLOCKED` is a small tuple of destructive substrings (`"rm "`, `"sudo"`, `"mkfs"`, …); the
  `any(bad in command ...)` scan is the actual policy.
- On a hit: the red `[Denied]` print lets *you* watch the gate fire, and the `message` is
  what the **model** sees — so it stops and suggests the command instead.

### What the run shows

The prompt drives two mutating Bash calls in a temp dir — `mkdir archive` and `rm -rf` the
tree. Both reach the callback (`[Screening]` prints for each). The `mkdir` is **allowed** and
runs; the `rm -rf` trips **`[Denied]`** in red, the deny `message` lands as that call's tool
result, and the agent **pivots** — its answer explains the block and hands you the `rm`
command to run yourself. That pivot is the payoff: a denial *with a reason* steers the model,
where a bare failure would just stall it.

---

## Dynamic `PermissionUpdate` via `context.suggestions` (`dynamic_permission.py`)

Goal: **grant once, then stop asking.** The first time a gated operation is approved, change
the session's policy so the rest run without re-consulting the callback.

The lever is **`PermissionResultAllow(updated_permissions=[...])`** — a list of
`PermissionUpdate`s applied when you allow the call. The trap is building them by hand: a
`PermissionUpdate(type="setMode", mode="acceptEdits")` **without** a `destination` field is
malformed and silently ignored, and an `addRules` rule with `rule_content=None` matches
nothing. (Both were tried; neither did anything.)

The reliable way is to let the CLI build them for you. Every permission request comes with
**`context.suggestions`** — a list of correctly-formed `PermissionUpdate`s (the same
"accept edits / always allow" choices the interactive prompt would offer). You just echo
them back:

```python
if tool_name != "Write":
    return PermissionResultAllow()

print(color(f"[Applying suggestions] {context.suggestions}", GREEN))
return PermissionResultAllow(updated_permissions=list(context.suggestions))
```

For a `Write` in `default` mode, `context.suggestions` is:

```python
[PermissionUpdate(type='setMode', mode='acceptEdits', destination='session'),
 PermissionUpdate(type='addDirectories', directories=[<the target dir>], destination='session')]
```

Note the `setMode` carries `destination='session'` — the piece hand-built attempts left out.
Returning these flips the session into `acceptEdits`, so the next file write is auto-accepted.

### The `PermissionUpdate` shape

One dataclass, a `type` discriminator, and different required fields per type:

| `type` | Fields it reads |
| --- | --- |
| `addRules` / `replaceRules` / `removeRules` | `rules`, `behavior`, `destination` |
| `setMode` | `mode`, **`destination`** |
| `addDirectories` / `removeDirectories` | `directories`, `destination` |

`destination` is `'session'` (in-memory, this run only), or `'userSettings'` /
`'projectSettings'` / `'localSettings'` (persisted to those files for future runs).

### What the run shows

The prompt asks for two separate `Write` calls. The transcript shows **`[Callback consulted]
Write` exactly once** — on the first write. Applying its suggestions switches the session to
`acceptEdits`, so the **second write is auto-accepted and never reaches the callback**. Two
writes, one consultation: that silence is the dynamic grant working — and it's why keeping
your own "already granted" bookkeeping isn't needed *here* (a correctly-formed update
short-circuits the callback), whereas without one it would be (the callback has no implicit
memory of its own).

---

## Run them

```bash
PYTHONPATH="$(pwd)" uv run python -m playground.13_permissions_hooks.permission_callback
PYTHONPATH="$(pwd)" uv run python -m playground.13_permissions_hooks.dynamic_permission
```

`PYTHONPATH="$(pwd)"` puts the repo root on Python's import path so the package-relative
imports (`from ..common...`) resolve; `-m` runs the file **as a module in its package** so
those `..` imports have a package context. Both stream live and record their run into the
shared usage ledger (subscription billing). Each uses a throwaway temp dir and cleans it up.
```
