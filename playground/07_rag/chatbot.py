from anthropic.types import MessageParam
from ..common.chat import add_user_message, run_conversation_stream
from .tools import tools, run_tool

system = """\
You have access to tools for reading and searching files.

When asked about a file's contents:
1. Use get_file_info to check its size first.
2. If the file is small (under 500 lines and 10,000 characters), read it directly with the text editor.
3. If the file is large, use rag_search to find relevant chunks instead of reading the whole file.

Always prefer rag_search for targeted questions about large files — it's faster and uses less context.\
"""

messages: list[MessageParam] = []

print("\033[33mRAG chatbot ready.\033[0m\n")

while True:
    user_input = input("\033[32m|:\033[0m ")
    print()

    if user_input == "exit":
        break

    add_user_message(messages, user_input)
    run_conversation_stream(
        messages, system=system, tools=tools, run_tool_callback=run_tool
    )
