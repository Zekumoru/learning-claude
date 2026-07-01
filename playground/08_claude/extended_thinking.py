from anthropic.types import (
    MessageParam,
    ThinkingBlock,
    TextBlock,
    RedactedThinkingBlock,
)
from ..common.chat import chat, add_user_message
from ..common.renderer import print_usage

messages: list[MessageParam] = []

add_user_message(messages, "How many r's in the word 'strawberry'?")

# 4.6+ models (incl. Sonnet 5) replace the legacy {type: "enabled", budget_tokens}
# config with adaptive thinking; the model chooses how much to think.
response = chat(messages, thinking={"type": "adaptive"})

print_usage(response)

for block in response.content:
    match block:
        case ThinkingBlock():
            print(f"\n\033[36m[Thinking]\033[0m\n{block.thinking}\n")
        case RedactedThinkingBlock():
            print(
                f"\n\033[31m[Redacted Thinking]\033[0m\n(encrypted, {len(block.data)} chars)\n"
            )
        case TextBlock():
            print(f"\n\033[32m[Response]\033[0m\n{block.text}\n")
