# 08 - Features of Claude

Exercises exploring Claude's advanced API features: extended thinking, vision, PDF support, citations, prompt caching, and code execution.

## Files

- `extended_thinking.py` — enables thinking, prints both the reasoning and final answer, handles redacted thinking blocks
- `vision.py` — sends a base64-encoded image with a text prompt, prints Claude's analysis
- `pdf.py` — sends a base64-encoded PDF with a text prompt, prints Claude's summary
- `citations.py` — enables citations on a PDF, prints inline markers and a references section
- `caching.py` — demonstrates prompt caching with cache breakpoints, compares cache write vs read usage

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

### Vision

Claude can analyze images included in user messages. Images are sent as content blocks alongside text blocks within a single message.

#### Sending Images

Two source types are supported:

- **Base64** — encode the file bytes and include them inline
- **URL** — pass a direct link to the image

```python
import base64

with open("image.png", "rb") as f:
    image_bytes = base64.standard_b64encode(f.read()).decode("utf-8")

add_user_message(messages, [
    {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": image_bytes,
        },
    },
    {"type": "text", "text": "What do you see in this image?"},
])
```

#### Limits

- Up to **100 images** across all messages in a single request
- Max **5 MB** per image
- Single image: max 8000px height/width
- Multiple images: max 2000px height/width
- Supported formats: PNG, JPEG, GIF, WebP

#### Token Cost

Each image counts as tokens based on its dimensions: `tokens = (width × height) / 750`.

#### Prompting Tips

The same prompt engineering techniques that work for text apply to images — structured step-by-step instructions, one-shot examples, and breaking complex analysis into smaller steps all improve accuracy significantly over simple questions.

### PDF Support

Claude can read and analyze PDF files directly. The API shape is nearly identical to images — the differences are the block type and media type.

#### Sending PDFs

```python
import base64

with open("document.pdf", "rb") as f:
    file_bytes = base64.standard_b64encode(f.read()).decode("utf-8")

add_user_message(messages, [
    {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": file_bytes,
        },
    },
    {"type": "text", "text": "Summarize the document in one sentence."},
])
```

#### Differences from Images

| | Images | PDFs |
|---|---|---|
| Block type | `"image"` | `"document"` |
| Media type | `"image/png"`, `"image/jpeg"`, etc. | `"application/pdf"` |
| SDK param type | `ImageBlockParam` | `DocumentBlockParam` |

#### What Claude Can Extract

Beyond plain text, Claude can analyze images, charts, tables, and document structure embedded in PDFs — making it a single tool for full document understanding.

### Citations

Citations let Claude reference specific parts of source documents, creating a verifiable trail from response back to source material.

#### Enabling Citations

Add `title` and `citations` fields to a document block:

```python
{
    "type": "document",
    "source": {
        "type": "base64",
        "media_type": "application/pdf",
        "data": file_bytes,
    },
    "title": "earth.pdf",
    "citations": {"enabled": True},
}
```

Works with both PDFs and plain text (`"media_type": "text/plain"`).

#### Response Structure

With citations enabled, `response.content` contains multiple `TextBlock`s — each with a `text` field and a `citations` list. The response is broken into small fragments, each citing the specific source passage it draws from.

Each citation contains:

- **`cited_text`** — the exact text from the source document
- **`document_index`** — which document (when multiple are provided)
- **`document_title`** — the title you assigned

Location fields depend on the source type:

| Source | Location type | Fields |
|---|---|---|
| PDF | `CitationPageLocation` | `start_page_number`, `end_page_number` |
| Plain text | `CitationCharLocation` | `start_char_index`, `end_char_index` |

#### Formatting Cited Text

Text extracted from PDFs contains line breaks from the page layout. Collapse whitespace before displaying:

```python
cited_text = " ".join(citation.cited_text.split())
```

### Prompt Caching

Prompt caching speeds up responses and reduces cost by reusing computational work from previous requests. Instead of reprocessing the same content every time, Claude saves the work and serves it from cache on follow-up requests.

#### How It Works

Caching is a **prefix match**. The API processes your request in a fixed order — **tools → system prompt → messages** — and caches everything up to a `cache_control` breakpoint. On the next request, if the content up to that breakpoint is byte-identical, the cached work is reused.

Any change before a breakpoint — even a single character — invalidates the cache for that breakpoint and everything after it.

#### Cache Breakpoints

Add `cache_control` to a content block to mark the cache boundary:

```python
system = [
    {
        "type": "text",
        "text": "You are an expert coding assistant...",
        "cache_control": {"type": "ephemeral"},
    }
]
```

Since tools render before the system prompt, a breakpoint on the system block caches both tools and system together.

Rules:
- Max **4 breakpoints** per request
- Minimum cacheable prefix depends on the model (e.g., 2048 tokens for Sonnet 4.6)
- Only the longhand block form supports `cache_control` — plain strings don't have a place for it

#### Breakpoint Strategy

You don't need a breakpoint on every block — one breakpoint caches everything before it. Place them at **stability boundaries**:

1. Breakpoint on last tool → caches all tools
2. Breakpoint on system prompt → caches tools + system
3. Breakpoint on last stable message → caches the conversation prefix
4. One spare for mid-conversation use

In a conversation loop, "move" the breakpoint by placing `cache_control` on the latest turn's last content block each time. The growing history before it is included in the prefix automatically.

#### TTL and Pricing

| TTL | Write cost | Read cost | Syntax |
|---|---|---|---|
| 5 minutes (default) | 1.25× input rate | 0.1× input rate | `{"type": "ephemeral"}` |
| 1 hour | 2× input rate | 0.1× input rate | `{"type": "ephemeral", "ttl": "1h"}` |

Break-even with 5-minute TTL is just 2 requests (1.25× + 0.1× = 1.35× vs 2× uncached).

#### Verifying Cache Hits

The response `usage` object reports cache activity:

| Field | Meaning |
|---|---|
| `cache_creation_input_tokens` | Tokens written to cache (paid write premium) |
| `cache_read_input_tokens` | Tokens served from cache (paid 0.1×) |
| `input_tokens` | Tokens processed at full price (uncached remainder) |

Total prompt size = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.

#### Best Candidates for Caching

- **System prompts** — rarely change between requests
- **Tool definitions** — same tools across an entire conversation
- **Conversation history** — grows each turn but the prefix stays stable
- **Large documents** — when asking multiple questions about the same content
