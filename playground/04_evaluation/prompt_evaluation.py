from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message
from pydantic import BaseModel, TypeAdapter
import json


class TestCase(BaseModel):
    task: str


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


def run_prompt(test_case: TestCase):
    """Merges the prompt and test case input, then returns the result"""
    prompt = f"""
Please solve the following task:

{test_case.task}
"""

    messages: list[MessageParam] = []
    add_user_message(messages, prompt)
    output = chat(messages)
    return output


class EvalResult(BaseModel):
    output: str
    test_case: TestCase
    score: float


def run_test_case(test_case: TestCase) -> EvalResult:
    """Calls run_prompt, then grades the result"""
    output = run_prompt(test_case)

    # TODO: Grading
    score = 10

    return EvalResult(output=output, test_case=test_case, score=score)


def run_eval(dataset: list[TestCase]) -> list[EvalResult]:
    """Loads the dataset and calls run_test_case with each case"""
    results = []

    for test_case in dataset:
        result = run_test_case(test_case)
        results.append(result)

    return results


dataset = generate_dataset()
print(dataset)

results = run_eval(dataset)
json_str = TypeAdapter(list[EvalResult]).dump_json(results, indent=2).decode()
print(json_str)
