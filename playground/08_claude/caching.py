from anthropic.types import MessageParam, ToolUnionParam, TextBlockParam, Usage
from ..common.chat import (
    client,
    model,
    max_tokens,
    add_user_message,
    text_from_message,
)
from ..common.renderer import (
    color,
    RED,
    GREEN,
    YELLOW,
    CYAN,
)
from ..common.tools import read_media_schema, text_editor_schema

system: list[TextBlockParam] = [
    {
        "type": "text",
        "text": (
            "You are an expert coding assistant. You help users write clean, "
            "well-structured code. You analyze code for bugs, suggest "
            "improvements, and explain complex concepts clearly."
        ),
        "cache_control": {"type": "ephemeral"},
    }
]

# Use tool schema to reach the minimum required tokens for caching,
# which is 2048 for Sonnet 4.6 at the time of writing.
tools: list[ToolUnionParam] = [read_media_schema, text_editor_schema]


def print_cache_creation_input_tokens(usage: Usage):
    tokens = usage.cache_creation_input_tokens or 0
    msg = f"  cache_creation_input_tokens: {usage.cache_creation_input_tokens}"
    print(color(msg, RED) if tokens > 0 else msg)


def print_cache_read_input_tokens(usage: Usage):
    tokens = usage.cache_read_input_tokens or 0
    msg = f"  cache_read_input_tokens:     {usage.cache_read_input_tokens}"
    print(color(msg, GREEN) if tokens > 0 else msg)


messages: list[MessageParam] = []

prompt = "What tools do you have?"

add_user_message(messages, prompt)

print(color("--- Prompt ---", CYAN))
print(prompt)

print()

print(color("--- Request 1 (expects cache WRITE) ---", YELLOW))
response1 = client.messages.create(
    model=model, max_tokens=max_tokens, system=system, tools=tools, messages=messages
)

usage1 = response1.usage
print(f"  input_tokens:                {usage1.input_tokens}")
print_cache_creation_input_tokens(usage1)
print_cache_read_input_tokens(usage1)
print(f"  output_tokens:               {usage1.output_tokens}")

print()

print(color("--- Request 2 (expects cache READ) ---", YELLOW))
response2 = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=system,
    tools=tools,
    messages=messages,
)

usage2 = response2.usage
print(f"  input_tokens:                {usage2.input_tokens}")
print_cache_creation_input_tokens(usage2)
print_cache_read_input_tokens(usage2)
print(f"  output_tokens:               {usage2.output_tokens}")

print()

print(color("--- Response 1 ---", CYAN))
print(f"Response: {text_from_message(response1)}")

print()

print(color("--- Response 2 ---", CYAN))
print(f"Response: {text_from_message(response2)}")
