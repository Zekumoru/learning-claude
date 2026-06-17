from anthropic.types import MessageParam, ToolUseBlock, TextBlock
from ..common.chat import (
    client,
    model,
    max_tokens,
    add_user_message,
)
from .tools import get_current_datetime, get_current_datetime_schema
from typing import cast, Any
import sys

messages: list[MessageParam] = []

add_user_message(messages, "What is the exact time, formatted as HH:MM:SS?")

result = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    messages=messages,
    tools=[get_current_datetime_schema],
)

messages.append({"role": "assistant", "content": result.content})

tool_use = next(
    (block for block in result.content if isinstance(block, ToolUseBlock)), None
)

if tool_use is None:
    sys.exit("Could not find tool use block")

current_datetime = get_current_datetime(**cast(Any, tool_use.input))

messages.append(
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": current_datetime,
                "is_error": False,
            }
        ],
    }
)

result = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    messages=messages,
    tools=[get_current_datetime_schema],
)

reply = result.content[0]

if not isinstance(reply, TextBlock):
    sys.exit("Missing text block")

print(reply.text)
