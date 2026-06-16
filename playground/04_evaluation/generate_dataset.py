from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message
from pydantic import BaseModel, TypeAdapter
from pathlib import Path
from typing import Literal


class TestCase(BaseModel):
    task: str
    format: Literal["python", "json", "regex"]


class TestCases(BaseModel):
    test_cases: list[TestCase]


def generate_dataset():
    prompt = """
Generate an evaluation dataset for a prompt evaluation. The dataset will be used to evaluate prompts that generate Python, JSON, or Regex specifically for AWS-related tasks. Generate an array of JSON objects, each representing task that requires Python, JSON, or a Regex to complete.

Example output:
```json
[
    {
        "task": "Description of task",
        "format": "python"
    },
    ...additional
]
```

* Focus on tasks that can be solved by writing a single Python function, a single JSON object, or a single regex.
* Focus on tasks that do not require writing much code.

Please generate 3 objects.
"""

    messages: list[MessageParam] = []
    add_user_message(messages, prompt)

    output = chat(messages, output_format=TestCases)
    return output.test_cases


if __name__ == "__main__":
    dataset = generate_dataset()
    json_str = TypeAdapter(list[TestCase]).dump_json(dataset, indent=2).decode()
    output_path = Path(__file__).parent / "dataset.json"
    output_path.write_text(json_str)
    print(f"Dataset saved to {output_path}")
