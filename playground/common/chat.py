from dotenv import load_dotenv

load_dotenv()

from typing import TypeVar, overload, cast, Any
from pydantic import BaseModel
from anthropic import Anthropic
from anthropic.types import (
    ModelParam,
    MessageParam,
    TextBlock,
    MessageCreateParams,
)

model: ModelParam = "claude-sonnet-4-6"
max_tokens = 1024

client = Anthropic()


def add_user_message(messages: list[MessageParam], text: str) -> None:
    messages.append({"role": "user", "content": text})


def add_assistant_message(messages: list[MessageParam], text: str) -> None:
    messages.append({"role": "assistant", "content": text})


TOutput = TypeVar("TOutput", bound=BaseModel)


@overload
def chat(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    output_format: None = None,
) -> str: ...


@overload
def chat(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    output_format: type[TOutput],
) -> TOutput: ...


def chat(
    messages: list[MessageParam],
    *,
    system: str | None = None,
    temperature: float | None = None,
    stop_sequences: list[str] | None = None,
    output_format: type[TOutput] | None = None,
) -> str | TOutput:
    params: MessageCreateParams = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if system is not None:
        params["system"] = system

    if temperature is not None:
        params["temperature"] = temperature

    if stop_sequences is not None:
        params["stop_sequences"] = stop_sequences

    if output_format is not None:
        response = client.messages.parse(
            **cast(Any, params), output_format=output_format
        )

        parsed = response.parsed_output

        if not isinstance(parsed, output_format):
            raise TypeError(f"Expected parsed output of type {output_format.__name__}")

        return parsed

    message = client.messages.create(**params)

    first_block = message.content[0]

    if not isinstance(first_block, TextBlock):
        raise TypeError("Expected a text response block")

    return first_block.text
