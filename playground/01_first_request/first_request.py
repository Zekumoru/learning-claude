from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic
from anthropic.types import ModelParam

client = Anthropic()
model: ModelParam = "claude-sonnet-4-6"

message = client.messages.create(
    model=model,
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "What is quantum computing? Answer in one sentence.",
        }
    ],
)

if message.content[0].type == "text":
    print(message.content[0].text)
else:
    print("Expected text response, but got:", message.content[0].type)
