from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message
from .generate_dataset import TestCase
from .report import write_html_report
from pydantic import BaseModel, TypeAdapter
from pathlib import Path
import json


class EvalResult(BaseModel):
    output: str
    test_case: TestCase
    score: float


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


dataset_path = Path(__file__).parent / "dataset.json"
raw = json.loads(dataset_path.read_text())
dataset = TypeAdapter(list[TestCase]).validate_python(raw)

results = run_eval(dataset)
write_html_report(results)
