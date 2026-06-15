from anthropic.types import MessageParam
from ..common.chat import (
    client,
    model,
    max_tokens,
    add_user_message,
)

messages: list[MessageParam] = []

# The exercise is to return a valid JSON without any commentary for three
# different sample AWS CLI commands.
# Though, the lesson expects prefilling to solve this problem and most newer
# models don't use it anymore since they've gotten smarter (as stated by the
# docs) and prefer using output_format, to which I'll do here.
add_user_message(
    messages,
    "Generate three different sample AWS CLI commands. Each should be very short.",
)


from pydantic import BaseModel


class AwsCliCommands(BaseModel):
    commands: list[str]


response = client.messages.parse(
    model=model, max_tokens=max_tokens, messages=messages, output_format=AwsCliCommands
)

output = response.parsed_output
if output:
    for command in output.commands:
        print(command)
else:
    print("Error: Missing JSON output")
