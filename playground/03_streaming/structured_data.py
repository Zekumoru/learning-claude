from anthropic.types import MessageParam
from ..common.chat import (
    client,
    model,
    max_tokens,
    chat,
    add_user_message,
    add_assistant_message,
    text_from_message,
)

messages: list[MessageParam] = []

add_user_message(messages, "Generate a very short event bridge rule as json.")


# Does not work in most of the new models
def generate_with_prefill():
    add_assistant_message(messages, "```json")
    result = chat(messages, stop_sequences=["```"])
    print(text_from_message(result))


def generate_with_output_config():
    # Create JSON schema with Pydantic
    from pydantic import BaseModel, Field

    class Detail(BaseModel):
        state: list[str]

    class EventBridgeRule(BaseModel):
        source: list[str]
        detail_type: list[str] = Field(alias="detail-type")
        detail: Detail

    response = client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        output_format=EventBridgeRule,
    )

    rule = response.parsed_output
    print(rule)


generate_with_output_config()
