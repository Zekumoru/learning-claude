from anthropic.types import MessageParam, ToolUnionParam
from ..common.chat import run_conversation_stream, add_user_message, color, YELLOW
from ..common.tools import (
    run_tool,
    read_media_schema,
    text_editor_schema,
)

messages: list[MessageParam] = []

tools: list[ToolUnionParam] = [
    read_media_schema,
    text_editor_schema,
]

print(
    color(
        "Chatbot with adaptive thinking, images and documents. Type 'exit' to quit.\n",
        YELLOW,
    )
)

while True:
    user_input = input("\033[36m|:\033[0m ")

    if user_input.strip().lower() == "exit":
        break

    add_user_message(messages, user_input)
    run_conversation_stream(
        messages, thinking={"type": "adaptive"}, tools=tools, run_tool_callback=run_tool
    )
    print()
