# 08 - Features of Claude

Exercises exploring Claude's advanced API features: extended thinking, vision, PDF support, citations, prompt caching, and code execution.

## Files

- `extended_thinking.py` — enables thinking, prints both the reasoning and final answer, handles redacted thinking blocks

## Concepts Learned

### Extended Thinking

Extended thinking gives Claude a "scratch pad" to reason through complex problems before generating a final response. Instead of producing an answer in one shot, the response comes in two parts:

1. **Thinking block** — Claude's internal reasoning process (visible to the developer)
2. **Text block** — the final answer, informed by that reasoning

Enable it by passing a `thinking` config to the API:

```python
response = chat(
    messages,
    thinking={"type": "enabled", "budget_tokens": 2048},
)
```

- `budget_tokens` — maximum tokens Claude can use for reasoning (minimum: 1024)
- `max_tokens` must be **greater than** `budget_tokens`

#### When to Use

Don't default to it. Run prompts without thinking first, optimize the prompt itself, and only enable thinking when accuracy still isn't where you need it. It increases both cost (you pay for thinking tokens) and latency.

#### Incompatibilities

Extended thinking is **not compatible** with:

- Temperature (must be omitted or default)
- Message pre-filling (starting assistant responses)

#### Response Handling

With thinking enabled, `response.content` contains a mix of block types:

- **`ThinkingBlock`** — has `thinking` (the reasoning text) and `signature` (cryptographic proof the thinking wasn't tampered with)
- **`RedactedThinkingBlock`** — appears when internal safety systems flag the reasoning. Contains encrypted `data` you can't read, but must pass back as-is in multi-turn conversations so Claude doesn't lose context
- **`TextBlock`** — the final answer

```python
for block in response.content:
    match block:
        case ThinkingBlock():
            print(block.thinking)
        case RedactedThinkingBlock():
            print(f"(encrypted, {len(block.data)} chars)")
        case TextBlock():
            print(block.text)
```

#### Signatures

Each thinking block includes a cryptographic `signature`. When you pass a conversation back to Claude in a multi-turn flow, the API verifies this signature to ensure no one modified the reasoning. This prevents tampering with Claude's thought process.

#### Display Options

The `display` parameter controls how thinking content is returned:

| Option | Behavior | Use case |
|---|---|---|
| `"summarized"` | Returns a readable summary of the thinking | Debugging, transparency |
| `"omitted"` | Returns an empty `thinking` field with only the `signature` | Production apps that never surface thinking to users; faster time-to-first-text-token when streaming |

Both options still charge for full thinking tokens — `display` only affects what's transmitted, not what's computed.
