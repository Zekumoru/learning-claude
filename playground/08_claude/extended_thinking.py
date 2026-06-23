from anthropic.types import MessageParam, ThinkingBlock, TextBlock
from ..common.chat import chat, max_tokens, print_usage, add_user_message

budget_tokens = int(max_tokens / 2)
messages: list[MessageParam] = []

add_user_message(messages, "How many r's in the word 'strawberry'?")

response = chat(messages, thinking={"type": "enabled", "budget_tokens": budget_tokens})

print_usage(response)

for block in response.content:
    if isinstance(block, ThinkingBlock):
        print(f"\n\033[36m[Thinking]\033[0m\n{block.thinking}\n")
    elif isinstance(block, TextBlock):
        print(f"\n\033[32m[Response]\033[0m\n{block.text}\n")
